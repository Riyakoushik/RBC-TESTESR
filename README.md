# RBC-TESTER Document Conversion Pipeline

**Ultimate Document Conversion System - Convert ANY File to Markdown**

A local-first, unlimited file type conversion pipeline designed for the emotional-AI project. Converts PDFs, scanned documents, images, code, archives, presentations, spreadsheets, ebooks, audio, video, and 200+ file formats into clean, structured markdown/text files optimized for AI dataset creation.

## 🚀 Key Features

- **UNLIMITED File Type Support**: 200+ file formats including documents, images, code, archives, spreadsheets, presentations, ebooks, audio, video
- **Smart OCR Pipeline**: EasyOCR (primary) with Tesseract fallback - works on Python 3.14+
- **Advanced Document Processing**: Unstructured.io for comprehensive format handling
- **Archive Extraction**: Auto-extracts and converts ZIP, TAR, RAR, 7Z contents
- **Code to Markdown**: Converts 50+ programming languages with syntax highlighting
- **Table Extraction**: Converts Excel, CSV, TSV to Markdown tables
- **Text Cleaning**: Removes duplicates, headers, footers, page numbers, OCR artifacts
- **Progress Tracking**: Live CPU, RAM, disk monitoring with ETA calculation
- **Resume Capability**: Automatically resumes interrupted conversions
- **Batch Processing**: Memory-efficient processing with thermal management
- **Python 3.14 Compatible**: No need to downgrade Python version
- **Recursive Processing**: Handles nested directories automatically

## 📦 Installation

### Prerequisites

- Python 3.9 or higher (tested on Python 3.14)
- Windows 10/11 (Linux/macOS compatible)
- Tesseract OCR (for fallback)

### Install Tesseract (Windows)

```powershell
# Via winget
winget install UB-Mannheim.TesseractOCR

# Or download from:
# https://github.com/UB-Mannheim/tesseract/wiki
```

### Setup Project

```bash
# Clone or create project directory
cd RBC-TESTER

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install all dependencies (unlimited support)
pip install -r requirements.txt
```

### Optional: Audio/Video Support

```bash
# For audio transcription (requires whisper-openai)
pip install whisper-openai

# For 7z archive support
pip install py7zr

# For RAR archive support
pip install rarfile
```

## 🎯 Quick Start

### Convert Everything in One Command

```bash
# Place all files in input/ directory (any format)
python convert.py convert

# Results appear in output/ directory as .md files
```

### Convert Specific File Types

```bash
# Convert all PDFs
python convert.py convert --filter .pdf

# Convert all images
python convert.py convert --filter .png

# Convert all code files
python convert.py convert --filter .py
```

## 📚 Supported File Types (200+ Formats)

### 📄 Documents
- PDF, DOCX, DOC, DOCM, PPTX, PPT, PPTM
- ODT, ODS, ODP (OpenOffice)
- EPUB, MOBI, AZW, AZW3, FB2 (E-books)
- RTF, TEX, LATEX

### 🖼️ Images (OCR Applied)
- PNG, JPG, JPEG, JPE, JFIF
- TIFF, TIF, BMP, GIF, WEBP
- SVG, ICO, HEIC, HEIF, AVIF, JP2, J2K

### 💻 Code (50+ Languages)
- Python, JavaScript, TypeScript, Java, C, C++
- C#, PHP, Ruby, Go, Rust, Swift, Kotlin
- Scala, R, MATLAB, Shell, PowerShell, SQL
- Perl, Lua, Dart, JSX, TSX, Vue, Svelte
- CSS, SCSS, SASS, Less, XML, WXML

### 📊 Data & Spreadsheets
- JSON, JSONL, YAML, YML, TOML, INI, CFG
- CSV, TSV, Parquet, Feather, Pickle
- XLSX, XLS, XLSM, ODS

### 🗜️ Archives (Auto-Extract & Convert)
- ZIP, TAR, TAR.GZ, TGZ, RAR, 7Z

### 🎵 Audio (Optional Transcription)
- MP3, WAV, FLAC, AAC, OGG, M4A, WMA

### 🎥 Video (Optional Frame Extraction)
- MP4, AVI, MOV, MKV, WEBM, FLV, WMV

### 📝 Text & Markup
- TXT, MD, MARKDOWN, HTML, HTM, XHTML
- XML, LOG, RST, ADOC, BIB

## 🛠️ CLI Commands

### Convert All Files

```bash
# Basic conversion (all supported formats)
python convert.py convert

# With custom directories
python convert.py convert -i ./my_documents -o ./converted

# Verbose output
python convert.py convert -v

# Force reprocess all files
python convert.py convert --no-resume
```

### Convert Single File

```bash
python convert.py convert-single document.pdf
python convert.py convert-single image.png
python convert.py convert-single code.py
python convert.py convert-single archive.zip
```

### Check Status

```bash
python convert.py status
```

### Reset Progress

```bash
# Reset state (will reprocess all files)
python convert.py reset --yes

# Clean output directory
python convert.py clean-output --yes
```

## ⚙️ Configuration

Edit `config.yaml` for full control:

```yaml
# OCR Configuration
ocr:
  primary_engine: "easyocr"    # Works on Python 3.14
  fallback_engine: "tesseract"
  language: "en"              # Supports: en, es, fr, de, it, pt, ru, ja, ko, zh-cn, zh-tw
  use_gpu: false
  batch_size: 4

# Processing
processing:
  batch_size: 10
  batch_delay: 2
  max_memory_percent: 80
  output_format: "md"          # "md" or "txt"
  recursive: true              # Process nested directories
  max_file_size_mb: 0          # 0 = no limit
  min_file_size_kb: 1

# Text Cleaning
cleaning:
  duplicate_window: 5
  min_line_length: 3
  remove_patterns:
    - "^\\s*\\d+\\s*$"
    - "^Page \\d+"
    - "^Copyright"
```

## 📁 Project Structure

```
RBC-TESTER/
├── input/                  # Place ANY files here (any format)
│   ├── documents/
│   │   ├── report.pdf
│   │   └── slides.pptx
│   ├── code/
│   │   ├── script.py
│   │   └── app.js
│   ├── images/
│   │   ├── scan.png
│   │   └── diagram.jpg
│   └── archives/
│       └── data.zip
├── output/                 # All converted to .md files
│   ├── documents/
│   │   ├── report.md
│   │   └── slides.md
│   ├── code/
│   │   ├── script.md
│   │   └── app.md
│   ├── images/
│   │   ├── scan.md
│   │   └── diagram.md
│   └── archives_extracted/  # Auto-extracted archives
├── logs/                   # Conversion logs
├── src/
│   ├── main.py            # CLI entry point
│   ├── converter.py       # Document conversion logic
│   ├── ocr.py             # OCR processing
│   ├── cleaner.py         # Text cleaning
│   ├── monitor.py         # System monitoring
│   ├── utils.py           # File utilities
│   └── config.py          # Configuration
├── config.yaml            # User configuration
├── requirements.txt       # Python dependencies
└── convert.py             # Entry point script
```

## 🎓 Fully-Fledged Conversion Prompt

**To convert ALL files to Markdown with NO LIMITS:**

```bash
# Step 1: Place ALL your files in the input/ directory
# - Documents (PDF, DOCX, PPTX, EPUB, etc.)
# - Images (PNG, JPG, etc.) - will be OCR'd
# - Code files (Python, JS, etc.) - will be syntax highlighted
# - Archives (ZIP, TAR, etc.) - will be auto-extracted
# - Spreadsheets (Excel, CSV) - will be table-converted
# - Audio/Video (optional) - requires additional setup

# Step 2: Configure for unlimited processing
# Edit config.yaml:
processing:
  recursive: true              # Process all subdirectories
  max_file_size_mb: 0          # No file size limit
  skip_existing: false         # Process all files
  output_format: "md"          # Output as Markdown

# Step 3: Run the conversion
python convert.py convert

# Step 4: Check results
# All files in input/ are now converted to .md in output/
# Archive contents are extracted and converted
# Code files have syntax highlighting
# Tables are converted to Markdown format
# OCR text from images is included
```

## 📊 Output Format Examples

### Code Files → Markdown with Syntax Highlighting

```markdown
```python
def hello_world():
    print("Hello, World!")
```
```

### Spreadsheets → Markdown Tables

```markdown
| Name | Age | City |
|------|-----|------|
| John | 25  | NYC  |
| Jane | 30  | LA   |
```

### Images → OCR Text

```markdown
# Extracted from scan.png
This is the text that was in the image...
```

### Archives → Extracted & Converted

```
input/
  data.zip
    ├── document.pdf
    └── image.png

output/
  data_extracted/
    ├── document.md
    └── image.md
```

## 🔧 Performance Optimization

### For Low-End Systems (12GB RAM, 2GB VRAM)

```yaml
# config.yaml
processing:
  batch_size: 5
  batch_delay: 3
  max_memory_percent: 70

ocr:
  batch_size: 2
  use_gpu: false
```

### For High-End Systems

```yaml
# config.yaml
processing:
  batch_size: 20
  batch_delay: 0
  max_memory_percent: 90

ocr:
  batch_size: 8
  use_gpu: true
```

## 🐛 Troubleshooting

### EasyOCR Not Working

```bash
# EasyOCR should work on Python 3.14+
# If issues occur, it will fall back to Tesseract
```

### Archive Extraction Issues

```bash
# For 7z support
pip install py7zr

# For RAR support
pip install rarfile
```

### Memory Errors

1. Reduce `batch_size` in config
2. Reduce `ocr.batch_size`
3. Increase `batch_delay`
4. Process files in smaller batches

## 📈 API Usage

### Python API

```python
from src.converter import DocumentConverterPipeline

# Initialize pipeline
pipeline = DocumentConverterPipeline()

# Convert single file
output_path, success = pipeline.convert_file("document.pdf")

# Convert directory
pipeline.convert_directory()
```

### Direct OCR

```python
from src.ocr import OCRProcessor

ocr = OCRProcessor()
text, success = ocr.process_file("image.png")
```

## 🎯 Use Cases

- **AI Dataset Creation**: Convert diverse documents to unified Markdown format
- **Code Documentation**: Extract code with syntax highlighting
- **Research Paper Processing**: Convert PDFs, images, and references
- **Archive Migration**: Extract and convert old archives
- **Content Migration**: Move from various formats to Markdown
- **OCR Digitization**: Convert scanned documents to searchable text

## 🔍 Monitoring

Live progress display with system metrics:

```
┌─────────────────────────────────────┐  ┌─────────────────┐
│  Converting files...                │  │ CPU: 45%        │
│  ████████████████████████░░ 75%     │  │ Memory: 62%     │
│  [150/200] ETA: 5m 30s             │  │ Disk: 45.2 GB   │
├─────────────────────────────────────┤  │ Files/min: 8.5  │
│ Current: large_archive.zip          │  └─────────────────┘
└─────────────────────────────────────┘

Total: 200  Successful: 150  Failed: 2  Extracted: 125.5 MB
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    main.py (CLI)                     │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────┐  ┌─────────────────┐  │
│  │ converter.py│  │monitor.py│  │    utils.py     │  │
│  │ (Unstructured│  │(psutil)  │  │ (State/Paths)   │  │
│  │  .io)       │  └──────────┘  └─────────────────┘  │
│  ├─────────────┤                                    │
│  │  ┌───────┐  │  ┌──────────┐                       │
│  │  │ocr.py │  │  │cleaner.py│                       │
│  │  │EasyOCR│  │  │          │                       │
│  │  │Tesseract│  │(Text/Table)│                     │
│  │  └───────┘  │  └──────────┘                       │
│  └─────────────┘                                    │
└─────────────────────────────────────────────────────┘
```

## 📝 License

MIT License

## 🙏 Credits

- [Unstructured.io](https://github.com/Unstructured-IO/unstructured) - Universal document processing
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) - OCR engine (Python 3.14 compatible)
- [Tesseract](https://github.com/tesseract-ocr/tesseract) - Fallback OCR
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal UI
