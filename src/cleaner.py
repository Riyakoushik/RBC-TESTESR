"""
Text cleaning and post-processing for OCR and document extraction output.
Removes duplicates, headers, footers, page numbers, and normalizes text.
"""

import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from loguru import logger

from .config import get_config


@dataclass
class CleanResult:
    """Result of text cleaning operation."""
    text: str
    original_lines: int
    cleaned_lines: int
    duplicates_removed: int
    junk_removed: int


class TextCleaner:
    """
    Cleans and normalizes extracted text.
    Removes OCR artifacts, duplicates, and formatting noise.
    """
    
    def __init__(self):
        self.config = get_config()
        self.patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for text cleaning."""
        patterns = []
        for pattern_str in self.config.cleaning.remove_patterns:
            try:
                patterns.append(re.compile(pattern_str, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern_str}': {e}")
        return patterns
    
    def clean(self, text: str) -> CleanResult:
        """
        Main cleaning method - applies all cleaning steps.
        
        Args:
            text: Raw extracted text
        
        Returns:
            CleanResult with cleaned text and statistics
        """
        original_lines = len(text.split('\n'))
        
        # Apply cleaning steps in order
        text = self._normalize_line_endings(text)
        text = self._remove_junk_lines(text)
        text = self._remove_duplicate_lines(text)
        text = self._normalize_whitespace(text)
        text = self._fix_common_ocr_errors(text)
        text = self._remove_empty_lines(text)
        
        cleaned_lines = len(text.split('\n'))
        
        return CleanResult(
            text=text,
            original_lines=original_lines,
            cleaned_lines=cleaned_lines,
            duplicates_removed=original_lines - cleaned_lines,
            junk_removed=0  # Calculated during processing
        )
    
    def _normalize_line_endings(self, text: str) -> str:
        """Normalize all line endings to Unix style."""
        return text.replace('\r\n', '\n').replace('\r', '\n')
    
    def _remove_junk_lines(self, text: str) -> str:
        """
        Remove lines matching junk patterns (headers, footers, page numbers).
        """
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Skip if too short
            if len(stripped) < self.config.cleaning.min_line_length:
                continue
            
            # Check against patterns
            is_junk = False
            for pattern in self.patterns:
                if pattern.search(stripped):
                    is_junk = True
                    break
            
            if not is_junk:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _remove_duplicate_lines(self, text: str) -> str:
        """
        Remove duplicate lines within a sliding window.
        Handles repeated headers/footers across pages.
        """
        lines = text.split('\n')
        window_size = self.config.cleaning.duplicate_window
        cleaned = []
        
        # Track seen lines in window
        window: Set[str] = set()
        
        for line in lines:
            normalized = self._normalize_for_comparison(line)
            
            if normalized and normalized in window:
                # Duplicate found, skip it
                continue
            
            cleaned.append(line)
            
            # Add to window
            if normalized:
                window.add(normalized)
                
                # Maintain window size
                if len(window) > window_size:
                    # Remove oldest (approximation using list)
                    window_list = list(window)
                    window = set(window_list[-window_size:])
        
        return '\n'.join(cleaned)
    
    def _normalize_for_comparison(self, line: str) -> str:
        """
        Normalize line for duplicate comparison.
        Ignores case, whitespace variations, and minor OCR differences.
        """
        # Lowercase and strip
        normalized = line.strip().lower()
        
        # Collapse whitespace
        normalized = ' '.join(normalized.split())
        
        # Remove common OCR artifacts for comparison
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        normalized = normalized.replace('0', 'o')  # Common confusion
        normalized = normalized.replace('1', 'l')  # Common confusion
        
        return normalized
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace while preserving paragraph structure."""
        if not self.config.cleaning.normalize_whitespace:
            return text
        
        lines = text.split('\n')
        normalized = []
        
        for line in lines:
            # Trim trailing whitespace
            line = line.rstrip()
            # Normalize internal spaces (but preserve indentation)
            stripped = line.lstrip()
            indent = line[:len(line) - len(stripped)]
            normalized_line = indent + ' '.join(stripped.split())
            normalized.append(normalized_line)
        
        return '\n'.join(normalized)
    
    def _fix_common_ocr_errors(self, text: str) -> str:
        """Fix common OCR recognition errors."""
        if not self.config.cleaning.fix_ocr_errors:
            return text
        
        fixes = [
            (r'([a-zA-Z])\d([a-zA-Z])', r'\1l\2'),  # 1->l in words
            (r'0([a-zA-Z]{2,})', r'o\1'),  # 0->o at word start
            (r'([a-zA-Z]{2,})0', r'\1o'),  # 0->o at word end
            (r'rn', 'm'),  # rn->m (common confusion)
            (r'cl', 'd'),  # cl->d (common confusion)
        ]
        
        for pattern, replacement in fixes:
            text = re.sub(pattern, replacement, text)
        
        return text
    
    def _remove_empty_lines(self, text: str) -> str:
        """Remove excessive empty lines but keep paragraph breaks."""
        lines = text.split('\n')
        cleaned = []
        empty_count = 0
        
        for line in lines:
            if line.strip() == '':
                empty_count += 1
                # Keep at most 2 consecutive empty lines
                if empty_count <= 2:
                    cleaned.append(line)
            else:
                empty_count = 0
                cleaned.append(line)
        
        return '\n'.join(cleaned)


class TableExtractor:
    """
    Extracts and formats tables from document content.
    Converts tables to Markdown format.
    """
    
    def __init__(self):
        self.config = get_config()
    
    def extract_markdown_table(self, table_data: List[List[str]]) -> Optional[str]:
        """
        Convert table data to Markdown table format.
        
        Args:
            table_data: 2D list of table cell contents
        
        Returns:
            Markdown table string or None if invalid
        """
        if not table_data:
            return None
        
        # Check minimum dimensions
        rows = len(table_data)
        if rows < self.config.tables.min_rows:
            return None
        
        cols = len(table_data[0]) if table_data else 0
        if cols < self.config.tables.min_columns:
            return None
        
        # Normalize all rows to same column count
        normalized = []
        for row in table_data:
            # Pad or truncate to match first row
            if len(row) < cols:
                row = row + [''] * (cols - len(row))
            elif len(row) > cols:
                row = row[:cols]
            normalized.append(row)
        
        # Build markdown table
        lines = []
        
        # Header row
        header = normalized[0]
        lines.append('| ' + ' | '.join(str(cell).strip() for cell in header) + ' |')
        
        # Separator
        lines.append('|' + '|'.join(['---'] * cols) + '|')
        
        # Data rows
        for row in normalized[1:]:
            # Clean cell content
            cleaned_cells = []
            for cell in row:
                # Escape pipe characters
                cell_str = str(cell).replace('|', '\\|').strip()
                # Normalize whitespace
                cell_str = ' '.join(cell_str.split())
                cleaned_cells.append(cell_str)
            
            lines.append('| ' + ' | '.join(cleaned_cells) + ' |')
        
        return '\n'.join(lines)
    
    def detect_and_convert_tables(self, text: str, table_data: Optional[List] = None) -> str:
        """
        Detect table-like structures in text and convert to markdown.
        
        Args:
            text: Input text potentially containing tables
            table_data: Optional structured table data from document parser
        
        Returns:
            Text with tables converted to markdown format
        """
        # If structured table data provided, use it
        if table_data:
            markdown_tables = []
            for table in table_data:
                md_table = self.extract_markdown_table(table)
                if md_table:
                    markdown_tables.append(md_table)
            
            # Insert tables into text at appropriate locations
            # This is simplified - real implementation would need
            # better table positioning logic
            if markdown_tables:
                return '\n\n'.join(markdown_tables) + '\n\n' + text
        
        # Try to detect ASCII tables in text
        # Look for patterns like:
        # col1 | col2 | col3
        # ---- | ---- | ----
        lines = text.split('\n')
        result_lines = []
        in_table = False
        table_buffer = []
        
        table_pattern = re.compile(r'^(.*\|.*)+$')
        separator_pattern = re.compile(r'^[\|\-\s]+$')
        
        for line in lines:
            if table_pattern.match(line) and '|' in line:
                if not in_table:
                    in_table = True
                    table_buffer = []
                table_buffer.append(line)
            elif in_table and separator_pattern.match(line.replace('-', '').replace('|', '').strip()):
                table_buffer.append(line)
            elif in_table:
                # End of table
                if len(table_buffer) >= 2:
                    # Convert to proper markdown
                    table_text = '\n'.join(table_buffer)
                    result_lines.append(table_text)
                    result_lines.append('')  # Empty line after table
                else:
                    result_lines.extend(table_buffer)
                
                in_table = False
                table_buffer = []
                result_lines.append(line)
            else:
                result_lines.append(line)
        
        # Handle table at end of text
        if in_table and len(table_buffer) >= 2:
            result_lines.append('\n'.join(table_buffer))
        elif in_table:
            result_lines.extend(table_buffer)
        
        return '\n'.join(result_lines)


class ContentOptimizer:
    """
    Optimizes content structure for emotional-AI dataset.
    Ensures consistent formatting and quality.
    """
    
    def __init__(self):
        self.cleaner = TextCleaner()
        self.table_extractor = TableExtractor()
    
    def process(self, text: str, tables: Optional[List] = None) -> str:
        """
        Full processing pipeline for extracted content.
        
        Args:
            text: Raw extracted text
            tables: Optional structured table data
        
        Returns:
            Optimized, cleaned text ready for dataset
        """
        # Clean text
        result = self.cleaner.clean(text)
        cleaned_text = result.text
        
        # Process tables if present
        if tables:
            cleaned_text = self.table_extractor.detect_and_convert_tables(
                cleaned_text, tables
            )
        
        # Final formatting
        cleaned_text = self._finalize_format(cleaned_text)
        
        return cleaned_text
    
    def _finalize_format(self, text: str) -> str:
        """Apply final formatting touches."""
        # Ensure text ends with newline
        if not text.endswith('\n'):
            text += '\n'
        
        # Add metadata header if configured
        # This could be extended for GraphRAG integration
        
        return text


def clean_text(text: str) -> str:
    """
    Convenience function for one-off text cleaning.
    
    Args:
        text: Raw text to clean
    
    Returns:
        Cleaned text
    """
    cleaner = TextCleaner()
    result = cleaner.clean(text)
    return result.text


def clean_file(input_path: str, output_path: str) -> bool:
    """
    Clean text file and save result.
    
    Args:
        input_path: Path to input text file
        output_path: Path to save cleaned output
    
    Returns:
        True if successful
    """
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        cleaned = clean_text(text)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        
        return True
    except Exception as e:
        logger.error(f"Failed to clean file {input_path}: {e}")
        return False
