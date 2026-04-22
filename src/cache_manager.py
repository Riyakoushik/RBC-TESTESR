"""
Cache Manager for RBC-TESTER Knowledge System.
Uses SQLite for efficient metadata and embedding storage.
Optimized for low-memory systems (12GB RAM, 2GB VRAM).
"""

import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from loguru import logger

from .config import get_config, get_project_root


class CacheManager:
    """
    SQLite-based cache manager for knowledge system metadata.
    Stores file hashes, embeddings, dates, people, tags, and backlinks.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.config = get_config()
        self.project_root = get_project_root()
        
        if db_path is None:
            db_path = self.project_root / "cache" / "knowledge_cache.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize SQLite database with required tables."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Files table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP,
                    last_modified TIMESTAMP,
                    content_hash TEXT
                )
            """)
            
            # Dates table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    date_str TEXT NOT NULL,
                    date_normalized TEXT NOT NULL,
                    date_type TEXT,
                    FOREIGN KEY (file_id) REFERENCES files (id)
                )
            """)
            
            # People table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    person_name TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    FOREIGN KEY (file_id) REFERENCES files (id)
                )
            """)
            
            # Tags table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES files (id)
                )
            """)
            
            # Embeddings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL UNIQUE,
                    embedding BLOB NOT NULL,
                    embedding_dim INTEGER,
                    model_name TEXT,
                    created_at TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES files (id)
                )
            """)
            
            # Backlinks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backlinks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file_id INTEGER NOT NULL,
                    target_file_id INTEGER NOT NULL,
                    similarity REAL NOT NULL,
                    created_at TIMESTAMP,
                    FOREIGN KEY (source_file_id) REFERENCES files (id),
                    FOREIGN KEY (target_file_id) REFERENCES files (id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files (file_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dates_normalized ON dates (date_normalized)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_people_name ON people (person_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_name ON tags (tag)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backlinks_similarity ON backlinks (similarity)")
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cache database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize cache database: {e}")
            raise
    
    def _get_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file content."""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash {file_path}: {e}")
            return ""
    
    def _get_content_hash(self, content: str) -> str:
        """Calculate MD5 hash of text content."""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def register_file(self, file_path: str, title: str = None, content: str = "") -> int:
        """
        Register a file in the cache database.
        
        Args:
            file_path: Path to the file
            title: Extracted title (optional)
            content: File content for hash calculation (optional)
        
        Returns:
            File ID in database
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            file_hash = self._get_file_hash(file_path)
            content_hash = self._get_content_hash(content) if content else ""
            last_modified = datetime.fromtimestamp(Path(file_path).stat().st_mtime)
            
            cursor.execute("""
                INSERT OR REPLACE INTO files 
                (file_path, file_hash, title, last_modified, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM files WHERE file_path = ?), ?))
            """, (file_path, file_hash, title, last_modified, content_hash, file_path, datetime.now()))
            
            file_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return file_id
            
        except Exception as e:
            logger.error(f"Failed to register file {file_path}: {e}")
            return -1
    
    def store_dates(self, file_id: int, dates: List[Dict[str, Any]]):
        """
        Store extracted dates for a file.
        
        Args:
            file_id: File ID in database
            dates: List of date dictionaries with 'date_str', 'date_normalized', 'date_type'
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete existing dates for this file
            cursor.execute("DELETE FROM dates WHERE file_id = ?", (file_id,))
            
            # Insert new dates
            for date_info in dates:
                cursor.execute("""
                    INSERT INTO dates (file_id, date_str, date_normalized, date_type)
                    VALUES (?, ?, ?, ?)
                """, (file_id, date_info.get('date_str'), date_info.get('date_normalized'), date_info.get('date_type')))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store dates for file_id {file_id}: {e}")
    
    def store_people(self, file_id: int, people: List[str]):
        """
        Store extracted people names for a file.
        
        Args:
            file_id: File ID in database
            people: List of person names
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete existing people for this file
            cursor.execute("DELETE FROM people WHERE file_id = ?", (file_id,))
            
            # Insert new people
            for person in people:
                cursor.execute("""
                    INSERT INTO people (file_id, person_name)
                    VALUES (?, ?)
                """, (file_id, person))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store people for file_id {file_id}: {e}")
    
    def store_tags(self, file_id: int, tags: List[str]):
        """
        Store tags for a file.
        
        Args:
            file_id: File ID in database
            tags: List of tags
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete existing tags for this file
            cursor.execute("DELETE FROM tags WHERE file_id = ?", (file_id,))
            
            # Insert new tags
            for tag in tags:
                cursor.execute("""
                    INSERT INTO tags (file_id, tag)
                    VALUES (?, ?)
                """, (file_id, tag))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store tags for file_id {file_id}: {e}")
    
    def store_embedding(self, file_id: int, embedding: List[float], model_name: str = "all-MiniLM-L6-v2"):
        """
        Store embedding vector for a file.
        
        Args:
            file_id: File ID in database
            embedding: Embedding vector as list of floats
            model_name: Name of the embedding model used
        """
        try:
            import numpy as np
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert embedding to bytes for storage
            embedding_array = np.array(embedding, dtype=np.float32)
            embedding_blob = embedding_array.tobytes()
            
            cursor.execute("""
                INSERT OR REPLACE INTO embeddings 
                (file_id, embedding, embedding_dim, model_name, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (file_id, embedding_blob, len(embedding), model_name, datetime.now()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store embedding for file_id {file_id}: {e}")
    
    def get_embedding(self, file_id: int) -> Optional[List[float]]:
        """
        Retrieve embedding for a file.
        
        Args:
            file_id: File ID in database
        
        Returns:
            Embedding vector as list of floats, or None if not found
        """
        try:
            import numpy as np
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT embedding, embedding_dim FROM embeddings WHERE file_id = ?", (file_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                embedding_blob, dim = result
                embedding_array = np.frombuffer(embedding_blob, dtype=np.float32)
                return embedding_array.tolist()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve embedding for file_id {file_id}: {e}")
            return None
    
    def store_backlink(self, source_file_id: int, target_file_id: int, similarity: float):
        """
        Store a backlink relationship between files.
        
        Args:
            source_file_id: Source file ID
            target_file_id: Target file ID
            similarity: Similarity score (0-1)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO backlinks 
                (source_file_id, target_file_id, similarity, created_at)
                VALUES (?, ?, ?, ?)
            """, (source_file_id, target_file_id, similarity, datetime.now()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to store backlink: {e}")
    
    def get_all_file_embeddings(self) -> List[Tuple[int, List[float]]]:
        """
        Get all file embeddings for similarity search.
        
        Returns:
            List of (file_id, embedding) tuples
        """
        try:
            import numpy as np
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT file_id, embedding FROM embeddings")
            results = cursor.fetchall()
            conn.close()
            
            embeddings = []
            for file_id, embedding_blob in results:
                embedding_array = np.frombuffer(embedding_blob, dtype=np.float32)
                embeddings.append((file_id, embedding_array.tolist()))
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to get all embeddings: {e}")
            return []
    
    def get_file_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file information by path.
        
        Args:
            file_path: Path to the file
        
        Returns:
            File information dictionary or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, file_path, title, created_at FROM files WHERE file_path = ?", (file_path,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result[0],
                    'file_path': result[1],
                    'title': result[2],
                    'created_at': result[3]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get file by path: {e}")
            return None
    
    def get_timeline_data(self) -> Dict[str, List[str]]:
        """
        Get all dates and associated files for timeline generation.
        
        Returns:
            Dictionary mapping normalized dates to list of file paths
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT d.date_normalized, f.file_path
                FROM dates d
                JOIN files f ON d.file_id = f.id
                ORDER BY d.date_normalized DESC
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            timeline = {}
            for date_str, file_path in results:
                if date_str not in timeline:
                    timeline[date_str] = []
                timeline[date_str].append(file_path)
            
            return timeline
            
        except Exception as e:
            logger.error(f"Failed to get timeline data: {e}")
            return {}
    
    def get_file_dates(self, file_path: str) -> List[str]:
        """
        Get all dates for a specific file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            List of normalized date strings
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT d.date_normalized
                FROM dates d
                JOIN files f ON d.file_id = f.id
                WHERE f.file_path = ?
                ORDER BY d.date_normalized
            """, (file_path,))
            
            results = cursor.fetchall()
            conn.close()
            
            return [row[0] for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get file dates: {e}")
            return []
    
    def get_file_people(self, file_path: str) -> List[str]:
        """
        Get all people mentioned in a file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            List of person names
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT p.person_name
                FROM people p
                JOIN files f ON p.file_id = f.id
                WHERE f.file_path = ?
                ORDER BY p.person_name
            """, (file_path,))
            
            results = cursor.fetchall()
            conn.close()
            
            return [row[0] for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get file people: {e}")
            return []
    
    def get_file_tags(self, file_path: str) -> List[str]:
        """
        Get all tags for a file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            List of tags
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT t.tag
                FROM tags t
                JOIN files f ON t.file_id = f.id
                WHERE f.file_path = ?
                ORDER BY t.tag
            """, (file_path,))
            
            results = cursor.fetchall()
            conn.close()
            
            return [row[0] for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get file tags: {e}")
            return []
    
    def get_file_backlinks(self, file_path: str, threshold: float = 0.75) -> List[Dict[str, Any]]:
        """
        Get backlinks for a file above similarity threshold.
        
        Args:
            file_path: Path to the file
            threshold: Minimum similarity score (default 0.75)
        
        Returns:
            List of backlink dictionaries with target file info
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT f2.file_path, f2.title, b.similarity
                FROM backlinks b
                JOIN files f1 ON b.source_file_id = f1.id
                JOIN files f2 ON b.target_file_id = f2.id
                WHERE f1.file_path = ? AND b.similarity >= ?
                ORDER BY b.similarity DESC
            """, (file_path, threshold))
            
            results = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'file_path': row[0],
                    'title': row[1],
                    'similarity': row[2]
                }
                for row in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to get file backlinks: {e}")
            return []
    
    def clear_file_data(self, file_path: str):
        """
        Clear all data for a specific file (for reprocessing).
        
        Args:
            file_path: Path to the file
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get file ID
            cursor.execute("SELECT id FROM files WHERE file_path = ?", (file_path,))
            result = cursor.fetchone()
            
            if result:
                file_id = result[0]
                
                # Delete related data
                cursor.execute("DELETE FROM dates WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM people WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM tags WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM embeddings WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM backlinks WHERE source_file_id = ? OR target_file_id = ?", (file_id, file_id))
                cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
                
                conn.commit()
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to clear file data: {e}")
