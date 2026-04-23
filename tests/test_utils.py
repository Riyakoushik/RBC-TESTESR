"""Tests for utility functions."""

import os
import tempfile
import pytest
from src.utils import detect_file_type, get_file_hash, get_output_path


def test_detect_file_type_pdf():
    assert detect_file_type("document.pdf") == "document"


def test_detect_file_type_image():
    assert detect_file_type("photo.png") == "image"
    assert detect_file_type("photo.jpg") == "image"


def test_detect_file_type_code():
    assert detect_file_type("script.py") == "code"
    assert detect_file_type("app.js") == "code"


def test_detect_file_type_email():
    assert detect_file_type("archive.mbox") == "email"
    assert detect_file_type("message.eml") == "email"


def test_detect_file_type_latex():
    assert detect_file_type("paper.tex") == "latex"
    assert detect_file_type("paper.latex") == "latex"


def test_detect_file_type_archive():
    assert detect_file_type("data.zip") == "archive"
    assert detect_file_type("data.tar") == "archive"


def test_detect_file_type_unknown():
    assert detect_file_type("mystery.xyz123") == "unknown"


def test_get_file_hash():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("test content")
        f.flush()
        hash_val = get_file_hash(f.name)
        assert len(hash_val) == 32  # MD5 hex length
    os.unlink(f.name)


def test_get_file_hash_nonexistent():
    result = get_file_hash("/nonexistent/file.txt")
    assert result == ""
