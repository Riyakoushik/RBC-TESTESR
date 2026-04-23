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
        """Build knowledge graph from cached data."""
        if not NETWORKX_AVAILABLE:
            logger.error("networkx not available")
            return None

        try:
            self.graph = nx.DiGraph()

            self._add_file_nodes()
            self._add_backlink_edges()
            self._add_tag_relationships()
            self._add_people_relationships()

            logger.info(f"Built graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")

            return self.graph

        except Exception as e:
            logger.error(f"Failed to build graph: {e}")
            return None

    def _add_file_nodes(self):
        """Add file nodes to the graph."""
        try:
            files = self.cache.get_all_files()
            for f in files:
                self.graph.add_node(
                    f['id'],
                    file_path=f['file_path'],
                    title=f['title'] or Path(f['file_path']).stem,
                    created_at=f['created_at'],
                    node_type='file'
                )
        except Exception as e:
            logger.error(f"Failed to add file nodes: {e}")

    def _add_backlink_edges(self):
        """Add backlink edges to the graph."""
        try:
            backlinks = self.cache.get_all_backlinks(min_similarity=0.5)
            for bl in backlinks:
                self.graph.add_edge(
                    bl['source_file_id'],
                    bl['target_file_id'],
                    edge_type='backlink',
                    similarity=bl['similarity'],
                    weight=bl['similarity']
                )
        except Exception as e:
            logger.error(f"Failed to add backlink edges: {e}")

    def _add_tag_relationships(self):
        """Add tag-based relationships to the graph."""
        try:
            tag_files = self.cache.get_all_tags_with_files()

            for tag, file_ids in tag_files.items():
                tag_node_id = f"tag_{tag}"
                self.graph.add_node(
                    tag_node_id,
                    tag=tag,
                    node_type='tag'
                )

                for file_id in file_ids:
                    if self.graph.has_node(file_id):
                        self.graph.add_edge(
                            file_id,
                            tag_node_id,
                            edge_type='tag',
                            weight=0.5
                        )
        except Exception as e:
            logger.error(f"Failed to add tag relationships: {e}")

    def _add_people_relationships(self):
        """Add people-based relationships to the graph."""
        try:
            people_files = self.cache.get_all_people_with_files()

            for person, file_ids in people_files.items():
                person_node_id = f"person_{person}"
                self.graph.add_node(
                    person_node_id,
                    person=person,
                    node_type='person'
                )

                for file_id in file_ids:
                    if self.graph.has_node(file_id):
                        self.graph.add_edge(
                            file_id,
                            person_node_id,
                            edge_type='person',
                            weight=0.5
                        )
        except Exception as e:
            logger.error(f"Failed to add people relationships: {e}")

    def save_graph(self):
        """Save graph to JSON for visualization."""
        if self.graph is None:
            logger.warning("No graph to save")
            return

        try:
            graph_data = {
                'nodes': [],
                'edges': [],
                'stats': self.get_graph_stats()
            }

            for node_id, data in self.graph.nodes(data=True):
                node_info = {'id': str(node_id), **{k: str(v) for k, v in data.items()}}
                graph_data['nodes'].append(node_info)

            for source, target, data in self.graph.edges(data=True):
                edge_info = {
                    'source': str(source),
                    'target': str(target),
                    **{k: str(v) for k, v in data.items()}
                }
                graph_data['edges'].append(edge_info)

            with open(self.graph_path, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Graph saved to {self.graph_path}")

        except Exception as e:
            logger.error(f"Failed to save graph: {e}")

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        if self.graph is None:
            return {}

        file_nodes = [n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'file']
        tag_nodes = [n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'tag']
        person_nodes = [n for n, d in self.graph.nodes(data=True) if d.get('node_type') == 'person']

        return {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'file_nodes': len(file_nodes),
            'tag_nodes': len(tag_nodes),
            'person_nodes': len(person_nodes),
            'density': round(nx.density(self.graph), 4) if self.graph.number_of_nodes() > 0 else 0,
        }

    def get_central_files(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get the most connected files by degree centrality."""
        if self.graph is None or self.graph.number_of_nodes() == 0:
            return []

        try:
            centrality = nx.degree_centrality(self.graph)
            file_nodes = {
                n: c for n, c in centrality.items()
                if self.graph.nodes[n].get('node_type') == 'file'
            }

            sorted_files = sorted(file_nodes.items(), key=lambda x: x[1], reverse=True)[:top_n]

            result = []
            for node_id, score in sorted_files:
                data = self.graph.nodes[node_id]
                result.append({
                    'file_path': data.get('file_path', ''),
                    'title': data.get('title', ''),
                    'centrality': round(score, 4)
                })

            return result

        except Exception as e:
            logger.error(f"Failed to get central files: {e}")
            return []

    def get_graph_json(self) -> Dict[str, Any]:
        """Get graph data as JSON-serializable dict for the web UI."""
        if self.graph is None:
            self.build_graph()

        if self.graph is None:
            return {'nodes': [], 'edges': [], 'stats': {}}

        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                'id': str(node_id),
                'label': data.get('title', data.get('tag', data.get('person', str(node_id)))),
                'type': data.get('node_type', 'unknown'),
            })

        edges = []
        for source, target, data in self.graph.edges(data=True):
            edges.append({
                'source': str(source),
                'target': str(target),
                'type': data.get('edge_type', 'unknown'),
                'weight': float(data.get('weight', 0.5)),
            })

        return {
            'nodes': nodes,
            'edges': edges,
            'stats': self.get_graph_stats()
        }
