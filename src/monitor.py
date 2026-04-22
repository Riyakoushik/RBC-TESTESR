"""
System monitoring for CPU, RAM, and disk usage.
Provides real-time metrics for the conversion pipeline.
"""

import time
import psutil
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from .config import get_config


@dataclass
class SystemMetrics:
    """Container for system resource metrics."""
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_percent: float
    disk_free_gb: float
    timestamp: datetime


class SystemMonitor:
    """
    Monitors system resources during conversion.
    Provides methods to check resource thresholds and get formatted metrics.
    """
    
    def __init__(self):
        self.config = get_config()
        self.process = psutil.Process()
        self.start_time = time.time()
        self.files_processed = 0
        self.bytes_processed = 0
        self._last_check = time.time()
        self._check_interval = 1.0  # Minimum seconds between checks
    
    def get_metrics(self) -> SystemMetrics:
        """
        Get current system metrics.
        
        Returns:
            SystemMetrics with current values
        """
        # Avoid calling too frequently
        now = time.time()
        if now - self._last_check < self._check_interval:
            # Return cached values if checked too recently
            pass
        
        self._last_check = now
        
        # Get disk usage for output directory
        config = get_config()
        output_path = config.paths.output_dir
        try:
            disk_usage = psutil.disk_usage(output_path)
            disk_percent = disk_usage.percent
            disk_free_gb = disk_usage.free / (1024**3)
        except Exception:
            # Fallback to root disk if output dir not accessible
            disk_usage = psutil.disk_usage('/')
            disk_percent = disk_usage.percent
            disk_free_gb = disk_usage.free / (1024**3)
        
        # Memory info
        memory = psutil.virtual_memory()
        
        metrics = SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=0.1),
            memory_percent=memory.percent,
            memory_available_mb=memory.available / (1024**2),
            disk_percent=disk_percent,
            disk_free_gb=disk_free_gb,
            timestamp=datetime.now()
        )
        
        return metrics
    
    def should_pause(self) -> bool:
        """
        Check if processing should pause due to resource constraints.
        
        Returns:
            True if memory or CPU exceeds configured thresholds
        """
        metrics = self.get_metrics()
        config = self.config.processing
        
        # Check memory threshold
        if metrics.memory_percent > config.max_memory_percent:
            logger.warning(f"Memory usage {metrics.memory_percent:.1f}% exceeds threshold {config.max_memory_percent}%")
            return True
        
        # Check CPU threshold (0 = no limit)
        if config.max_cpu_percent > 0 and metrics.cpu_percent > config.max_cpu_percent:
            logger.warning(f"CPU usage {metrics.cpu_percent:.1f}% exceeds threshold {config.max_cpu_percent}%")
            return True
        
        return False
    
    def wait_for_resources(self, timeout: Optional[float] = None) -> bool:
        """
        Wait until resources are below threshold.
        
        Args:
            timeout: Maximum time to wait in seconds
        
        Returns:
            True if resources available, False if timeout
        """
        start = time.time()
        check_interval = 2.0
        
        while self.should_pause():
            if timeout and (time.time() - start) > timeout:
                logger.error("Timeout waiting for resources")
                return False
            
            logger.info(f"Waiting for resources to free up...")
            time.sleep(check_interval)
        
        return True
    
    def update_progress(self, files_increment: int = 1, bytes_increment: int = 0) -> None:
        """Update processing counters."""
        self.files_processed += files_increment
        self.bytes_processed += bytes_increment
    
    def get_throughput(self) -> Dict[str, Any]:
        """
        Calculate processing throughput metrics.
        
        Returns:
            Dict with files/minute, bytes/second, etc.
        """
        elapsed = time.time() - self.start_time
        if elapsed < 1:
            elapsed = 1  # Avoid division by zero
        
        files_per_minute = (self.files_processed / elapsed) * 60
        bytes_per_second = self.bytes_processed / elapsed
        
        return {
            "elapsed_seconds": elapsed,
            "files_per_minute": round(files_per_minute, 2),
            "bytes_per_second": round(bytes_per_second, 2),
            "files_processed": self.files_processed
        }
    
    def estimate_remaining_time(self, total_files: int, pending_files: int) -> str:
        """
        Estimate time to complete remaining files.
        
        Args:
            total_files: Total number of files
            pending_files: Number of files remaining
        
        Returns:
            Formatted ETA string
        """
        if self.files_processed == 0 or pending_files == 0:
            return "calculating..."
        
        elapsed = time.time() - self.start_time
        avg_time_per_file = elapsed / self.files_processed
        estimated_remaining = avg_time_per_file * pending_files
        
        # Format nicely
        if estimated_remaining < 60:
            return f"{estimated_remaining:.0f}s"
        elif estimated_remaining < 3600:
            return f"{estimated_remaining/60:.1f}m"
        else:
            return f"{estimated_remaining/3600:.1f}h"
    
    def get_formatted_metrics(self) -> Dict[str, str]:
        """
        Get metrics formatted for display.
        
        Returns:
            Dict with formatted string values
        """
        metrics = self.get_metrics()
        throughput = self.get_throughput()
        
        return {
            "cpu": f"{metrics.cpu_percent:.1f}%",
            "memory": f"{metrics.memory_percent:.1f}%",
            "memory_available": f"{metrics.memory_available_mb:.0f} MB",
            "disk_usage": f"{metrics.disk_percent:.1f}%",
            "disk_free": f"{metrics.disk_free_gb:.1f} GB",
            "files_per_min": f"{throughput['files_per_minute']:.1f}"
        }


class ProgressTracker:
    """
    Tracks conversion progress with timing and ETA calculation.
    Integrates with Rich for live display.
    """
    
    def __init__(self, total_files: int):
        self.total_files = total_files
        self.processed = 0
        self.successful = 0
        self.failed = 0
        self.start_time = time.time()
        self.current_file: Optional[str] = None
        self.total_text_bytes = 0
    
    def start_file(self, file_path: str) -> None:
        """Mark start of processing a file."""
        self.current_file = file_path
    
    def complete_file(self, success: bool, text_size: int = 0) -> None:
        """Mark completion of current file."""
        self.processed += 1
        self.total_text_bytes += text_size
        
        if success:
            self.successful += 1
        else:
            self.failed += 1
        
        self.current_file = None
    
    def get_progress_percent(self) -> float:
        """Get completion percentage."""
        if self.total_files == 0:
            return 100.0
        return (self.processed / self.total_files) * 100
    
    def get_eta(self) -> str:
        """Calculate estimated time remaining."""
        if self.processed == 0:
            return "--:--"
        
        elapsed = time.time() - self.start_time
        avg_time = elapsed / self.processed
        remaining = avg_time * (self.total_files - self.processed)
        
        # Format as HH:MM:SS or MM:SS
        if remaining >= 3600:
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            return f"{hours}h {minutes}m"
        elif remaining >= 60:
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            return f"{minutes}m {seconds}s"
        else:
            return f"{int(remaining)}s"
    
    def get_elapsed(self) -> str:
        """Get elapsed time string."""
        elapsed = time.time() - self.start_time
        
        if elapsed >= 3600:
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            return f"{hours}h {minutes}m"
        elif elapsed >= 60:
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            return f"{minutes}m {seconds}s"
        else:
            return f"{int(elapsed)}s"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get all statistics."""
        return {
            "total": self.total_files,
            "processed": self.processed,
            "successful": self.successful,
            "failed": self.failed,
            "percent": self.get_progress_percent(),
            "eta": self.get_eta(),
            "elapsed": self.get_elapsed(),
            "total_text_mb": round(self.total_text_bytes / (1024 * 1024), 2)
        }
