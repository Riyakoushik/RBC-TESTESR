"""
Document conversion pipeline using Unstructured.io for all format support.
Integrates OCR for scanned content and provides unified output.
"""

import os
import re
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from loguru import logger

# Document processing libraries - unstructured.io
try:
    from unstructured.partition.auto import partition
    from unstructured.partition.pdf import partition_pdf
    from unstructured.partition.image import partition_image
    from unstructured.partition.docx import partition_docx
    from unstructured.partition.pptx import partition_pptx
    from unstructured.partition.html import partition_html
    from unstructured.partition.text import partition_text
    from unstructured.partition.epub import partition_epub
    UNSTRUCTURED_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Unstructured.io not available: {e}. Some features will be limited.")
    UNSTRUCTURED_AVAILABLE = False

from .config import get_config, get_project_root
from .utils import (
    detect_file_type, is_scanned_pdf, get_output_path,
    ensure_dir, ConversionState, write_failed_files, write_summary
)
from .ocr import OCRProcessor
from .cleaner import ContentOptimizer
from .monitor import ProgressTracker

# Knowledge system imports
try:
    from .cache_manager import CacheManager
    from .metadata_extractor import MetadataExtractor
    from .timeline_builder import TimelineBuilder
    from .embedding_engine import EmbeddingEngine
    from .backlink_engine import BacklinkEngine
    from .graph_builder import GraphBuilder
    KNOWLEDGE_SYSTEM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Knowledge system not available: {e}")
    KNOWLEDGE_SYSTEM_AVAILABLE = False


def df_to_markdown(df) -> str:
    """Convert pandas DataFrame to markdown table."""
    lines = []
    
    # Header
    header = " | ".join(str(col) for col in df.columns)
    lines.append(f"| {header} |")
    lines.append("|" + "|".join(["---"] * len(df.columns)) + "|")
    
    # Data rows
    for _, row in df.iterrows():
        row_str = " | ".join(str(val) if pd.notna(val) else "" for val in row)
        lines.append(f"| {row_str} |")
    
    return "\n".join(lines)


class DocumentConverterPipeline:
    """
    Main document conversion pipeline.
    Handles all file types and routes to appropriate converter.
    """
    
    def __init__(self):
        self.config = get_config()
        self.ocr_processor = OCRProcessor()
        self.content_optimizer = ContentOptimizer()
        self.state = ConversionState()
        
        # Initialize knowledge system components
        if KNOWLEDGE_SYSTEM_AVAILABLE and self.config.knowledge.enabled:
            self.cache_manager = CacheManager()
            self.metadata_extractor = MetadataExtractor()
            self.timeline_builder = TimelineBuilder(self.cache_manager)
            self.embedding_engine = EmbeddingEngine(self.cache_manager)
            self.backlink_engine = BacklinkEngine(self.cache_manager, self.embedding_engine)
            self.graph_builder = GraphBuilder(self.cache_manager)
            
            # Initialize embedding engine
            self.embedding_engine.initialize()
            
            logger.info("Knowledge system initialized")
        else:
            self.cache_manager = None
            self.metadata_extractor = None
            self.timeline_builder = None
            self.embedding_engine = None
            self.backlink_engine = None
            self.graph_builder = None
    
    def _convert_with_unstructured(self, file_path: str, output_path: str) -> bool:
        """
        Convert file using Unstructured.io (supports all formats).
        """
        if not UNSTRUCTURED_AVAILABLE:
            logger.warning("Unstructured.io not available")
            return False
        
        try:
            ext = Path(file_path).suffix.lower()
            config = get_config()
            
            # Use appropriate partition function based on file type
            if ext == '.pdf':
                elements = partition_pdf(file_path, infer_table_structure=True)
            elif ext in ['.docx', '.doc', '.docm']:
                elements = partition_docx(file_path, infer_table_structure=True)
            elif ext in ['.pptx', '.ppt', '.pptm']:
                elements = partition_pptx(file_path, infer_table_structure=True)
            elif ext in ['.html', '.htm', '.xhtml']:
                elements = partition_html(file_path)
            elif ext in ['.txt', '.md', '.markdown', '.rst', '.adoc']:
                elements = partition_text(file_path)
            elif ext == '.epub':
                elements = partition_epub(file_path)
            elif ext in ['.xlsx', '.xls', '.xlsm']:
                elements = partition(file_path, infer_table_structure=True)
            elif ext in config.supported_formats.images:
                # Images need OCR
                elements = partition_image(file_path)
            elif ext in config.supported_formats.code:
                # Code files - treat as text
                elements = partition_text(file_path)
            elif ext in config.supported_formats.data:
                # Data files - use auto partition
                elements = partition(file_path, infer_table_structure=True)
            else:
                # Use auto partition for other formats
                elements = partition(file_path, infer_table_structure=True)
            
            # Extract text from elements
            text_parts = []
            for element in elements:
                text = element.text.strip()
                if text:
                    text_parts.append(text)
            
            text = "\n\n".join(text_parts)
            optimized = self.content_optimizer.process(text)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            logger.info(f"Successfully converted with Unstructured.io: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Unstructured.io conversion failed: {e}")
            return False
    
    def convert_file(self, file_path: str) -> Tuple[str, bool]:
        """
        Convert a single file to markdown/text with knowledge system integration.
        
        Args:
            file_path: Path to input file
        
        Returns:
            Tuple of (output_path, success)
        """
        file_type = detect_file_type(file_path)
        
        # Generate output path
        output_path = get_output_path(
            file_path, 
            f".{self.config.processing.output_format}"
        )
        
        # Ensure output directory exists
        ensure_dir(os.path.dirname(output_path))
        
        try:
            if file_type == "document":
                success = self._convert_document(file_path, output_path)
            elif file_type == "image":
                success = self._convert_image(file_path, output_path)
            elif file_type == "text":
                success = self._convert_text(file_path, output_path)
            elif file_type == "code":
                success = self._convert_code(file_path, output_path)
            elif file_type == "archive":
                success = self._convert_archive(file_path, output_path)
            elif file_type == "audio":
                success = self._convert_audio(file_path, output_path)
            elif file_type == "video":
                success = self._convert_video(file_path, output_path)
            elif file_type == "data":
                success = self._convert_data(file_path, output_path)
            elif file_type == "ebook":
                success = self._convert_ebook(file_path, output_path)
            elif file_type == "spreadsheet":
                success = self._convert_spreadsheet(file_path, output_path)
            elif file_type == "presentation":
                success = self._convert_presentation(file_path, output_path)
            else:
                success = self._convert_with_unstructured(file_path, output_path)
            
            # Apply knowledge system processing if enabled
            if success and self.cache_manager:
                self._apply_knowledge_system(file_path, output_path)
            
            # Update state
            if success:
                self.state.mark_completed(file_path)
            else:
                self.state.mark_failed(file_path)
            
            return output_path, success
                
        except Exception as e:
            logger.error(f"Conversion failed for {file_path}: {e}")
            self.state.mark_failed(file_path)
            return output_path, False
    
    def _apply_knowledge_system(self, file_path: str, output_path: str):
        """
        Apply knowledge system processing to converted file.
        Extracts metadata, generates embeddings, creates backlinks, and enriches markdown.
        
        Args:
            file_path: Original input file path
            output_path: Converted output file path
        """
        try:
            # Read converted content
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract metadata
            metadata = self.metadata_extractor.extract_all_metadata(content, file_path)
            
            # Register file in cache
            file_id = self.cache_manager.register_file(file_path, metadata['title'], content)
            
            # Store metadata in cache
            date_info_list = [
                {'date_str': d['date_str'], 'date_normalized': d['date_normalized'], 'date_type': d['date_type']}
                for d in metadata['dates']
            ]
            self.cache_manager.store_dates(file_id, date_info_list)
            self.cache_manager.store_people(file_id, metadata['people'])
            self.cache_manager.store_tags(file_id, metadata['tags'])
            
            # Generate embedding
            self.embedding_engine.add_embedding(file_id, content)
            
            # Generate backlinks
            self.backlink_engine.generate_backlinks_for_file(file_path, content)
            
            # Rebuild timeline
            self.timeline_builder.build_timeline()
            
            # Enrich markdown with frontmatter and knowledge sections
            enriched_content = self._enrich_markdown(
                content,
                metadata,
                file_path
            )
            
            # Write enriched content back
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(enriched_content)
            
            logger.info(f"Knowledge system processing complete for {file_path}")
            
        except Exception as e:
            logger.error(f"Knowledge system processing failed for {file_path}: {e}")
    
    def _enrich_markdown(self, content: str, metadata: Dict[str, Any], file_path: str) -> str:
        """
        Enrich markdown with frontmatter and knowledge sections.
        
        Args:
            content: Original markdown content
            metadata: Extracted metadata
            file_path: File path
        
        Returns:
            Enriched markdown content
        """
        from datetime import datetime
        
        # Build frontmatter
        frontmatter_lines = ["---"]
        frontmatter_lines.append(f"title: {metadata['title']}")
        frontmatter_lines.append(f"created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if metadata['tags']:
            frontmatter_lines.append(f"tags: {metadata['tags']}")
        
        if metadata['people']:
            frontmatter_lines.append(f"people: {metadata['people']}")
        
        frontmatter_lines.append("---")
        frontmatter_lines.append("")
        
        # Build knowledge sections
        knowledge_sections = []
        
        # Timeline section
        timeline_md = self.timeline_builder.generate_timeline_markdown(file_path)
        if timeline_md:
            knowledge_sections.append(timeline_md)
        
        # Related notes section
        backlinks_md = self.backlink_engine.generate_backlinks_markdown(file_path)
        if backlinks_md:
            knowledge_sections.append(backlinks_md)
        
        # Mentioned people section
        if metadata['people']:
            people_lines = ["## Mentioned People"]
            for person in metadata['people']:
                people_lines.append(f"- {person}")
            knowledge_sections.append("\n".join(people_lines))
        
        # Combine all sections
        enriched = "\n".join(frontmatter_lines) + content
        
        if knowledge_sections:
            enriched += "\n\n" + "\n\n".join(knowledge_sections)
        
        return enriched
    
    def _convert_document(self, file_path: str, output_path: str) -> bool:
        """
        Convert document files (PDF, DOCX, PPTX, EPUB).
        Uses Unstructured.io for all formats with OCR support.
        """
        ext = Path(file_path).suffix.lower()
        
        # Use Unstructured.io (supports all formats including OCR)
        if UNSTRUCTURED_AVAILABLE:
            logger.info(f"Converting with Unstructured.io: {file_path}")
            success = self._convert_with_unstructured(file_path, output_path)
            if success:
                return True
            else:
                logger.warning("Unstructured.io failed, trying fallback")
        
        # Fallback to simpler converters
        logger.info(f"Using fallback converter for {file_path}")
        return self._convert_document_fallback(file_path, output_path, ext)
    
    def _convert_image(self, file_path: str, output_path: str) -> bool:
        """Convert image files with OCR."""
        # Use Unstructured.io with OCR
        if UNSTRUCTURED_AVAILABLE:
            return self._convert_with_unstructured(file_path, output_path)
        
        # Fallback to OCR processor
        logger.warning(f"Converting image with OCR: {file_path}")
        try:
            text = self.ocr_processor.process_file(file_path)
            if text:
                optimized = self.content_optimizer.process(text)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(optimized)
                return True
        except Exception as e:
            logger.error(f"Image conversion failed: {e}")
        return False
    
    def _convert_text(self, file_path: str, output_path: str) -> bool:
        """Convert text files directly."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            optimized = self.content_optimizer.process(text)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            return True
        except Exception as e:
            logger.error(f"Text conversion failed: {e}")
            return False
    
    def _convert_code(self, file_path: str, output_path: str) -> bool:
        """Convert code files to markdown with syntax highlighting."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            
            ext = Path(file_path).suffix.lower().lstrip('.')
            
            # Create markdown with code block
            markdown = f"```{ext}\n{code}\n```"
            
            optimized = self.content_optimizer.process(markdown)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            return True
            
        except Exception as e:
            logger.error(f"Code conversion failed: {e}")
            return False
    
    def _convert_data(self, file_path: str, output_path: str) -> bool:
        """Convert data files (JSON, YAML, etc.)."""
        # Use Unstructured.io auto partition
        if UNSTRUCTURED_AVAILABLE:
            return self._convert_with_unstructured(file_path, output_path)
        
        # Fallback to text conversion
        return self._convert_text(file_path, output_path)
    
    def _convert_ebook(self, file_path: str, output_path: str) -> bool:
        """Convert ebook files (EPUB, MOBI)."""
        # Use Unstructured.io
        if UNSTRUCTURED_AVAILABLE:
            return self._convert_with_unstructured(file_path, output_path)
        
        # Fallback to document converter
        return self._convert_document_fallback(file_path, output_path, Path(file_path).suffix.lower())
    
    def _convert_spreadsheet(self, file_path: str, output_path: str) -> bool:
        """Convert spreadsheet files (Excel, CSV)."""
        try:
            ext = Path(file_path).suffix.lower()
            
            if ext in ['.xlsx', '.xls', '.xlsm']:
                df = pd.read_excel(file_path, sheet_name=None)
            elif ext in ['.csv']:
                df = pd.read_csv(file_path)
            elif ext in ['.tsv']:
                df = pd.read_csv(file_path, sep='\t')
            else:
                return False
            
            # If multiple sheets, convert each
            if isinstance(df, dict):
                markdown_parts = []
                for sheet_name, sheet_df in df.items():
                    markdown_parts.append(f"## Sheet: {sheet_name}\n")
                    markdown_parts.append(df_to_markdown(sheet_df))
                text = "\n\n".join(markdown_parts)
            else:
                text = df_to_markdown(df)
            
            optimized = self.content_optimizer.process(text)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            return True
            
        except Exception as e:
            logger.error(f"Spreadsheet conversion failed: {e}")
            return False
    
    def _convert_presentation(self, file_path: str, output_path: str) -> bool:
        """Convert presentation files (PPTX, PPT)."""
        # Use Unstructured.io
        if UNSTRUCTURED_AVAILABLE:
            return self._convert_with_unstructured(file_path, output_path)
        
        # Fallback to document converter
        return self._convert_document_fallback(file_path, output_path, Path(file_path).suffix.lower())
    
    def _convert_archive(self, file_path: str, output_path: str) -> bool:
        """
        Extract and convert archive contents.
        """
        try:
            import zipfile
            import tarfile
            import shutil
            from pathlib import Path as P
            
            # Create temp extraction directory
            temp_dir = output_path + "_extracted"
            P(temp_dir).mkdir(parents=True, exist_ok=True)
            
            ext = Path(file_path).suffix.lower()
            
            if ext == '.zip':
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            elif ext in ['.tar', '.tar.gz', '.tgz']:
                with tarfile.open(file_path, 'r:*') as tar_ref:
                    tar_ref.extractall(temp_dir)
            elif ext == '.7z':
                logger.warning("7z extraction requires py7zr - install with: pip install py7zr")
                return False
            elif ext == '.rar':
                logger.warning("RAR extraction requires rarfile - install with: pip install rarfile")
                return False
            else:
                return False
            
            # Recursively convert extracted files
            extracted_files = list(P(temp_dir).rglob('*'))
            for extracted_file in extracted_files:
                if extracted_file.is_file():
                    self.convert_file(str(extracted_file))
            
            # Clean up temp directory
            shutil.rmtree(temp_dir)
            
            logger.info(f"Extracted and converted archive: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Archive extraction failed: {e}")
            return False
    
    def _convert_audio(self, file_path: str, output_path: str) -> bool:
        """
        Convert audio file (transcription requires whisper).
        """
        logger.warning(f"Audio transcription requires whisper-openai. Install with: pip install whisper-openai")
        logger.warning(f"Skipping audio file: {file_path}")
        return False
    
    def _convert_video(self, file_path: str, output_path: str) -> bool:
        """
        Convert video file (frame extraction requires additional setup).
        """
        logger.warning(f"Video processing requires additional setup. Skipping: {file_path}")
        return False
    
    def _convert_code(self, file_path: str, output_path: str) -> bool:
        """
        Convert code file to markdown with syntax highlighting.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            
            ext = Path(file_path).suffix.lower().lstrip('.')
            
            # Create markdown with code block
            markdown = f"```{ext}\n{code}\n```"
            
            optimized = self.content_optimizer.process(markdown)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            logger.info(f"Converted code file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Code conversion failed: {e}")
            return False
    
    def _convert_document_fallback(self, file_path: str, output_path: str, ext: str) -> bool:
        """
        Fallback document conversion when Unstructured.io is unavailable.
        Uses simpler libraries for common formats.
        """
        config = get_config()
        
        try:
            # Archives
            if ext in config.supported_formats.archives:
                return self._convert_archive(file_path, output_path)
            
            # Audio
            elif ext in config.supported_formats.audio:
                return self._convert_audio(file_path, output_path)
            
            # Video
            elif ext in config.supported_formats.video:
                return self._convert_video(file_path, output_path)
            
            # Code files
            elif ext in config.supported_formats.code:
                return self._convert_code(file_path, output_path)
            
            # Documents
            elif ext in ['.docx', '.doc', '.docm']:
                return self._convert_docx(file_path, output_path)
            elif ext in ['.pptx', '.ppt', '.pptm']:
                return self._convert_pptx(file_path, output_path)
            elif ext in config.supported_formats.ebooks:
                return self._convert_epub(file_path, output_path)
            elif ext == '.pdf':
                return self._convert_pdf_fallback(file_path, output_path)
            elif ext in config.supported_formats.spreadsheets:
                return self._convert_spreadsheet(file_path, output_path)
            elif ext in config.supported_formats.text:
                return self._convert_text_fallback(file_path, output_path)
            else:
                logger.warning(f"Unsupported format for fallback: {ext}")
                return False
        except Exception as e:
            logger.error(f"Fallback conversion failed: {e}")
            return False
    
    def _convert_docx(self, file_path: str, output_path: str) -> bool:
        """Convert DOCX using python-docx."""
        try:
            from docx import Document
            
            doc = Document(file_path)
            text_parts = []
            
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)
            
            # Extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text for cell in row)
                    text_parts.append(row_text)
            
            text = "\n\n".join(text_parts)
            optimized = self.content_optimizer.process(text)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            return True
        except ImportError:
            logger.error("python-docx not installed")
            return False
        except Exception as e:
            logger.error(f"DOCX conversion failed: {e}")
            return False
    
    def _convert_pptx(self, file_path: str, output_path: str) -> bool:
        """Convert PPTX using python-pptx."""
        try:
            from pptx import Presentation
            
            prs = Presentation(file_path)
            text_parts = []
            
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        if shape.text.strip():
                            text_parts.append(shape.text)
            
            text = "\n\n".join(text_parts)
            optimized = self.content_optimizer.process(text)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            return True
        except ImportError:
            logger.error("python-pptx not installed")
            return False
        except Exception as e:
            logger.error(f"PPTX conversion failed: {e}")
            return False
    
    def _convert_epub(self, file_path: str, output_path: str) -> bool:
        """Convert EPUB using ebooklib."""
        try:
            from ebooklib import epub
            from bs4 import BeautifulSoup
            
            book = epub.read_epub(file_path)
            text_parts = []
            
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    text = soup.get_text()
                    if text.strip():
                        text_parts.append(text)
            
            text = "\n\n".join(text_parts)
            optimized = self.content_optimizer.process(text)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            return True
        except ImportError:
            logger.error("ebooklib or beautifulsoup4 not installed")
            return False
        except Exception as e:
            logger.error(f"EPUB conversion failed: {e}")
            return False
    
    def _convert_spreadsheet(self, file_path: str, output_path: str) -> bool:
        """Convert spreadsheet to markdown table."""
        try:
            import pandas as pd
            ext = Path(file_path).suffix.lower()
            
            if ext in ['.xlsx', '.xls', '.xlsm']:
                df = pd.read_excel(file_path, sheet_name=None)
            elif ext in ['.csv']:
                df = pd.read_csv(file_path)
            elif ext in ['.tsv']:
                df = pd.read_csv(file_path, sep='\t')
            else:
                return False
            
            # If multiple sheets, convert each
            if isinstance(df, dict):
                markdown_parts = []
                for sheet_name, sheet_df in df.items():
                    markdown_parts.append(f"## Sheet: {sheet_name}\n")
                    markdown_parts.append(df_to_markdown(sheet_df))
                text = "\n\n".join(markdown_parts)
            else:
                text = df_to_markdown(df)
            
            optimized = self.content_optimizer.process(text)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            return True
            
        except Exception as e:
            logger.error(f"Spreadsheet conversion failed: {e}")
            return False
    
    def _convert_text_fallback(self, file_path: str, output_path: str) -> bool:
        """Convert text/markdown file directly."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            optimized = self.content_optimizer.process(text)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            return True
            
        except Exception as e:
            logger.error(f"Text conversion failed: {e}")
            return False
    
    def _convert_pdf_fallback(self, file_path: str, output_path: str) -> bool:
        """Convert PDF using pymupdf as fallback."""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            text_parts = []
            
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
            
            doc.close()
            
            text = "\n\n".join(text_parts)
            optimized = self.content_optimizer.process(text)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            return True
        except ImportError:
            logger.error("pymupdf not installed")
            return False
        except Exception as e:
            logger.error(f"PDF fallback conversion failed: {e}")
            return False
    
    def _convert_image(self, file_path: str, output_path: str) -> bool:
        """
        Convert image files using OCR.
        """
        text, success = self.ocr_processor.process_file(file_path)
        
        if success and text.strip():
            optimized = self.content_optimizer.process(text)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            return True
        
        return False
    
    def _convert_text(self, file_path: str, output_path: str) -> bool:
        """
        Convert text-based files (TXT, MD, HTML, etc).
        Handles format conversion and cleaning.
        """
        ext = Path(file_path).suffix.lower()
        
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Convert based on type
            if ext in ['.html', '.htm', '.xml']:
                content = self._html_to_markdown(content)
            elif ext == '.md':
                # Already markdown, just clean
                pass
            elif ext in ['.json', '.csv']:
                content = self._structured_to_markdown(content, ext)
            
            # Clean and optimize
            optimized = self.content_optimizer.process(content)
            
            # Write output
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(optimized)
            
            return True
            
        except Exception as e:
            logger.error(f"Text conversion failed: {e}")
            return False
    
    def _extract_from_docling(self, result: ConversionResult) -> str:
        """
        Extract text content from Docling conversion result.
        """
        text_parts = []
        
        try:
            # Try to get markdown output if available
            if hasattr(result, 'document') and result.document:
                doc = result.document
                
                # Export to markdown
                if hasattr(doc, 'export_to_markdown'):
                    return doc.export_to_markdown()
                
                # Manual extraction
                for item in doc.texts:
                    if isinstance(item, TextItem):
                        text_parts.append(item.text)
                
                # Add tables
                for table in doc.tables:
                    if isinstance(table, TableItem):
                        table_md = table.export_to_markdown()
                        if table_md:
                            text_parts.append(f"\n{table_md}\n")
                
                return '\n\n'.join(text_parts)
            
            # Fallback to any available text
            if hasattr(result, 'text') and result.text:
                return result.text
                
        except Exception as e:
            logger.warning(f"Error extracting from Docling result: {e}")
        
        return '\n\n'.join(text_parts) if text_parts else ""
    
    def _extract_tables_from_docling(self, result: ConversionResult) -> List[List[List[str]]]:
        """
        Extract table data from Docling result.
        """
        tables = []
        
        try:
            if hasattr(result, 'document') and result.document:
                doc = result.document
                
                for table_item in doc.tables:
                    if isinstance(table_item, TableItem):
                        # Try to get table data
                        if hasattr(table_item, 'data') and table_item.data:
                            table_data = []
                            for row in table_item.data:
                                row_data = [str(cell) if cell else '' for cell in row]
                                table_data.append(row_data)
                            tables.append(table_data)
                        elif hasattr(table_item, 'export_to_dataframe'):
                            import pandas as pd
                            df = table_item.export_to_dataframe()
                            tables.append(df.values.tolist())
        
        except Exception as e:
            logger.debug(f"Table extraction issue: {e}")
        
        return tables
    
    def _html_to_markdown(self, html_content: str) -> str:
        """
        Convert HTML content to Markdown.
        """
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            h.ignore_tables = False
            h.body_width = 0  # Don't wrap lines
            return h.handle(html_content)
        except ImportError:
            # Fallback to basic cleaning
            from html.parser import HTMLParser
            
            class MLStripper(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.reset()
                    self.fed = []
                
                def handle_data(self, d):
                    self.fed.append(d)
                
                def get_data(self):
                    return ''.join(self.fed)
            
            s = MLStripper()
            s.feed(html_content)
            return s.get_data()
    
    def _structured_to_markdown(self, content: str, ext: str) -> str:
        """
        Convert structured data (JSON, CSV) to markdown.
        """
        try:
            if ext == '.json':
                import json
                data = json.loads(content)
                
                # If it's a list of objects, make a table
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                    headers = list(data[0].keys())
                    rows = [[str(row.get(h, '')) for h in headers] for row in data]
                    
                    # Build markdown table
                    lines = []
                    lines.append('| ' + ' | '.join(headers) + ' |')
                    lines.append('|' + '|'.join(['---'] * len(headers)) + '|')
                    for row in rows[:100]:  # Limit to 100 rows
                        lines.append('| ' + ' | '.join(row) + ' |')
                    
                    return '\n'.join(lines)
                else:
                    # Pretty print JSON
                    return f"```json\n{json.dumps(data, indent=2)}\n```"
                    
            elif ext == '.csv':
                import csv
                from io import StringIO
                
                reader = csv.reader(StringIO(content))
                rows = list(reader)
                
                if rows:
                    lines = []
                    # Header
                    lines.append('| ' + ' | '.join(rows[0]) + ' |')
                    lines.append('|' + '|'.join(['---'] * len(rows[0])) + '|')
                    # Data rows
                    for row in rows[1:100]:  # Limit rows
                        lines.append('| ' + ' | '.join(row) + ' |')
                    
                    return '\n'.join(lines)
        
        except Exception as e:
            logger.debug(f"Structured conversion failed: {e}")
        
        return content


class BatchProcessor:
    """
    Handles batch processing of files with progress tracking.
    """
    
    def __init__(self):
        self.converter = DocumentConverterPipeline()
        self.config = get_config()
    
    def process_batch(self, files: List[str], tracker: ProgressTracker) -> Tuple[int, int, int]:
        """
        Process a batch of files.
        
        Args:
            files: List of file paths to process
            tracker: Progress tracker for status updates
        
        Returns:
            Tuple of (successful, failed, total_text_bytes)
        """
        successful = 0
        failed = 0
        total_text = 0
        
        batch_size = self.config.processing.batch_size
        
        for i, file_path in enumerate(files):
            tracker.start_file(file_path)
            
            try:
                output_path, success = self.converter.convert_file(file_path)
                
                if success:
                    successful += 1
                    # Get size of output for statistics
                    try:
                        text_size = os.path.getsize(output_path)
                        total_text += text_size
                    except:
                        pass
                else:
                    failed += 1
                
                tracker.complete_file(success, total_text)
                
                # Batch delay for thermal management
                if (i + 1) % batch_size == 0 and i < len(files) - 1:
                    import time
                    time.sleep(self.config.processing.batch_delay)
                    
            except Exception as e:
                logger.error(f"Unexpected error processing {file_path}: {e}")
                tracker.complete_file(False)
                failed += 1
        
        return successful, failed, total_text
    
    def run(self, files: List[str], tracker: ProgressTracker) -> Dict[str, Any]:
        """
        Run full batch processing pipeline.
        
        Args:
            files: List of all files to process
            tracker: Progress tracker
        
        Returns:
            Summary statistics dictionary
        """
        state = ConversionState()
        pending = state.get_pending_files(files)
        
        if not pending:
            logger.info("All files already processed")
            return {
                "total": len(files),
                "successful": len(state.completed),
                "failed": len(state.failed),
                "skipped": len(files) - len(state.completed) - len(state.failed)
            }
        
        logger.info(f"Processing {len(pending)} pending files out of {len(files)} total")
        
        # Process batches
        successful, failed, total_text = self.process_batch(pending, tracker)
        
        # Write summary
        stats = tracker.get_stats()
        write_summary(
            total=len(files),
            successful=stats['successful'],
            failed=stats['failed'],
            total_text=total_text
        )
        
        # Write failed files log
        if state.failed:
            write_failed_files(list(state.failed))
        
        return {
            "total": len(files),
            "successful": stats['successful'],
            "failed": stats['failed'],
            "total_text_bytes": total_text
        }


def convert_single_file(file_path: str) -> Tuple[str, bool]:
    """
    Convert a single file (convenience function).
    
    Args:
        file_path: Path to file to convert
    
    Returns:
        Tuple of (output_path, success)
    """
    pipeline = DocumentConverterPipeline()
    return pipeline.convert_file(file_path)


def convert_directory(input_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert all supported files in directory.
    
    Args:
        input_dir: Input directory (None = use config)
    
    Returns:
        Summary statistics
    """
    from .utils import get_input_files
    from .monitor import ProgressTracker
    
    files = get_input_files()
    
    if not files:
        logger.warning("No files found to process")
        return {"total": 0, "successful": 0, "failed": 0}
    
    tracker = ProgressTracker(len(files))
    processor = BatchProcessor()
    
    return processor.run(files, tracker)
