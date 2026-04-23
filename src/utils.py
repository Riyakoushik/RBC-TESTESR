"""
Utility functions for file handling, path management, and state persistence.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
try:
    import magic
    MAGIC_AVAILABLE = True
except (ImportError, OSError):
    MAGIC_AVAILABLE = False
from loguru import logger

from .config import get_config, get_project_root


def detect_file_type(file_path: str) -> str:
    """
    Detect file type using python-magic and extension.
    
    Args:
        file_path: Path to file to analyze
    
    Returns:
        Category: 'document', 'image', 'text', 'code', 'data', 'archive', 'ebook', 'spreadsheet', 'presentation', 'audio', 'video', or 'unknown'
    """
    config = get_config()
    ext = Path(file_path).suffix.lower()
    
    # Check extension first (faster and works without libmagic)
    if ext in config.supported_formats.email:
        return "email"
    if ext in config.supported_formats.latex:
        return "latex"
    # Google Takeout detection: .json files inside a "Takeout" directory tree
    if ext == ".json":
        parts = Path(file_path).parts
        if any(p.lower() == "takeout" for p in parts):
            return "google_takeout"
    if ext in config.supported_formats.documents:
        return "document"
    if ext in config.supported_formats.images:
        return "image"
    if ext in config.supported_formats.text:
        return "text"
    if ext in config.supported_formats.code:
        return "code"
    if ext in config.supported_formats.data:
        return "data"
    if ext in config.supported_formats.archives:
        return "archive"
    if ext in config.supported_formats.ebooks:
        return "ebook"
    if ext in config.supported_formats.spreadsheets:
        return "spreadsheet"
    if ext in config.supported_formats.presentations:
        return "presentation"
    if ext in config.supported_formats.audio:
        return "audio"
    if ext in config.supported_formats.video:
        return "video"
    
    # Fallback to mime type detection (only if python-magic available)
    if MAGIC_AVAILABLE:
        try:
            mime = magic.from_file(file_path, mime=True)
            if mime:
                if mime.startswith('image/'):
                    return "image"
                elif mime in ['application/pdf', 'application/msword', 
                             'application/vnd.openxmlformats-officedocument']:
                    return "document"
                elif mime.startswith('text/'):
                    return "text"
                elif mime.startswith('audio/'):
                    return "audio"
                elif mime.startswith('video/'):
                    return "video"
                elif mime in ['application/zip', 'application/x-tar']:
                    return "archive"
        except Exception as e:
            logger.debug(f"Mime detection failed for {file_path}: {e}")
    
    return "unknown"


def is_scanned_pdf(file_path: str) -> bool:
    """
    Detect if PDF is scanned (image-based) or contains text.
    
    Args:
        file_path: Path to PDF file
    
    Returns:
        True if PDF appears to be scanned/image-based
    """
    try:
        import fitz  # PyMuPDF

        with fitz.open(file_path) as doc:
            text_pages = 0
            image_pages = 0

            for page_num in range(min(doc.page_count, 5)):
                page = doc[page_num]

                text = page.get_text().strip()
                if len(text) > 50:
                    text_pages += 1

                images = page.get_images()
                if len(images) > 0:
                    image_pages += 1

            return image_pages > text_pages or text_pages == 0

    except Exception as e:
        logger.warning(f"Could not analyze PDF {file_path}: {e}")
        return True


def get_file_hash(file_path: str) -> str:
    """
    Calculate MD5 hash of file for tracking/verification.
    
    Args:
        file_path: Path to file
    
    Returns:
        MD5 hash string
    """
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Failed to hash {file_path}: {e}")
        return ""


def get_output_path(input_path: str, output_ext: str = ".md") -> str:
    """
    Generate output path preserving folder structure.
    
    Args:
        input_path: Original input file path
        output_ext: Desired output extension
    
    Returns:
        Output file path
    """
    config = get_config()
    project_root = get_project_root()
    
    input_path = Path(input_path).resolve()
    input_dir = (project_root / config.paths.input_dir).resolve()
    output_dir = (project_root / config.paths.output_dir).resolve()
    
    # Calculate relative path from input directory
    try:
        rel_path = input_path.relative_to(input_dir)
    except ValueError:
        # File is outside input directory, use filename only
        rel_path = Path(input_path.name)
    
    # Change extension to output format
    output_name = rel_path.stem + output_ext
    output_path = output_dir / rel_path.parent / output_name
    
    return str(output_path)


def ensure_dir(path: str) -> None:
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)


def get_input_files() -> List[str]:
    """
    Get list of all supported input files.
    
    Returns:
        List of absolute file paths
    """
    config = get_config()
    project_root = get_project_root()
    input_dir = project_root / config.paths.input_dir
    
    if not input_dir.exists():
        logger.warning(f"Input directory does not exist: {input_dir}")
        return []
    
    extensions = config.get_all_extensions()
    files = []
    
    for ext in extensions:
        pattern = f"**/*{ext}"
        files.extend(input_dir.glob(pattern))
    
    # Convert to strings and sort for consistent ordering
    return sorted([str(f.resolve()) for f in files])


def is_already_converted(input_path: str) -> bool:
    """
    Check if file has already been converted.
    
    Args:
        input_path: Original input file path
    
    Returns:
        True if output file exists
    """
    config = get_config()
    output_path = get_output_path(input_path, f".{config.processing.output_format}")
    return os.path.exists(output_path)


class ConversionState:
    """
    Manages persistent state for resumable conversions.
    Tracks completed and failed files.
    """
    
    def __init__(self, state_file: Optional[str] = None):
        config = get_config()
        project_root = get_project_root()
        
        if state_file is None:
            state_file = project_root / config.paths.state_file
        
        self.state_file = Path(state_file)
        self.completed: Set[str] = set()
        self.failed: Set[str] = set()
        self.stats: Dict = {
            "started_at": None,
            "last_updated": None,
            "total_files": 0,
            "processed": 0,
            "failed_count": 0
        }
        
        self._load()
    
    def _load(self) -> None:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.completed = set(data.get('completed', []))
                self.failed = set(data.get('failed', []))
                self.stats = data.get('stats', self.stats)
                logger.info(f"Loaded state: {len(self.completed)} completed, {len(self.failed)} failed")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
    
    def save(self) -> None:
        """Save state to file."""
        try:
            ensure_dir(self.state_file.parent)
            self.stats['last_updated'] = datetime.now().isoformat()
            
            data = {
                'completed': list(self.completed),
                'failed': list(self.failed),
                'stats': self.stats
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def mark_completed(self, file_path: str) -> None:
        """Mark file as successfully converted."""
        self.completed.add(file_path)
        self.stats['processed'] += 1
        if self.stats['started_at'] is None:
            self.stats['started_at'] = datetime.now().isoformat()
        self.save()
    
    def mark_failed(self, file_path: str) -> None:
        """Mark file as failed."""
        self.failed.add(file_path)
        self.stats['failed_count'] += 1
        self.save()
    
    def is_completed(self, file_path: str) -> bool:
        """Check if file was already processed successfully."""
        return file_path in self.completed
    
    def is_failed(self, file_path: str) -> bool:
        """Check if file previously failed."""
        return file_path in self.failed
    
    def should_process(self, file_path: str) -> bool:
        """Check if file should be processed (not completed and not skipped)."""
        config = get_config()
        
        if not config.processing.skip_existing:
            return True
        
        if self.is_completed(file_path):
            return False
        
        if config.processing.skip_existing and is_already_converted(file_path):
            return False
        
        return True
    
    def reset(self) -> None:
        """Clear all state."""
        self.completed.clear()
        self.failed.clear()
        self.stats = {
            "started_at": None,
            "last_updated": None,
            "total_files": 0,
            "processed": 0,
            "failed_count": 0
        }
        self.save()
    
    def get_pending_files(self, all_files: List[str]) -> List[str]:
        """Get list of files that still need processing."""
        self.stats['total_files'] = len(all_files)
        pending = [f for f in all_files if self.should_process(f)]
        return pending


def write_failed_files(failed_files: List[str]) -> None:
    """
    Write list of failed files to log file.
    
    Args:
        failed_files: List of file paths that failed conversion
    """
    config = get_config()
    project_root = get_project_root()
    failed_log_path = project_root / config.paths.failed_files_log
    
    try:
        with open(failed_log_path, 'w', encoding='utf-8') as f:
            f.write("# Failed Files Log\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            for file_path in failed_files:
                f.write(f"{file_path}\n")
        logger.info(f"Wrote {len(failed_files)} failed files to {failed_log_path}")
    except Exception as e:
        logger.error(f"Failed to write failed files log: {e}")


def write_summary(total: int, successful: int, failed: int, total_text: int) -> None:
    """
    Write conversion summary to JSON file.
    
    Args:
        total: Total number of files
        successful: Number of successful conversions
        failed: Number of failed conversions
        total_text: Total extracted text size in bytes
    """
    config = get_config()
    project_root = get_project_root()
    summary_path = project_root / config.paths.summary_file
    
    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_files": total,
        "successful": successful,
        "failed": failed,
        "total_text_extracted_bytes": total_text,
        "total_text_extracted_mb": round(total_text / (1024 * 1024), 2),
        "success_rate": round((successful / total * 100), 2) if total > 0 else 0
    }
    
    try:
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Wrote summary to {summary_path}")
    except Exception as e:
        logger.error(f"Failed to write summary: {e}")


def format_size(size_bytes: int) -> str:
    """Format byte size to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_duration(seconds: float) -> str:
    """Format seconds to human readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"
