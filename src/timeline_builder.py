"""
Timeline Builder for RBC-TESTER Knowledge System.
Generates timeline.json from extracted dates and file metadata.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from .config import get_config, get_project_root
from .cache_manager import CacheManager


class TimelineBuilder:
    """
    Builds and manages timeline data from file metadata.
    Creates timeline.json for chronological organization of notes.
    """
    
    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.config = get_config()
        self.project_root = get_project_root()
        
        if cache_manager is None:
            self.cache = CacheManager()
        else:
            self.cache = cache_manager
        
        self.timeline_path = self.project_root / "knowledge" / "timeline" / "timeline.json"
        self.timeline_path.parent.mkdir(parents=True, exist_ok=True)
    
    def build_timeline(self) -> Dict[str, List[str]]:
        """
        Build timeline from all cached file dates.
        
        Returns:
            Dictionary mapping normalized dates to list of file paths
        """
        try:
            # Get all dates from cache
            timeline_data = self.cache.get_timeline_data()
            
            # Sort by date (descending)
            sorted_timeline = dict(sorted(
                timeline_data.items(),
                key=lambda x: x[0],
                reverse=True
            ))
            
            # Save to JSON
            self._save_timeline(sorted_timeline)
            
            logger.info(f"Timeline built with {len(sorted_timeline)} date entries")
            return sorted_timeline
            
        except Exception as e:
            logger.error(f"Failed to build timeline: {e}")
            return {}
    
    def _save_timeline(self, timeline_data: Dict[str, List[str]]):
        """
        Save timeline data to JSON file.
        
        Args:
            timeline_data: Timeline dictionary
        """
        try:
            with open(self.timeline_path, 'w', encoding='utf-8') as f:
                json.dump(timeline_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Timeline saved to {self.timeline_path}")
            
        except Exception as e:
            logger.error(f"Failed to save timeline: {e}")
    
    def load_timeline(self) -> Dict[str, List[str]]:
        """
        Load timeline from JSON file.
        
        Returns:
            Timeline dictionary
        """
        try:
            if self.timeline_path.exists():
                with open(self.timeline_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
            
        except Exception as e:
            logger.error(f"Failed to load timeline: {e}")
            return {}
    
    def get_file_timeline_entries(self, file_path: str) -> List[str]:
        """
        Get timeline entries for a specific file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            List of date strings
        """
        return self.cache.get_file_dates(file_path)
    
    def add_file_to_timeline(self, file_path: str, dates: List[str]):
        """
        Add a file to the timeline with its dates.
        
        Args:
            file_path: Path to the file
            dates: List of normalized date strings
        """
        try:
            # Get file ID
            file_info = self.cache.get_file_by_path(file_path)
            if not file_info:
                logger.warning(f"File not in cache: {file_path}")
                return
            
            file_id = file_info['id']
            
            # Store dates
            date_info_list = [
                {'date_str': date, 'date_normalized': date, 'date_type': 'date'}
                for date in dates
            ]
            self.cache.store_dates(file_id, date_info_list)
            
            # Rebuild timeline
            self.build_timeline()
            
        except Exception as e:
            logger.error(f"Failed to add file to timeline: {e}")
    
    def generate_timeline_markdown(self, file_path: str) -> str:
        """
        Generate timeline section for a file's markdown.
        
        Args:
            file_path: Path to the file
        
        Returns:
            Markdown string with timeline entries
        """
        dates = self.get_file_timeline_entries(file_path)
        
        if not dates:
            return ""
        
        lines = ["## Timeline"]
        for date in dates:
            # Get filename without extension
            filename = Path(file_path).stem
            lines.append(f"- {date} → {filename}")
        
        return "\n".join(lines)
    
    def get_timeline_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics about the timeline.
        
        Returns:
            Dictionary with timeline statistics
        """
        timeline = self.load_timeline()
        
        if not timeline:
            return {
                'total_dates': 0,
                'total_files': 0,
                'date_range': None,
                'most_active_dates': []
            }
        
        # Count total files
        all_files = set()
        for date, files in timeline.items():
            all_files.update(files)
        
        # Get date range
        dates = list(timeline.keys())
        date_range = f"{dates[-1]} to {dates[0]}" if dates else None
        
        # Get most active dates
        sorted_by_count = sorted(
            timeline.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        most_active = sorted_by_count[:5]
        
        return {
            'total_dates': len(timeline),
            'total_files': len(all_files),
            'date_range': date_range,
            'most_active_dates': [
                {'date': date, 'file_count': len(files)}
                for date, files in most_active
            ]
        }
