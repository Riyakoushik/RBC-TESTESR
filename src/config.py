"""
Configuration management for RBC-TESTER.
Loads and validates YAML configuration with sensible defaults.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from loguru import logger


class PathsConfig(BaseModel):
    """Path configuration for input/output directories."""
    input_dir: str = "input"
    output_dir: str = "output"
    logs_dir: str = "logs"
    failed_files_log: str = "failed_files.txt"
    summary_file: str = "summary.json"
    state_file: str = ".conversion_state.json"
    cache_dir: str = "cache"
    knowledge_dir: str = "knowledge"


class OCRConfig(BaseModel):
    """OCR engine configuration."""
    primary_engine: str = "paddleocr"
    fallback_engine: str = "tesseract"
    language: str = "en"
    use_gpu: bool = False
    batch_size: int = 4
    dpi: int = 200
    thread_count: int = 2


class CleaningConfig(BaseModel):
    """Text cleaning and normalization settings."""
    duplicate_window: int = 5
    min_line_length: int = 3
    remove_patterns: List[str] = Field(default_factory=lambda: [
        "^\\s*\\d+\\s*$",
        "^Page \\d+",
        "^Copyright",
        "^©",
        "^All rights",
        "^Confidential"
    ])
    normalize_whitespace: bool = True
    fix_ocr_errors: bool = True


class ProcessingConfig(BaseModel):
    """Processing behavior configuration."""
    batch_size: int = 10
    batch_delay: int = 2
    max_memory_percent: int = 80
    max_cpu_percent: int = 0
    auto_resume: bool = True
    skip_existing: bool = True
    output_format: str = "md"
    recursive: bool = True
    max_file_size_mb: int = 0
    min_file_size_kb: int = 1


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    max_size_mb: int = 10
    backup_count: int = 3
    console_output: bool = True
    file_output: bool = True


class TablesConfig(BaseModel):
    """Table extraction configuration."""
    convert_to_markdown: bool = True
    min_rows: int = 2
    min_columns: int = 2
    include_captions: bool = True


class SupportedFormats(BaseModel):
    """Supported file format extensions - unlimited support."""
    documents: List[str] = Field(default_factory=lambda: [
        ".pdf", ".docx", ".doc", ".docm", ".pptx", ".ppt", ".pptm",
        ".odt", ".ods", ".odp", ".epub", ".mobi", ".rtf", ".tex"
    ])
    images: List[str] = Field(default_factory=lambda: [
        ".png", ".jpg", ".jpeg", ".jpe", ".jfif", ".tiff", ".tif",
        ".bmp", ".gif", ".webp", ".svg", ".ico", ".heic", ".heif",
        ".avif", ".jp2", ".j2k"
    ])
    text: List[str] = Field(default_factory=lambda: [
        ".txt", ".md", ".markdown", ".html", ".htm", ".xhtml", ".xml",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
        ".csv", ".tsv", ".log", ".rst", ".adoc", ".tex", ".bib"
    ])
    code: List[str] = Field(default_factory=lambda: [
        ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".hpp",
        ".cs", ".php", ".rb", ".go", ".rs", ".swift", ".kt", ".scala",
        ".r", ".m", ".sh", ".bash", ".zsh", ".ps1", ".sql", ".pl",
        ".lua", ".dart", ".jsx", ".tsx", ".vue", ".svelte", ".css",
        ".scss", ".sass", ".less"
    ])
    data: List[str] = Field(default_factory=lambda: [
        ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".csv",
        ".tsv", ".parquet", ".feather", ".pickle", ".pkl"
    ])
    archives: List[str] = Field(default_factory=lambda: [
        ".zip", ".tar", ".tar.gz", ".tgz", ".rar", ".7z"
    ])
    ebooks: List[str] = Field(default_factory=lambda: [
        ".epub", ".mobi", ".azw", ".azw3", ".fb2"
    ])
    spreadsheets: List[str] = Field(default_factory=lambda: [
        ".xlsx", ".xls", ".xlsm", ".ods", ".csv", ".tsv"
    ])
    presentations: List[str] = Field(default_factory=lambda: [
        ".pptx", ".ppt", ".pptm", ".odp", ".key"
    ])
    audio: List[str] = Field(default_factory=lambda: [
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"
    ])
    video: List[str] = Field(default_factory=lambda: [
        ".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv"
    ])
    email: List[str] = Field(default_factory=lambda: [
        ".mbox", ".eml", ".msg"
    ])
    latex: List[str] = Field(default_factory=lambda: [
        ".tex", ".latex", ".bib", ".sty", ".cls"
    ])
    google_takeout: List[str] = Field(default_factory=lambda: [
        ".json"
    ])


class KnowledgeConfig(BaseModel):
    """Knowledge system configuration for second-brain features."""
    enabled: bool = True
    backlink_threshold: float = 0.75
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 10
    max_embedding_length: int = 512
    known_people: List[str] = Field(default_factory=list)


class Config(BaseModel):
    """Main application configuration container."""
    paths: PathsConfig = Field(default_factory=PathsConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    tables: TablesConfig = Field(default_factory=TablesConfig)
    supported_formats: SupportedFormats = Field(default_factory=SupportedFormats)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)

    def get_all_extensions(self) -> set:
        """Get all supported file extensions as a set."""
        exts = set()
        exts.update(self.supported_formats.documents)
        exts.update(self.supported_formats.images)
        exts.update(self.supported_formats.text)
        exts.update(self.supported_formats.code)
        exts.update(self.supported_formats.data)
        exts.update(self.supported_formats.archives)
        exts.update(self.supported_formats.ebooks)
        exts.update(self.supported_formats.spreadsheets)
        exts.update(self.supported_formats.presentations)
        exts.update(self.supported_formats.audio)
        exts.update(self.supported_formats.video)
        exts.update(self.supported_formats.email)
        exts.update(self.supported_formats.latex)
        return exts


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file. If None, searches for config.yaml
                    in current directory and parent directories.
    
    Returns:
        Config object with loaded settings or defaults if file not found.
    """
    if config_path is None:
        # Search for config.yaml in current and parent directories
        current = Path.cwd()
        for path in [current] + list(current.parents):
            config_file = path / "config.yaml"
            if config_file.exists():
                config_path = str(config_file)
                break
    
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return Config(**data)
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
            logger.info("Using default configuration")
    else:
        logger.info("No config file found, using defaults")
    
    return Config()


def get_project_root() -> Path:
    """Get the project root directory (where this file's parent is)."""
    return Path(__file__).parent.parent


# Global config instance (initialized on first access)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path: Optional[str] = None) -> Config:
    """Reload configuration from file."""
    global _config
    _config = load_config(config_path)
    return _config
