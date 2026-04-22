"""
Backlink Engine for RBC-TESTER Knowledge System.
Generates backlinks based on semantic similarity using embeddings.
Optimized for low-memory systems with batched processing.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

from .config import get_config, get_project_root
from .cache_manager import CacheManager
from .embedding_engine import EmbeddingEngine


class BacklinkEngine:
    """
    Generates and manages backlinks between files based on semantic similarity.
    Uses embeddings to find related notes and create automatic connections.
    """
    
    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        embedding_engine: Optional[EmbeddingEngine] = None,
        similarity_threshold: float = 0.75
    ):
        self.config = get_config()
        self.project_root = get_project_root()
        
        if cache_manager is None:
            self.cache = CacheManager()
        else:
            self.cache = cache_manager
        
        if embedding_engine is None:
            self.embedding_engine = EmbeddingEngine(self.cache)
        else:
            self.embedding_engine = embedding_engine
        
        self.similarity_threshold = similarity_threshold
        self.backlinks_path = self.project_root / "knowledge" / "backlinks" / "backlinks.json"
        self.backlinks_path.parent.mkdir(parents=True, exist_ok=True)
    
    def generate_backlinks_for_file(self, file_path: str, text: str) -> List[Dict[str, Any]]:
        """
        Generate backlinks for a file based on similarity with existing files.
        
        Args:
            file_path: Path to the file
            text: File content for embedding generation
        
        Returns:
            List of backlink dictionaries
        """
        try:
            # Register file in cache
            file_id = self.cache.register_file(file_path, content=text)
            
            if file_id < 0:
                logger.warning(f"Failed to register file: {file_path}")
                return []
            
            # Generate and store embedding
            self.embedding_engine.add_embedding(file_id, text)
            
            # Find similar files
            similar_files = self.embedding_engine.find_similar_files(
                file_id,
                k=10,
                exclude_self=True
            )
            
            # Filter by similarity threshold
            backlinks = []
            for similar_file_id, similarity in similar_files:
                if similarity >= self.similarity_threshold:
                    # Get file info from cache
                    import sqlite3
                    conn = sqlite3.connect(self.cache.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT file_path, title FROM files WHERE id = ?",
                        (similar_file_id,)
                    )
                    result = cursor.fetchone()
                    conn.close()
                    
                    if result:
                        backlinks.append({
                            'file_path': result[0],
                            'title': result[1] or Path(result[0]).stem,
                            'similarity': similarity
                        })
                        
                        # Store backlink in cache
                        self.cache.store_backlink(file_id, similar_file_id, similarity)
            
            logger.info(f"Generated {len(backlinks)} backlinks for {file_path}")
            return backlinks
            
        except Exception as e:
            logger.error(f"Failed to generate backlinks for {file_path}: {e}")
            return []
    
    def regenerate_all_backlinks(self, file_paths: List[str], texts: List[str]):
        """
        Regenerate backlinks for all files.
        Useful after adding many new files or changing threshold.
        
        Args:
            file_paths: List of file paths
            texts: List of corresponding file contents
        """
        try:
            logger.info(f"Regenerating backlinks for {len(file_paths)} files")
            
            # Clear existing backlinks
            self._clear_all_backlinks()
            
            # Rebuild embeddings index
            self.embedding_engine._load_embeddings_from_cache()
            
            # Generate backlinks for each file
            for file_path, text in zip(file_paths, texts):
                self.generate_backlinks_for_file(file_path, text)
            
            # Save backlinks to JSON
            self._save_backlinks()
            
            logger.info("Backlink regeneration complete")
            
        except Exception as e:
            logger.error(f"Failed to regenerate backlinks: {e}")
    
    def _clear_all_backlinks(self):
        """Clear all backlinks from cache."""
        try:
            conn = self.cache._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM backlinks")
            conn.commit()
            conn.close()
            logger.info("Cleared all backlinks")
        except Exception as e:
            logger.error(f"Failed to clear backlinks: {e}")
    
    def _save_backlinks(self):
        """Save backlinks to JSON file for easy access."""
        try:
            # Get all backlinks from cache
            conn = self.cache._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT f1.file_path as source, f2.file_path as target, f2.title, b.similarity
                FROM backlinks b
                JOIN files f1 ON b.source_file_id = f1.id
                JOIN files f2 ON b.target_file_id = f2.id
                WHERE b.similarity >= ?
                ORDER BY b.similarity DESC
            """, (self.similarity_threshold,))
            
            results = cursor.fetchall()
            conn.close()
            
            # Organize by source file
            backlinks_dict = {}
            for source, target, title, similarity in results:
                if source not in backlinks_dict:
                    backlinks_dict[source] = []
                backlinks_dict[source].append({
                    'file_path': target,
                    'title': title or Path(target).stem,
                    'similarity': similarity
                })
            
            # Save to JSON
            with open(self.backlinks_path, 'w', encoding='utf-8') as f:
                json.dump(backlinks_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved backlinks to {self.backlinks_path}")
            
        except Exception as e:
            logger.error(f"Failed to save backlinks: {e}")
    
    def get_backlinks(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Get backlinks for a specific file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            List of backlink dictionaries
        """
        return self.cache.get_file_backlinks(file_path, self.similarity_threshold)
    
    def generate_backlinks_markdown(self, file_path: str) -> str:
        """
        Generate backlinks section for a file's markdown.
        
        Args:
            file_path: Path to the file
        
        Returns:
            Markdown string with backlinks
        """
        backlinks = self.get_backlinks(file_path)
        
        if not backlinks:
            return ""
        
        lines = ["## Related Notes"]
        for backlink in backlinks:
            # Use wikilink format: [[filename]]
            filename = Path(backlink['file_path']).stem
            lines.append(f"- [[{filename}]]")
        
        return "\n".join(lines)
    
    def get_backlink_network_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the backlink network.
        
        Returns:
            Dictionary with network statistics
        """
        try:
            conn = self.cache._get_connection()
            cursor = conn.cursor()
            
            # Count total backlinks
            cursor.execute("SELECT COUNT(*) FROM backlinks WHERE similarity >= ?", (self.similarity_threshold,))
            total_backlinks = cursor.fetchone()[0]
            
            # Count files with backlinks
            cursor.execute("""
                SELECT COUNT(DISTINCT source_file_id)
                FROM backlinks
                WHERE similarity >= ?
            """, (self.similarity_threshold,))
            files_with_backlinks = cursor.fetchone()[0]
            
            # Get average similarity
            cursor.execute("""
                SELECT AVG(similarity)
                FROM backlinks
                WHERE similarity >= ?
            """, (self.similarity_threshold,))
            avg_similarity = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                'total_backlinks': total_backlinks,
                'files_with_backlinks': files_with_backlinks,
                'average_similarity': round(avg_similarity, 3),
                'similarity_threshold': self.similarity_threshold
            }
            
        except Exception as e:
            logger.error(f"Failed to get backlink stats: {e}")
            return {}
