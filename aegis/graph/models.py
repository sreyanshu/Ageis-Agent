"""
Aegis Project Graph Data Models
Defines strongly typed graph nodes, edges, query parameters, and traversal results.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field

from aegis.indexer.base import SymbolType, RelationType, ConfidenceLevel, Provenance


class GraphNode(BaseModel):
    """A discrete software entity vertex in the project intelligence graph."""
    id: str                                  # E.g. "python:app.services.UserService.get_user"
    name: str
    symbol_type: SymbolType
    language: str
    file_path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    signature: Optional[str] = None
    content_hash: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A directed semantic relationship between two graph nodes."""
    source_id: str
    relation: RelationType
    target_id: str
    confidence: ConfidenceLevel = ConfidenceLevel.DIRECT
    provenance: Provenance
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TraversalPath(BaseModel):
    """Represents a path of nodes and edges discovered during graph traversal."""
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    depth: int = 0


class GraphStats(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    nodes_by_type: Dict[str, int] = Field(default_factory=dict)
    edges_by_relation: Dict[str, int] = Field(default_factory=dict)
    file_count: int = 0
