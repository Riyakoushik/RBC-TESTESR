"""Tests for configuration loading and validation."""

import pytest
from src.config import Config, SupportedFormats, ProcessingConfig, load_config


def test_default_config():
    """Test that default config loads without errors."""
    config = Config()
    assert config.paths.input_dir == "input"
    assert config.paths.output_dir == "output"
    assert config.ocr.primary_engine in ("easyocr", "paddleocr")
    assert config.processing.batch_size == 10


def test_processing_config_has_new_fields():
    """Test that ProcessingConfig includes recursive and file size fields."""
    config = ProcessingConfig()
    assert config.recursive is True
    assert config.max_file_size_mb == 0
    assert config.min_file_size_kb == 1


def test_supported_formats_include_email():
    """Test that supported formats include email types."""
    fmt = SupportedFormats()
    assert ".mbox" in fmt.email
    assert ".eml" in fmt.email


def test_supported_formats_include_latex():
    """Test that supported formats include LaTeX types."""
    fmt = SupportedFormats()
    assert ".tex" in fmt.latex
    assert ".latex" in fmt.latex


def test_get_all_extensions():
    """Test that get_all_extensions includes email and latex."""
    config = Config()
    exts = config.get_all_extensions()
    assert ".mbox" in exts
    assert ".tex" in exts
    assert ".pdf" in exts
    assert ".py" in exts
