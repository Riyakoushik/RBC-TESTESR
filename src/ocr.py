"""
OCR processing using EasyOCR (primary), PaddleOCR, and Tesseract (fallback).
Optimized for low-end systems with batch processing support.
EasyOCR works on Python 3.14 and is recommended for Windows.
"""

import os
import re
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path
import numpy as np
from PIL import Image
from loguru import logger

from .config import get_config
from .utils import detect_file_type, is_scanned_pdf, get_project_root


class OCREngine:
    """
    Unified OCR interface supporting EasyOCR, PaddleOCR, and Tesseract.
    Auto-selects engine based on configuration and availability.
    EasyOCR works on Python 3.14 and is recommended for Windows.
    """

    def __init__(self):
        self.config = get_config()
        self.easy_ocr = None
        self.paddle_ocr = None
        self.tesseract_available = False
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize OCR engines based on configuration.

        Returns:
            True if at least one engine is available
        """
        if self._initialized:
            return True

        success = False

        # Try to initialize EasyOCR (primary - works on Python 3.14)
        try:
            import easyocr
            logger.info("Initializing EasyOCR...")
            self.easy_ocr = easyocr.Reader(
                [self.config.ocr.language],
                gpu=self.config.ocr.use_gpu,
                verbose=False
            )
            logger.info("EasyOCR initialized successfully")
            success = True
        except Exception as e:
            logger.warning(f"Failed to initialize EasyOCR: {e}")
            self.easy_ocr = None

        # Try PaddleOCR as secondary (requires Python 3.11-3.12)
        if not success and self.config.ocr.primary_engine == "paddleocr":
            try:
                from paddleocr import PaddleOCR

                use_gpu = self.config.ocr.use_gpu
                logger.info(f"Initializing PaddleOCR (GPU: {use_gpu})...")

                self.paddle_ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang=self.config.ocr.language,
                    use_gpu=use_gpu,
                    show_log=False,
                    enable_mkldnn=True  # Intel CPU optimization
                )
                logger.info("PaddleOCR initialized successfully")
                success = True

            except Exception as e:
                logger.warning(f"Failed to initialize PaddleOCR: {e}")
                self.paddle_ocr = None

        # Check Tesseract availability (fallback)
        if self.config.ocr.fallback_engine == "tesseract" or not success:
            try:
                import pytesseract
                # Test tesseract
                pytesseract.get_tesseract_version()
                self.tesseract_available = True
                logger.info("Tesseract OCR available as fallback")
                success = True
            except Exception as e:
                logger.warning(f"Tesseract not available: {e}")
                self.tesseract_available = False

        self._initialized = True
        return success
    
    def process_image(self, image_path: str) -> Tuple[str, List[Dict]]:
        """
        Process image with OCR and extract text.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (extracted_text, structured_data)
        """
        if not self._initialized:
            self.initialize()

        # Try EasyOCR first (works on Python 3.14)
        if self.easy_ocr:
            try:
                result = self._easy_process(image_path)
                if result[0].strip():  # Check if we got meaningful text
                    return result
                else:
                    logger.debug(f"EasyOCR returned empty text for {image_path}, trying fallback")
            except Exception as e:
                logger.warning(f"EasyOCR failed for {image_path}: {e}")

        # Try PaddleOCR as secondary
        if self.paddle_ocr:
            try:
                result = self._paddle_process(image_path)
                if result[0].strip():  # Check if we got meaningful text
                    return result
                else:
                    logger.debug(f"PaddleOCR returned empty text for {image_path}, trying fallback")
            except Exception as e:
                logger.warning(f"PaddleOCR failed for {image_path}: {e}")

        # Fallback to Tesseract
        if self.tesseract_available:
            try:
                return self._tesseract_process(image_path)
            except Exception as e:
                logger.error(f"Tesseract also failed for {image_path}: {e}")

        return "", []

    def _easy_process(self, image_path: str) -> Tuple[str, List[Dict]]:
        """
        Process image using EasyOCR.
        Returns text and bounding box data.
        """
        result = self.easy_ocr.readtext(image_path, detail=1)

        lines = []
        structured = []

        for (bbox, text, confidence) in result:
            if confidence > 0.5:  # Filter low confidence
                lines.append(text)
                structured.append({
                    'text': text,
                    'confidence': confidence,
                    'bbox': bbox
                })

        return '\n'.join(lines), structured

    def _paddle_process(self, image_path: str) -> Tuple[str, List[Dict]]:
        """
        Process image using PaddleOCR.
        Returns text and bounding box data.
        """
        result = self.paddle_ocr.ocr(image_path, cls=True)
        
        lines = []
        structured = []
        
        if result and result[0]:
            for line in result[0]:
                if line:
                    bbox = line[0]  # Bounding box coordinates
                    text = line[1][0]  # Text content
                    confidence = line[1][1]  # Confidence score
                    
                    if text and confidence > 0.5:  # Filter low confidence
                        lines.append(text)
                        structured.append({
                            'text': text,
                            'confidence': confidence,
                            'bbox': bbox
                        })
        
        return '\n'.join(lines), structured
    
    def _tesseract_process(self, image_path: str) -> Tuple[str, List[Dict]]:
        """
        Process image using Tesseract OCR.
        """
        import pytesseract
        from pytesseract import Output
        
        # Get text
        text = pytesseract.image_to_string(
            image_path,
            lang=self.config.ocr.language
        )
        
        # Get structured data
        data = pytesseract.image_to_data(
            image_path,
            output_type=Output.DICT
        )
        
        structured = []
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            if int(data['conf'][i]) > 30:  # Confidence threshold
                text_item = data['text'][i].strip()
                if text_item:
                    structured.append({
                        'text': text_item,
                        'confidence': data['conf'][i] / 100.0,
                        'bbox': [
                            data['left'][i],
                            data['top'][i],
                            data['width'][i],
                            data['height'][i]
                        ]
                    })
        
        return text, structured
    
    def process_pdf(self, pdf_path: str) -> Tuple[str, List[Dict]]:
        """
        Process PDF (scanned) by converting pages to images first.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Tuple of (extracted_text, page_data)
        """
        from pdf2image import convert_from_path
        
        config = self.config
        all_text = []
        all_data = []
        
        try:
            # Convert PDF to images
            logger.info(f"Converting PDF to images: {pdf_path}")
            images = convert_from_path(
                pdf_path,
                dpi=config.ocr.dpi,
                fmt='png'
            )
            
            logger.info(f"PDF has {len(images)} pages")
            
            # Process each page
            for page_num, image in enumerate(images, 1):
                logger.debug(f"Processing page {page_num}/{len(images)}")
                
                # Save to temp file (memory efficient)
                temp_path = f"temp_page_{page_num}.png"
                image.save(temp_path, 'PNG')
                
                try:
                    text, data = self.process_image(temp_path)
                    if text.strip():
                        all_text.append(f"\n--- Page {page_num} ---\n")
                        all_text.append(text)
                        all_data.append({
                            'page': page_num,
                            'content': data
                        })
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                
                # Batch delay for thermal management
                if config.processing.batch_delay > 0 and page_num % config.ocr.batch_size == 0:
                    import time
                    time.sleep(config.processing.batch_delay)
            
            return '\n'.join(all_text), all_data
            
        except Exception as e:
            logger.error(f"Failed to process PDF {pdf_path}: {e}")
            return "", []
    
    def process_batch(self, image_paths: List[str]) -> List[Tuple[str, List[Dict]]]:
        """
        Process multiple images in batch for efficiency.
        
        Args:
            image_paths: List of image file paths
        
        Returns:
            List of (text, data) tuples
        """
        results = []
        batch_size = self.config.ocr.batch_size
        
        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} files")
            
            for img_path in batch:
                result = self.process_image(img_path)
                results.append(result)
            
            # Delay between batches
            if self.config.processing.batch_delay > 0 and i + batch_size < len(image_paths):
                import time
                time.sleep(self.config.processing.batch_delay)
        
        return results


class OCRProcessor:
    """
    High-level OCR processor that handles file type detection
    and routes to appropriate processing method.
    """
    
    def __init__(self):
        self.engine = OCREngine()
    
    def process_file(self, file_path: str) -> Tuple[str, bool]:
        """
        Process any file with OCR.
        
        Args:
            file_path: Path to file to process
        
        Returns:
            Tuple of (extracted_text, success)
        """
        file_path = str(Path(file_path).resolve())
        file_type = detect_file_type(file_path)
        
        if not self.engine.initialize():
            logger.error("No OCR engine available")
            return "", False
        
        try:
            if file_type == "image":
                logger.info(f"Processing image: {file_path}")
                text, _ = self.engine.process_image(file_path)
                return text, True
                
            elif file_type == "document":
                # Check if PDF is scanned
                if file_path.lower().endswith('.pdf'):
                    if is_scanned_pdf(file_path):
                        logger.info(f"Processing scanned PDF: {file_path}")
                        text, _ = self.engine.process_pdf(file_path)
                        return text, True
                    else:
                        logger.info(f"PDF appears to have text, skipping OCR: {file_path}")
                        return "", False  # Signal to use document converter instead
                else:
                    # Other document types - try to convert to images
                    logger.info(f"Converting document to images: {file_path}")
                    # This would need document-to-image conversion
                    return "", False
                    
            else:
                logger.warning(f"Unsupported file type for OCR: {file_path}")
                return "", False
                
        except Exception as e:
            logger.error(f"OCR processing failed for {file_path}: {e}")
            return "", False


# Convenience function for direct OCR
def extract_text_from_image(image_path: str, use_paddle: bool = True) -> str:
    """
    Extract text from image using OCR.
    
    Args:
        image_path: Path to image file
        use_paddle: Use PaddleOCR if available
    
    Returns:
        Extracted text
    """
    processor = OCRProcessor()
    text, _ = processor.process_file(image_path)
    return text


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from scanned PDF using OCR.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Extracted text
    """
    processor = OCRProcessor()
    text, _ = processor.process_file(pdf_path)
    return text
