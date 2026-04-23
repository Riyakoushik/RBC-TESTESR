"""
API routes for the RBC-TESTER Web Dashboard.
Provides endpoints for stats, progress, management, timeline, and graph data.
"""

import os
import sys
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

# Ensure project root is on path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import get_config, get_project_root
from src.utils import detect_file_type, get_input_files, ConversionState

router = APIRouter()

# Global state for tracking active conversions
_conversion_state = {
    "running": False,
    "thread": None,
    "progress": {
        "total": 0,
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "current_file": "",
        "started_at": None,
        "eta_seconds": None,
    },
    "logs": [],
}
_MAX_LOGS = 500


def _add_log(level: str, message: str):
    """Add a log entry to the in-memory log buffer."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
    }
    _conversion_state["logs"].append(entry)
    if len(_conversion_state["logs"]) > _MAX_LOGS:
        _conversion_state["logs"] = _conversion_state["logs"][-_MAX_LOGS:]


# ---- Stats endpoints ----

@router.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get overall conversion statistics."""
    config = get_config()
    root = get_project_root()

    input_dir = root / config.paths.input_dir
    output_dir = root / config.paths.output_dir

    # Count input files
    input_files = []
    if input_dir.exists():
        input_files = get_input_files()

    # Count output files
    output_files = []
    output_size = 0
    if output_dir.exists():
        for f in output_dir.rglob("*"):
            if f.is_file():
                output_files.append(str(f))
                output_size += f.stat().st_size

    # File type breakdown
    type_counts: Dict[str, int] = {}
    for fp in input_files:
        ft = detect_file_type(fp)
        type_counts[ft] = type_counts.get(ft, 0) + 1

    # Conversion state
    state = ConversionState()

    # Knowledge system stats
    knowledge_stats = {}
    try:
        from src.cache_manager import CacheManager
        cache = CacheManager()
        knowledge_stats = cache.get_stats()
    except Exception:
        pass

    return {
        "input_files": len(input_files),
        "output_files": len(output_files),
        "output_size_mb": round(output_size / (1024 * 1024), 2),
        "completed": len(state.completed),
        "failed": len(state.failed),
        "pending": len(input_files) - len(state.completed) - len(state.failed),
        "file_types": type_counts,
        "knowledge": knowledge_stats,
    }


@router.get("/stats/system")
async def get_system_stats() -> Dict[str, Any]:
    """Get system resource usage."""
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / (1024**3), 2),
        "memory_total_gb": round(memory.total / (1024**3), 2),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024**3), 2),
        "disk_total_gb": round(disk.total / (1024**3), 2),
    }


# ---- Progress endpoints ----

@router.get("/progress")
async def get_progress() -> Dict[str, Any]:
    """Get current conversion progress."""
    progress = _conversion_state["progress"].copy()
    progress["running"] = _conversion_state["running"]

    # Calculate ETA
    if progress["running"] and progress["started_at"] and progress["processed"] > 0:
        elapsed = time.time() - progress["started_at"]
        rate = progress["processed"] / elapsed
        remaining = progress["total"] - progress["processed"]
        progress["eta_seconds"] = round(remaining / rate) if rate > 0 else None
        progress["percent"] = round(
            (progress["processed"] / progress["total"]) * 100, 1
        ) if progress["total"] > 0 else 0
    else:
        progress["percent"] = 0

    return progress


# ---- File listing ----

@router.get("/files")
async def list_files(
    status: Optional[str] = None,
    file_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """List input files with optional filtering."""
    input_files = get_input_files()
    state = ConversionState()

    files_data = []
    for fp in input_files:
        ft = detect_file_type(fp)
        file_status = "pending"
        if fp in state.completed:
            file_status = "completed"
        elif fp in state.failed:
            file_status = "failed"

        # Apply filters
        if status and file_status != status:
            continue
        if file_type and ft != file_type:
            continue

        try:
            size = os.path.getsize(fp)
        except OSError:
            size = 0

        files_data.append({
            "path": fp,
            "name": Path(fp).name,
            "type": ft,
            "status": file_status,
            "size_kb": round(size / 1024, 1),
        })

    total = len(files_data)
    files_data = files_data[offset:offset + limit]

    return {
        "total": total,
        "files": files_data,
        "limit": limit,
        "offset": offset,
    }


# ---- Conversion management ----

class ConversionRequest(BaseModel):
    """Request body for starting a conversion."""
    files: Optional[List[str]] = None


@router.post("/convert/start")
async def start_conversion(
    request: Optional[ConversionRequest] = None,
    background_tasks: BackgroundTasks = None,
) -> Dict[str, str]:
    """Start a conversion job."""
    if _conversion_state["running"]:
        raise HTTPException(status_code=409, detail="Conversion already running")

    def run_conversion():
        try:
            from src.converter import DocumentConverterPipeline, BatchProcessor
            from src.monitor import ProgressTracker

            _conversion_state["running"] = True
            _add_log("INFO", "Conversion started")

            files = get_input_files()
            if request and request.files:
                files = [f for f in files if f in request.files]

            state = ConversionState()
            pending = state.get_pending_files(files)

            _conversion_state["progress"]["total"] = len(pending)
            _conversion_state["progress"]["processed"] = 0
            _conversion_state["progress"]["successful"] = 0
            _conversion_state["progress"]["failed"] = 0
            _conversion_state["progress"]["started_at"] = time.time()

            processor = BatchProcessor()

            for i, file_path in enumerate(pending):
                if not _conversion_state["running"]:
                    _add_log("INFO", "Conversion stopped by user")
                    break

                _conversion_state["progress"]["current_file"] = Path(file_path).name
                _add_log("INFO", f"Processing: {Path(file_path).name}")

                try:
                    output_path, success = processor.converter.convert_file(file_path)
                    if success:
                        _conversion_state["progress"]["successful"] += 1
                        _add_log("INFO", f"Success: {Path(file_path).name}")
                    else:
                        _conversion_state["progress"]["failed"] += 1
                        _add_log("WARNING", f"Failed: {Path(file_path).name}")
                except Exception as e:
                    _conversion_state["progress"]["failed"] += 1
                    _add_log("ERROR", f"Error processing {Path(file_path).name}: {e}")

                _conversion_state["progress"]["processed"] = i + 1

            # Finalize batch (rebuild timeline once)
            processor.converter.finalize_batch()

            _add_log("INFO", f"Conversion complete: {_conversion_state['progress']['successful']} succeeded, {_conversion_state['progress']['failed']} failed")

        except Exception as e:
            _add_log("ERROR", f"Conversion error: {e}")
        finally:
            _conversion_state["running"] = False
            _conversion_state["progress"]["current_file"] = ""

    thread = threading.Thread(target=run_conversion, daemon=True)
    _conversion_state["thread"] = thread
    thread.start()

    return {"status": "started"}


@router.post("/convert/stop")
async def stop_conversion() -> Dict[str, str]:
    """Stop the running conversion."""
    if not _conversion_state["running"]:
        raise HTTPException(status_code=400, detail="No conversion running")

    _conversion_state["running"] = False
    _add_log("INFO", "Stop requested")
    return {"status": "stopping"}


@router.post("/convert/retry")
async def retry_failed(background_tasks: BackgroundTasks = None) -> Dict[str, str]:
    """Retry all failed files."""
    if _conversion_state["running"]:
        raise HTTPException(status_code=409, detail="Conversion already running")

    state = ConversionState()
    failed_files = list(state.failed)

    if not failed_files:
        return {"status": "no_failed_files"}

    # Clear failed status so they can be reprocessed
    for fp in failed_files:
        state.failed.discard(fp)
    state.save()

    _add_log("INFO", f"Retrying {len(failed_files)} failed files")

    return {"status": "retry_queued", "count": len(failed_files)}


@router.post("/convert/reset")
async def reset_state() -> Dict[str, str]:
    """Reset conversion state (clear completed and failed tracking)."""
    if _conversion_state["running"]:
        raise HTTPException(status_code=409, detail="Cannot reset while conversion is running")

    state = ConversionState()
    state.completed.clear()
    state.failed.clear()
    state.save()

    _add_log("INFO", "Conversion state reset")
    return {"status": "reset"}


# ---- Logs ----

@router.get("/logs")
async def get_logs(limit: int = 100, level: Optional[str] = None) -> Dict[str, Any]:
    """Get recent conversion logs."""
    logs = _conversion_state["logs"]

    if level:
        logs = [l for l in logs if l["level"] == level.upper()]

    logs = logs[-limit:]

    return {
        "total": len(_conversion_state["logs"]),
        "logs": logs,
    }


# ---- Knowledge system ----

@router.get("/timeline")
async def get_timeline() -> Dict[str, Any]:
    """Get timeline data from the knowledge system."""
    root = get_project_root()
    timeline_path = root / "knowledge" / "timeline" / "timeline.json"

    if timeline_path.exists():
        with open(timeline_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {"timeline": data}

    # Try loading from cache
    try:
        from src.cache_manager import CacheManager
        cache = CacheManager()
        timeline_data = cache.get_timeline_data()
        return {"timeline": timeline_data}
    except Exception:
        return {"timeline": {}}


@router.get("/graph")
async def get_graph() -> Dict[str, Any]:
    """Get knowledge graph data for visualization."""
    try:
        from src.graph_builder import GraphBuilder
        from src.cache_manager import CacheManager

        cache = CacheManager()
        graph_builder = GraphBuilder(cache)
        return graph_builder.get_graph_json()
    except Exception as e:
        # Try loading from file
        root = get_project_root()
        graph_path = root / "knowledge" / "graph.json"
        if graph_path.exists():
            with open(graph_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"nodes": [], "edges": [], "stats": {}, "error": str(e)}


@router.get("/backlinks/{file_path:path}")
async def get_file_backlinks(file_path: str) -> Dict[str, Any]:
    """Get backlinks for a specific file."""
    try:
        from src.cache_manager import CacheManager
        cache = CacheManager()
        backlinks = cache.get_file_backlinks(file_path)
        return {"file_path": file_path, "backlinks": backlinks}
    except Exception as e:
        return {"file_path": file_path, "backlinks": [], "error": str(e)}
