"""
Metadata Extractor for RBC-TESTER Knowledge System.
Extracts dates, times, people, tags, and other metadata from text content.
Optimized for low-memory systems.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

try:
    from dateutil import parser as date_parser
    from dateutil.relativedelta import relativedelta
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False
    logger.warning("python-dateutil not available, date parsing will be limited")

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    logger.warning("rapidfuzz not available, fuzzy matching will be limited")


class MetadataExtractor:
    """
    Extract metadata from text including dates, people, tags, and other entities.
    Optimized for personal knowledge management and timeline generation.
    """
    
    def __init__(self):
        # Common person names to look for (can be expanded)
        self.known_people = set()
        self._load_known_people()
        
        # Date patterns
        self.date_patterns = [
            # Month Year (e.g., "March 2024")
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b',
            
            # DD Month YYYY (e.g., "22 Apr 2026")
            r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b',
            
            # Month DD, YYYY (e.g., "April 22, 2026")
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b',
            
            # YYYY-MM-DD (ISO format)
            r'\b\d{4}-\d{2}-\d{2}\b',
            
            # DD/MM/YYYY or MM/DD/YYYY
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b',
            
            # Relative dates
            r'\b(?:yesterday|today|tomorrow|last week|last month|last year|this week|this month|this year)\b',
            
            # Age patterns (e.g., "age 18")
            r'\bage\s+\d+\b',
            
            # Time patterns
            r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b',
        ]
        
        # Person name patterns
        self.name_patterns = [
            # Capitalized words that look like names
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # First Last
            r'\b[A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+\b',  # First M. Last
        ]
        
        # Tag patterns (hashtags, keywords)
        self.tag_patterns = [
            r'#\w+',  # Hashtags
            r'\b(?:important|urgent|todo|done|idea|question|note|reference)\b',  # Common tags
        ]
    
    def _load_known_people(self):
        """Load known people names from cache or config."""
        # This can be expanded to load from a file
        pass
    
    def extract_dates(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract dates and times from text.
        
        Args:
            text: Text content to analyze
        
        Returns:
            List of date dictionaries with 'date_str', 'date_normalized', 'date_type'
        """
        dates = []
        current_date = datetime.now()
        
        for pattern in self.date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                date_str = match.group()
                
                try:
                    normalized_date = self._normalize_date(date_str, current_date)
                    if normalized_date:
                        dates.append({
                            'date_str': date_str,
                            'date_normalized': normalized_date,
                            'date_type': self._classify_date_type(date_str)
                        })
                except Exception as e:
                    logger.debug(f"Failed to parse date '{date_str}': {e}")
        
        return dates
    
    def _normalize_date(self, date_str: str, reference_date: datetime) -> Optional[str]:
        """
        Normalize date string to ISO format (YYYY-MM-DD).
        
        Args:
            date_str: Date string to normalize
            reference_date: Reference date for relative dates
        
        Returns:
            Normalized date string or None if parsing fails
        """
        if not DATEUTIL_AVAILABLE:
            return None
        
        try:
            # Handle relative dates
            date_str_lower = date_str.lower()
            
            if 'yesterday' in date_str_lower:
                normalized = reference_date - timedelta(days=1)
                return normalized.strftime('%Y-%m-%d')
            elif 'today' in date_str_lower:
                return reference_date.strftime('%Y-%m-%d')
            elif 'tomorrow' in date_str_lower:
                normalized = reference_date + timedelta(days=1)
                return normalized.strftime('%Y-%m-%d')
            elif 'last week' in date_str_lower:
                normalized = reference_date - timedelta(weeks=1)
                return normalized.strftime('%Y-%m')
            elif 'last month' in date_str_lower:
                normalized = reference_date - relativedelta(months=1)
                return normalized.strftime('%Y-%m')
            elif 'last year' in date_str_lower:
                normalized = reference_date - relativedelta(years=1)
                return normalized.strftime('%Y')
            elif 'this week' in date_str_lower:
                return reference_date.strftime('%Y-%W')
            elif 'this month' in date_str_lower:
                return reference_date.strftime('%Y-%m')
            elif 'this year' in date_str_lower:
                return reference_date.strftime('%Y')
            elif 'age' in date_str_lower:
                # Handle age patterns (e.g., "age 18")
                age_match = re.search(r'age\s+(\d+)', date_str_lower)
                if age_match:
                    age = int(age_match.group(1))
                    birth_year = reference_date.year - age
                    return f"{birth_year}"
            
            # Parse with dateutil
            parsed_date = date_parser.parse(date_str, fuzzy=True)
            
            # Return in appropriate format based on precision
            if parsed_date.hour == 0 and parsed_date.minute == 0 and parsed_date.second == 0:
                # Date only
                return parsed_date.strftime('%Y-%m-%d')
            else:
                # Date with time
                return parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                
        except Exception as e:
            logger.debug(f"Date normalization failed for '{date_str}': {e}")
            return None
    
    def _classify_date_type(self, date_str: str) -> str:
        """
        Classify the type of date.
        
        Args:
            date_str: Date string to classify
        
        Returns:
            Date type string
        """
        date_str_lower = date_str.lower()
        
        if 'age' in date_str_lower:
            return 'age'
        elif 'yesterday' in date_str_lower or 'today' in date_str_lower or 'tomorrow' in date_str_lower:
            return 'relative'
        elif ':' in date_str:
            return 'datetime'
        elif len(date_str.split()) == 2 and re.match(r'^\d{4}$', date_str.split()[-1]):
            return 'month_year'
        else:
            return 'date'
    
    def extract_people(self, text: str, known_people: Optional[List[str]] = None) -> List[str]:
        """
        Extract person names from text.
        
        Args:
            text: Text content to analyze
            known_people: List of known person names to prioritize
        
        Returns:
            List of person names
        """
        people = set()
        
        # Extract using patterns
        for pattern in self.name_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                name = match.group()
                # Filter out common false positives
                if not self._is_false_positive_name(name):
                    people.add(name)
        
        # If known people provided, do fuzzy matching
        if known_people and RAPIDFUZZ_AVAILABLE:
            words = text.split()
            for known_person in known_people:
                # Find best matches
                matches = process.extract(
                    known_person,
                    words,
                    scorer=fuzz.token_sort_ratio,
                    limit=3
                )
                for match, score in matches:
                    if score >= 80:  # 80% similarity threshold
                        people.add(known_person)
        
        return sorted(list(people))
    
    def _is_false_positive_name(self, name: str) -> bool:
        """
        Check if a potential name is a false positive.
        
        Args:
            name: Potential name to check
        
        Returns:
            True if likely a false positive
        """
        false_positives = {
            'The', 'This', 'That', 'These', 'Those',
            'However', 'Therefore', 'Moreover', 'Furthermore',
            'First', 'Second', 'Third', 'Finally',
            'Introduction', 'Conclusion', 'Summary',
            'Chapter', 'Section', 'Appendix',
            'Trust Issues', 'After Breakup', 'Before', 'After',
            'During', 'Since', 'While', 'Through',
            'Issues', 'Problems', 'Concerns', 'Thoughts',
        }
        
        # Check if name is in false positives
        if name in false_positives:
            return True
        
        # Check if name contains common non-name words
        non_name_words = {'issues', 'breakup', 'trust', 'after', 'before', 'during'}
        if any(word in name.lower().split() for word in non_name_words):
            return True
        
        # Check if name is too short
        if len(name.split()) < 2 and len(name) < 5:
            return True
        
        return False
    
    def extract_tags(self, text: str) -> List[str]:
        """
        Extract tags from text.
        
        Args:
            text: Text content to analyze
        
        Returns:
            List of tags
        """
        tags = set()
        
        # Extract hashtags
        hashtag_matches = re.findall(r'#(\w+)', text)
        tags.update([tag.lower() for tag in hashtag_matches])
        
        # Extract common keywords as tags
        for pattern in self.tag_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                tag = match.group().lower().lstrip('#')
                tags.add(tag)
        
        return sorted(list(tags))
    
    def extract_title(self, text: str, file_path: str) -> str:
        """
        Extract or generate a title for the content.
        
        Args:
            text: Text content
            file_path: Path to the file
        
        Returns:
            Title string
        """
        # Try to extract from first line or heading
        lines = text.split('\n')
        
        # Look for first non-empty line
        for line in lines:
            stripped = line.strip()
            if stripped:
                # If it looks like a heading (starts with #), extract it
                if stripped.startswith('#'):
                    return stripped.lstrip('#').strip()
                # Otherwise use first line as title if it's short enough
                if len(stripped) < 100:
                    return stripped
                break
        
        # Fall back to filename
        return Path(file_path).stem
    
    def extract_all_metadata(self, text: str, file_path: str, known_people: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Extract all metadata from text.
        
        Args:
            text: Text content to analyze
            file_path: Path to the file
            known_people: Optional list of known people names
        
        Returns:
            Dictionary with all extracted metadata
        """
        return {
            'title': self.extract_title(text, file_path),
            'dates': self.extract_dates(text),
            'people': self.extract_people(text, known_people),
            'tags': self.extract_tags(text),
        }
