"""
Aegis Graph Storage Engine
Provides an abstract storage interface and a high-performance SQLite graph backend
for storing and querying graph nodes and edges.
"""

from __future__ import annotations
import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from aegis.graph.models import GraphNode, GraphEdge, GraphStats
from aegis.indexer.base import SymbolType, RelationType, ConfidenceLevel, Provenance


class GraphStore(ABC):
    """Abstract interface for project intelligence graph persistence."""

    @abstractmethod
    def upsert_node(self, node: GraphNode) -> None:
        pass

    @abstractmethod
    def upsert_nodes(self, nodes: List[GraphNode]) -> None:
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        pass

    @abstractmethod
    def get_nodes_by_file(self, file_path: str) -> List[GraphNode]:
        pass

    @abstractmethod
    def get_nodes_by_type(self, symbol_type: SymbolType) -> List[GraphNode]:
        pass

    @abstractmethod
    def add_edge(self, edge: GraphEdge) -> None:
        pass

    @abstractmethod
    def add_edges(self, edges: List[GraphEdge]) -> None:
        pass

    @abstractmethod
    def get_outgoing_edges(self, source_id: str, relation: Optional[RelationType] = None) -> List[GraphEdge]:
        pass

    @abstractmethod
    def get_incoming_edges(self, target_id: str, relation: Optional[RelationType] = None) -> List[GraphEdge]:
        pass

    @abstractmethod
    def remove_file(self, file_path: str) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass

    @abstractmethod
    def get_stats(self) -> GraphStats:
        pass


class SQLiteGraphStore(GraphStore):
    """Local SQLite-backed graph database with indexed source/target traversal."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    symbol_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_start INTEGER,
                    line_end INTEGER,
                    signature TEXT,
                    content_hash TEXT,
                    metadata JSON
                );

                CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file_path);
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(symbol_type);

                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    provenance JSON NOT NULL,
                    metadata JSON,
                    UNIQUE(source_id, relation, target_id)
                );

                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
                CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(relation);
                CREATE INDEX IF NOT EXISTS idx_edges_file ON edges(file_path);
                """
            )

    def upsert_node(self, node: GraphNode) -> None:
        self.upsert_nodes([node])

    def upsert_nodes(self, nodes: List[GraphNode]) -> None:
        if not nodes:
            return
        rows = [
            (
                n.id,
                n.name,
                n.symbol_type.value,
                n.language,
                n.file_path,
                n.line_start,
                n.line_end,
                n.signature,
                n.content_hash,
                json.dumps(n.metadata),
            )
            for n in nodes
        ]
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO nodes (id, name, symbol_type, language, file_path, line_start, line_end, signature, content_hash, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    symbol_type=excluded.symbol_type,
                    language=excluded.language,
                    file_path=excluded.file_path,
                    line_start=excluded.line_start,
                    line_end=excluded.line_end,
                    signature=excluded.signature,
                    content_hash=excluded.content_hash,
                    metadata=excluded.metadata
                """,
                rows,
            )

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_node(row)

    def get_nodes_by_file(self, file_path: str) -> List[GraphNode]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM nodes WHERE file_path = ?", (file_path,))
            return [self._row_to_node(r) for r in cur.fetchall()]

    def get_nodes_by_type(self, symbol_type: SymbolType) -> List[GraphNode]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM nodes WHERE symbol_type = ?", (symbol_type.value,))
            return [self._row_to_node(r) for r in cur.fetchall()]

    def add_edge(self, edge: GraphEdge) -> None:
        self.add_edges([edge])

    def add_edges(self, edges: List[GraphEdge]) -> None:
        if not edges:
            return
        rows = [
            (
                e.source_id,
                e.relation.value,
                e.target_id,
                e.confidence.value,
                e.provenance.file_path,
                json.dumps(e.provenance.model_dump()),
                json.dumps(e.metadata),
            )
            for e in edges
        ]
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO edges (source_id, relation, target_id, confidence, file_path, provenance, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, relation, target_id) DO UPDATE SET
                    confidence=excluded.confidence,
                    file_path=excluded.file_path,
                    provenance=excluded.provenance,
                    metadata=excluded.metadata
                """,
                rows,
            )

    def get_outgoing_edges(self, source_id: str, relation: Optional[RelationType] = None) -> List[GraphEdge]:
        query = "SELECT * FROM edges WHERE source_id = ?"
        params: List[Any] = [source_id]
        if relation:
            query += " AND relation = ?"
            params.append(relation.value)

        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            return [self._row_to_edge(r) for r in cur.fetchall()]

    def get_incoming_edges(self, target_id: str, relation: Optional[RelationType] = None) -> List[GraphEdge]:
        query = "SELECT * FROM edges WHERE target_id = ?"
        params: List[Any] = [target_id]
        if relation:
            query += " AND relation = ?"
            params.append(relation.value)

        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            return [self._row_to_edge(r) for r in cur.fetchall()]

    def remove_file(self, file_path: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM nodes WHERE file_path = ?", (file_path,))
            conn.execute("DELETE FROM edges WHERE file_path = ?", (file_path,))

    def clear(self) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM nodes")
            conn.execute("DELETE FROM edges")

    def get_stats(self) -> GraphStats:
        with self._get_connection() as conn:
            cur_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            cur_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            cur_files = conn.execute("SELECT COUNT(DISTINCT file_path) FROM nodes").fetchone()[0]

            types_cur = conn.execute("SELECT symbol_type, COUNT(*) FROM nodes GROUP BY symbol_type")
            nodes_by_type = {r[0]: r[1] for r in types_cur.fetchall()}

            rel_cur = conn.execute("SELECT relation, COUNT(*) FROM edges GROUP BY relation")
            edges_by_rel = {r[0]: r[1] for r in rel_cur.fetchall()}

            return GraphStats(
                total_nodes=cur_nodes,
                total_edges=cur_edges,
                nodes_by_type=nodes_by_type,
                edges_by_relation=edges_by_rel,
                file_count=cur_files,
            )

    def _row_to_node(self, r: sqlite3.Row) -> GraphNode:
        return GraphNode(
            id=r["id"],
            name=r["name"],
            symbol_type=SymbolType(r["symbol_type"]),
            language=r["language"],
            file_path=r["file_path"],
            line_start=r["line_start"],
            line_end=r["line_end"],
            signature=r["signature"],
            content_hash=r["content_hash"] or "",
            metadata=json.loads(r["metadata"]) if r["metadata"] else {},
        )

    def _row_to_edge(self, r: sqlite3.Row) -> GraphEdge:
        prov_data = json.loads(r["provenance"]) if r["provenance"] else {}
        return GraphEdge(
            source_id=r["source_id"],
            relation=RelationType(r["relation"]),
            target_id=r["target_id"],
            confidence=ConfidenceLevel(r["confidence"]),
            provenance=Provenance(**prov_data),
            metadata=json.loads(r["metadata"]) if r["metadata"] else {},
        )
