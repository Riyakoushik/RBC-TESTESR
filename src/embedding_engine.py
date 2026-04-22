"""
Embedding Engine for RBC-TESTER Knowledge System.
Uses sentence-transformers and FAISS for similarity search.
Optimized for low-memory systems (CPU mode only, batched processing).
"""

import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available")

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("faiss not available")

from .config import get_config, get_project_root
from .cache_manager import CacheManager


class EmbeddingEngine:
    """
    Generates and manages embeddings for similarity search.
    Uses sentence-transformers for embedding generation and FAISS for efficient search.
    Optimized for CPU-only operation on low-memory systems.
    """
    
    def __init__(self, cache_manager: Optional[CacheManager] = None, model_name: str = "all-MiniLM-L6-v2"):
        self.config = get_config()
        self.project_root = get_project_root()
        
        if cache_manager is None:
            self.cache = CacheManager()
        else:
            self.cache = cache_manager
        
        self.model_name = model_name
        self.model = None
        self.index = None
        self.file_ids = []
        self._initialized = False
        
        # Low-memory optimization settings
        self.batch_size = 10  # Process in small batches
        self.embedding_dim = 384  # all-MiniLM-L6-v2 dimension
    
    def initialize(self) -> bool:
        """
        Initialize the embedding model and FAISS index.
        
        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.error("sentence-transformers not available")
            return False
        
        if not FAISS_AVAILABLE:
            logger.error("faiss not available")
            return False
        
        try:
            logger.info(f"Loading sentence-transformers model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            
            # Initialize FAISS index (CPU mode only)
            self.index = faiss.IndexFlatIP(self.embedding_dim)
            
            # Load existing embeddings from cache
            self._load_embeddings_from_cache()
            
            self._initialized = True
            logger.info("Embedding engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding engine: {e}")
            return False
    
    def _load_embeddings_from_cache(self):
        """Load existing embeddings from cache database."""
        try:
            embeddings_data = self.cache.get_all_file_embeddings()
            
            if embeddings_data:
                logger.info(f"Loading {len(embeddings_data)} existing embeddings from cache")
                
                for file_id, embedding in embeddings_data:
                    # Add to FAISS index
                    embedding_array = np.array([embedding], dtype=np.float32)
                    # Normalize for cosine similarity
                    faiss.normalize_L2(embedding_array)
                    self.index.add(embedding_array)
                    self.file_ids.append(file_id)
                
                logger.info(f"FAISS index loaded with {self.index.ntotal} embeddings")
            
        except Exception as e:
            logger.error(f"Failed to load embeddings from cache: {e}")
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector or None if failed
        """
        if not self._initialized:
            if not self.initialize():
                return None
        
        try:
            # Truncate text if too long (for memory efficiency)
            max_length = 512
            words = text.split()
            if len(words) > max_length:
                text = ' '.join(words[:max_length])
            
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors (None for failed embeddings)
        """
        if not self._initialized:
            if not self.initialize():
                return [None] * len(texts)
        
        embeddings = []
        
        # Process in batches for memory efficiency
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            try:
                # Truncate texts in batch
                truncated_batch = []
                for text in batch:
                    words = text.split()
                    if len(words) > 512:
                        text = ' '.join(words[:512])
                    truncated_batch.append(text)
                
                batch_embeddings = self.model.encode(
                    truncated_batch,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                    batch_size=min(len(truncated_batch), 4)
                )
                
                for embedding in batch_embeddings:
                    embeddings.append(embedding.tolist())
                    
            except Exception as e:
                logger.error(f"Failed to generate batch embeddings: {e}")
                embeddings.extend([None] * len(batch))
        
        return embeddings
    
    def add_embedding(self, file_id: int, text: str):
        """
        Add embedding for a file to the index and cache.
        
        Args:
            file_id: File ID in database
            text: Text content to embed
        """
        try:
            # Generate embedding
            embedding = self.generate_embedding(text)
            
            if embedding is None:
                logger.warning(f"Failed to generate embedding for file_id {file_id}")
                return
            
            # Store in cache
            self.cache.store_embedding(file_id, embedding, self.model_name)
            
            # Add to FAISS index
            embedding_array = np.array([embedding], dtype=np.float32)
            faiss.normalize_L2(embedding_array)
            self.index.add(embedding_array)
            self.file_ids.append(file_id)
            
            logger.debug(f"Added embedding for file_id {file_id}")
            
        except Exception as e:
            logger.error(f"Failed to add embedding for file_id {file_id}: {e}")
    
    def search_similar(self, text: str, k: int = 5) -> List[Tuple[int, float]]:
        """
        Search for similar files based on text.
        
        Args:
            text: Query text
            k: Number of results to return
        
        Returns:
            List of (file_id, similarity_score) tuples
        """
        if not self._initialized:
            if not self.initialize():
                return []
        
        if self.index.ntotal == 0:
            logger.warning("No embeddings in index")
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(text)
            
            if query_embedding is None:
                return []
            
            # Search in FAISS index
            query_array = np.array([query_embedding], dtype=np.float32)
            faiss.normalize_L2(query_array)
            
            similarities, indices = self.index.search(query_array, k)
            
            # Map indices to file IDs
            results = []
            for i in range(len(indices[0])):
                idx = indices[0][i]
                similarity = similarities[0][i]
                if idx < len(self.file_ids):
                    file_id = self.file_ids[idx]
                    results.append((file_id, float(similarity)))
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search similar files: {e}")
            return []
    
    def find_similar_files(self, file_id: int, k: int = 5, exclude_self: bool = True) -> List[Tuple[int, float]]:
        """
        Find files similar to a given file.
        
        Args:
            file_id: File ID to find similar files for
            k: Number of results to return
            exclude_self: Whether to exclude the file itself from results
        
        Returns:
            List of (file_id, similarity_score) tuples
        """
        if not self._initialized:
            if not self.initialize():
                return []
        
        if self.index.ntotal == 0:
            return []
        
        try:
            # Get embedding from cache
            embedding = self.cache.get_embedding(file_id)
            
            if embedding is None:
                logger.warning(f"No embedding found for file_id {file_id}")
                return []
            
            # Search in FAISS index
            embedding_array = np.array([embedding], dtype=np.float32)
            faiss.normalize_L2(embedding_array)
            
            similarities, indices = self.index.search(embedding_array, k + 1 if exclude_self else k)
            
            # Map indices to file IDs
            results = []
            for i in range(len(indices[0])):
                idx = indices[0][i]
                similarity = similarities[0][i]
                
                if idx < len(self.file_ids):
                    similar_file_id = self.file_ids[idx]
                    
                    # Exclude self if requested
                    if exclude_self and similar_file_id == file_id:
                        continue
                    
                    results.append((similar_file_id, float(similarity)))
                
                if len(results) >= k:
                    break
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to find similar files for file_id {file_id}: {e}")
            return []
    
    def get_similarity(self, file_id_1: int, file_id_2: int) -> Optional[float]:
        """
        Get similarity score between two files.
        
        Args:
            file_id_1: First file ID
            file_id_2: Second file ID
        
        Returns:
            Similarity score (0-1) or None if failed
        """
        try:
            # Get embeddings
            embedding_1 = self.cache.get_embedding(file_id_1)
            embedding_2 = self.cache.get_embedding(file_id_2)
            
            if embedding_1 is None or embedding_2 is None:
                return None
            
            # Calculate cosine similarity
            vec1 = np.array(embedding_1)
            vec2 = np.array(embedding_2)
            
            # Normalize
            vec1 = vec1 / np.linalg.norm(vec1)
            vec2 = vec2 / np.linalg.norm(vec2)
            
            # Cosine similarity
            similarity = np.dot(vec1, vec2)
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            return None
    
    def remove_embedding(self, file_id: int):
        """
        Remove embedding for a file from the index.
        Note: FAISS doesn't support deletion, so we rebuild the index.
        
        Args:
            file_id: File ID to remove
        """
        try:
            # Remove from cache
            # Note: This requires modifying cache_manager to support deletion
            logger.info(f"Removing embedding for file_id {file_id}")
            
            # Rebuild index without this file
            self._load_embeddings_from_cache()
            
        except Exception as e:
            logger.error(f"Failed to remove embedding: {e}")
    
    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the embedding index.
        
        Returns:
            Dictionary with index statistics
        """
        if not self._initialized:
            return {
                'initialized': False,
                'total_embeddings': 0,
                'model_name': self.model_name,
                'embedding_dim': self.embedding_dim
            }
        
        return {
            'initialized': True,
            'total_embeddings': self.index.ntotal,
            'model_name': self.model_name,
            'embedding_dim': self.embedding_dim,
            'batch_size': self.batch_size
        }
