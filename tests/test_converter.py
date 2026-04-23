"""Tests for archive safety and converter helpers."""

import pytest
from src.converter import _is_safe_archive_member


def test_safe_archive_member():
    assert _is_safe_archive_member("file.txt", "/tmp/extract") is True
    assert _is_safe_archive_member("subdir/file.txt", "/tmp/extract") is True


def test_unsafe_archive_member_path_traversal():
    assert _is_safe_archive_member("../../../etc/passwd", "/tmp/extract") is False
    assert _is_safe_archive_member("subdir/../../etc/shadow", "/tmp/extract") is False


def test_unsafe_archive_member_absolute():
    assert _is_safe_archive_member("/etc/passwd", "/tmp/extract") is False
