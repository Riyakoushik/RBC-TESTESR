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
                    file_info = self.cache.get_file_info_by_id(similar_file_id)

                    if file_info:
                        backlinks.append({
                            'file_path': file_info['file_path'],
                            'title': file_info['title'] or Path(file_info['file_path']).stem,
                            'similarity': similarity
                        })

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
        """Clear all backlinks from cache via CacheManager."""
        self.cache.clear_all_backlinks()
        logger.info("Cleared all backlinks")
    
    def _save_backlinks(self):
        """Save backlinks to JSON file for easy access."""
        try:
            all_backlinks = self.cache.get_all_backlinks(min_similarity=self.similarity_threshold)

            # Organize by source file
            backlinks_dict: Dict[str, List[Dict[str, Any]]] = {}
            for bl in all_backlinks:
                source_info = self.cache.get_file_info_by_id(bl['source_file_id'])
                target_info = self.cache.get_file_info_by_id(bl['target_file_id'])

                if source_info and target_info:
                    source_path = source_info['file_path']
                    if source_path not in backlinks_dict:
                        backlinks_dict[source_path] = []
                    backlinks_dict[source_path].append({
                        'file_path': target_info['file_path'],
                        'title': target_info['title'] or Path(target_info['file_path']).stem,
                        'similarity': bl['similarity']
                    })

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
        """Get statistics about the backlink network."""
        try:
            all_backlinks = self.cache.get_all_backlinks(min_similarity=self.similarity_threshold)

            total_backlinks = len(all_backlinks)
            source_ids = set(bl['source_file_id'] for bl in all_backlinks)
            files_with_backlinks = len(source_ids)
            avg_similarity = (
                sum(bl['similarity'] for bl in all_backlinks) / total_backlinks
                if total_backlinks > 0 else 0
            )

            return {
                'total_backlinks': total_backlinks,
                'files_with_backlinks': files_with_backlinks,
                'average_similarity': round(avg_similarity, 3),
                'similarity_threshold': self.similarity_threshold
            }

        except Exception as e:
            logger.error(f"Failed to get backlink stats: {e}")
            return {}
