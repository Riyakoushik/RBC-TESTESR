"""
Graph Builder for RBC-TESTER Knowledge System.
Builds knowledge graph using NetworkX for visualization and analysis.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logger.warning("networkx not available")

from .config import get_config, get_project_root
from .cache_manager import CacheManager


class GraphBuilder:
    """
    Builds and manages knowledge graph using NetworkX.
    Creates graph from backlinks, tags, people, and other relationships.
    """
    
    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.config = get_config()
        self.project_root = get_project_root()
        
        if cache_manager is None:
            self.cache = CacheManager()
        else:
            self.cache = cache_manager
        
        self.graph = None
        self.graph_path = self.project_root / "knowledge" / "graph.json"
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
    
    def build_graph(self) -> Optional[Any]:
        """
        Build knowledge graph from cached data.
        
        Returns:
            NetworkX graph object or None if networkx not available
        """
        if not NETWORKX_AVAILABLE:
            logger.error("networkx not available")
            return None
        
        try:
            self.graph = nx.DiGraph()
            
            # Add nodes (files)
            self._add_file_nodes()
            
            # Add edges (backlinks)
            self._add_backlink_edges()
            
            # Add tag relationships
            self._add_tag_relationships()
            
            # Add people relationships
            self._add_people_relationships()
            
            logger.info(f"Built graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
            
            return self.graph
            
        except Exception as e:
            logger.error(f"Failed to build graph: {e}")
            return None
    
    def _add_file_nodes(self):
        """Add file nodes to the graph."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.cache.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, file_path, title, created_at FROM files")
            results = cursor.fetchall()
            conn.close()
            
            for file_id, file_path, title, created_at in results:
                self.graph.add_node(
                    file_id,
                    file_path=file_path,
                    title=title or Path(file_path).stem,
                    created_at=created_at,
                    node_type='file'
                )
            
        except Exception as e:
            logger.error(f"Failed to add file nodes: {e}")
    
    def _add_backlink_edges(self):
        """Add backlink edges to the graph."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.cache.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT source_file_id, target_file_id, similarity
                FROM backlinks
                WHERE similarity >= 0.5
            """)
            results = cursor.fetchall()
            conn.close()
            
            for source_id, target_id, similarity in results:
                self.graph.add_edge(
                    source_id,
                    target_id,
                    edge_type='backlink',
                    similarity=similarity,
                    weight=similarity
                )
            
        except Exception as e:
            logger.error(f"Failed to add backlink edges: {e}")
    
    def _add_tag_relationships(self):
        """Add tag-based relationships to the graph."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.cache.db_path)
            cursor = conn.cursor()
            
            # Get all tags and their files
            cursor.execute("""
                SELECT t.tag, f.id
                FROM tags t
                JOIN files f ON t.file_id = f.id
            """)
            results = cursor.fetchall()
            conn.close()
            
            # Group files by tag
            tag_files = {}
            for tag, file_id in results:
                if tag not in tag_files:
                    tag_files[tag] = []
                tag_files[tag].append(file_id)
            
            # Add tag nodes and connect files to tags
            for tag, file_ids in tag_files.items():
                tag_node_id = f"tag_{tag}"
                self.graph.add_node(
                    tag_node_id,
                    tag=tag,
                    node_type='tag'
                )
                
                for file_id in file_ids:
                    self.graph.add_edge(
                        file_id,
                        tag_node_id,
                        edge_type='has_tag'
                    )
            
        except Exception as e:
            logger.error(f"Failed to add tag relationships: {e}")
    
    def _add_people_relationships(self):
        """Add people-based relationships to the graph."""
        try:
            import sqlite3
            conn = sqlite3.connect(self.cache.db_path)
            cursor = conn.cursor()
            
            # Get all people and their files
            cursor.execute("""
                SELECT p.person_name, f.id
                FROM people p
                JOIN files f ON p.file_id = f.id
            """)
            results = cursor.fetchall()
            conn.close()
            
            # Group files by person
            person_files = {}
            for person, file_id in results:
                if person not in person_files:
                    person_files[person] = []
                person_files[person].append(file_id)
            
            # Add person nodes and connect files to people
            for person, file_ids in person_files.items():
                person_node_id = f"person_{person}"
                self.graph.add_node(
                    person_node_id,
                    person_name=person,
                    node_type='person'
                )
                
                for file_id in file_ids:
                    self.graph.add_edge(
                        file_id,
                        person_node_id,
                        edge_type='mentions_person'
                    )
            
        except Exception as e:
            logger.error(f"Failed to add people relationships: {e}")
    
    def save_graph(self):
        """Save graph to JSON file."""
        if self.graph is None:
            logger.warning("No graph to save")
            return
        
        try:
            # Convert to JSON-serializable format
            graph_data = nx.node_link_data(self.graph)
            
            with open(self.graph_path, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Graph saved to {self.graph_path}")
            
        except Exception as e:
            logger.error(f"Failed to save graph: {e}")
    
    def load_graph(self) -> Optional[Any]:
        """Load graph from JSON file."""
        if not NETWORKX_AVAILABLE:
            return None
        
        try:
            if self.graph_path.exists():
                with open(self.graph_path, 'r', encoding='utf-8') as f:
                    graph_data = json.load(f)
                
                self.graph = nx.node_link_graph(graph_data)
                logger.info(f"Graph loaded from {self.graph_path}")
                return self.graph
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to load graph: {e}")
            return None
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge graph.
        
        Returns:
            Dictionary with graph statistics
        """
        if self.graph is None:
            if not self.build_graph():
                return {}
        
        try:
            return {
                'total_nodes': self.graph.number_of_nodes(),
                'total_edges': self.graph.number_of_edges(),
                'file_nodes': len([n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'file']),
                'tag_nodes': len([n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'tag']),
                'person_nodes': len([n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'person']),
                'density': nx.density(self.graph) if self.graph.number_of_nodes() > 1 else 0,
                'is_connected': nx.is_connected(self.graph.to_undirected()) if self.graph.number_of_nodes() > 0 else False
            }
            
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {}
    
    def get_related_files(self, file_path: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        Get files related to a given file through the graph.
        
        Args:
            file_path: Path to the file
            max_depth: Maximum depth of traversal
        
        Returns:
            List of related file dictionaries
        """
        if self.graph is None:
            if not self.build_graph():
                return []
        
        try:
            # Find file node
            file_node = None
            for node, data in self.graph.nodes(data=True):
                if data.get('file_path') == file_path:
                    file_node = node
                    break
            
            if file_node is None:
                return []
            
            # Get neighbors within max_depth
            related = []
            visited = set()
            
            def traverse(current_node, depth):
                if depth > max_depth or current_node in visited:
                    return
                
                visited.add(current_node)
                
                for neighbor in self.graph.neighbors(current_node):
                    neighbor_data = self.graph.nodes[neighbor]
                    
                    if neighbor_data.get('node_type') == 'file' and neighbor != file_node:
                        edge_data = self.graph.get_edge_data(current_node, neighbor)
                        related.append({
                            'file_path': neighbor_data.get('file_path'),
                            'title': neighbor_data.get('title'),
                            'relationship': edge_data.get('edge_type'),
                            'depth': depth
                        })
                    
                    traverse(neighbor, depth + 1)
            
            traverse(file_node, 0)
            
            return related
            
        except Exception as e:
            logger.error(f"Failed to get related files: {e}")
            return []
