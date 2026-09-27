"""
Aegis High-Level Project Intelligence Graph
Provides unified queries for dependency impact, API impact, UI impact, and test impact.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from aegis.graph.models import GraphNode, GraphEdge, GraphStats, TraversalPath
from aegis.graph.store import GraphStore, SQLiteGraphStore
from aegis.graph.traversal import GraphTraversal
from aegis.indexer.base import SymbolType, RelationType, ConfidenceLevel, Provenance
from aegis.indexer.symbol_index import SymbolIndex


class ProjectGraph:
    """High-level semantic graph facade for the workspace."""

    def __init__(self, workspace_root: Path | str, store: Optional[GraphStore] = None) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        db_path = self.workspace_root / ".aegis" / "graph.db"
        self.store = store or SQLiteGraphStore(db_path)
        self.traversal = GraphTraversal(self.store)

    def sync_from_symbol_index(self, symbol_index: SymbolIndex) -> GraphStats:
        """Synchronizes symbol index symbols and relationships into the persistent graph."""
        nodes: List[GraphNode] = []
        for sym in symbol_index.symbols.values():
            nodes.append(
                GraphNode(
                    id=sym.id,
                    name=sym.name,
                    symbol_type=sym.symbol_type,
                    language=sym.language,
                    file_path=sym.file_path,
                    line_start=sym.line_start,
                    line_end=sym.line_end,
                    signature=sym.signature,
                    content_hash=sym.content_hash,
                    metadata=sym.metadata,
                )
            )
        self.store.upsert_nodes(nodes)

        edges: List[GraphEdge] = []
        for rel in symbol_index.relationships:
            edges.append(
                GraphEdge(
                    source_id=rel.source_id,
                    relation=rel.relation,
                    target_id=rel.target_id,
                    confidence=rel.provenance.confidence,
                    provenance=rel.provenance,
                    metadata=rel.metadata,
                )
            )
        self.store.add_edges(edges)

        return self.store.get_stats()

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self.store.get_node(node_id)

    def get_nodes_by_file(self, file_path: str) -> List[GraphNode]:
        return self.store.get_nodes_by_file(file_path)

    def get_nodes_by_type(self, symbol_type: SymbolType) -> List[GraphNode]:
        return self.store.get_nodes_by_type(symbol_type)

    def get_affected_downstream(self, changed_symbol_ids: List[str], max_depth: int = 5) -> TraversalPath:
        """Finds all downstream nodes impacted by changes to start symbols."""
        return self.traversal.get_downstream_impact(changed_symbol_ids, max_depth=max_depth)

    def get_affected_apis(self, changed_symbol_ids: List[str]) -> List[GraphNode]:
        """Finds all HTTP/RPC route endpoints affected by the given symbol changes."""
        path = self.get_affected_downstream(changed_symbol_ids, max_depth=6)
        return [n for n in path.nodes if n.symbol_type == SymbolType.ROUTE or n.id.startswith("api:")]

    def get_affected_ui(self, changed_symbol_ids: List[str]) -> List[GraphNode]:
        """Finds all frontend UI components affected by the given symbol changes."""
        path = self.get_affected_downstream(changed_symbol_ids, max_depth=6)
        return [n for n in path.nodes if n.symbol_type == SymbolType.COMPONENT]

    def get_affected_tests(self, changed_symbol_ids: List[str]) -> List[GraphNode]:
        """Finds all test suites and test functions that exercise the changed symbols."""
        path = self.get_affected_downstream(changed_symbol_ids, max_depth=6)
        return [n for n in path.nodes if n.symbol_type == SymbolType.TEST or "test" in n.file_path.lower()]

    def get_affected_databases(self, changed_symbol_ids: List[str]) -> List[GraphNode]:
        """Finds database models or tables affected by the changes."""
        path = self.get_affected_downstream(changed_symbol_ids, max_depth=6)
        return [n for n in path.nodes if n.symbol_type == SymbolType.DB_MODEL or n.id.startswith("db_table:")]

    def get_stats(self) -> GraphStats:
        return self.store.get_stats()
