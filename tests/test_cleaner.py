"""Tests for text cleaner and content optimizer."""

import pytest
from src.cleaner import TextCleaner, ContentOptimizer, CleanResult


@pytest.fixture
def cleaner():
    return TextCleaner()


@pytest.fixture
def optimizer():
    return ContentOptimizer()


class TestTextCleaner:
    def test_normalize_line_endings(self, cleaner):
        text = "line1\r\nline2\rline3\nline4"
        result = cleaner._normalize_line_endings(text)
        assert "\r" not in result
        assert result == "line1\nline2\nline3\nline4"

    def test_remove_junk_lines_page_numbers(self, cleaner):
        text = "Some content\n42\nMore content\nPage 5\nFinal content"
        result = cleaner._remove_junk_lines(text)
        assert "42" not in result
        assert "Page 5" not in result
        assert "Some content" in result

    def test_sliding_window_dedup_preserves_order(self, cleaner):
        """Test that dedup correctly evicts oldest entries, not random ones."""
        lines = ["line_a", "line_b", "line_c", "line_d", "line_e", "line_a"]
        text = "\n".join(lines)
        result = cleaner._remove_duplicate_lines(text)
        result_lines = result.split("\n")
        # "line_a" appears again after window has moved past it,
        # so behavior depends on window size (default 5).
        # With window=5, line_a should still be in the window, so the duplicate is removed.
        assert result_lines.count("line_a") == 1

    def test_ocr_fix_does_not_corrupt_valid_words(self, cleaner):
        """Ensure OCR fixes don't corrupt words like 'return', 'class', 'learn'."""
        text = "return value from class method and learn something"
        result = cleaner._fix_common_ocr_errors(text)
        assert "return" in result
        assert "class" in result
        assert "learn" in result

    def test_normalize_for_comparison(self, cleaner):
        """Test that normalization doesn't replace digits with letters."""
        normalized = cleaner._normalize_for_comparison("Total: 2024 items")
        assert "2024" in normalized

    def test_remove_empty_lines(self, cleaner):
        text = "line1\n\n\n\n\nline2"
        result = cleaner._remove_empty_lines(text)
        # Should keep at most 2 consecutive empty lines
        assert "\n\n\n" not in result
        assert "line1" in result
        assert "line2" in result

    def test_full_clean(self, cleaner):
        text = "Hello world\r\n\r\nHello world\n42\nSome content\n\n\n\n\nMore"
        result = cleaner.clean(text)
        assert isinstance(result, CleanResult)
        assert "Some content" in result.text


class TestContentOptimizer:
    def test_process_adds_newline(self, optimizer):
        result = optimizer.process("hello")
        assert result.endswith("\n")

    def test_process_cleans_text(self, optimizer):
        text = "content\r\ncontent\n42\nmore"
        result = optimizer.process(text)
        assert "42" not in result
