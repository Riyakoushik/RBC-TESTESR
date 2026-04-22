#!/usr/bin/env python3
"""
RBC-TESTER Document Conversion Pipeline
Entry point script for running the document converter.

Usage:
    python convert.py                    # Convert all files in input/
    python convert.py convert -v           # Verbose mode
    python convert.py status               # Check conversion status
    python convert.py reset --yes          # Reset progress

For detailed help:
    python convert.py --help
    python convert.py convert --help
"""

import sys
from pathlib import Path

# Ensure src package is importable
project_root = Path(__file__).parent
src_path = project_root / "src"

if str(src_path) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.main import app

if __name__ == "__main__":
    app()
