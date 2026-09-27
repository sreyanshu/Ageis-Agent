"""
Aegis Graph Traversal Engine
Provides breadth-first and depth-bounded traversal algorithms for finding
downstream blast radius, upstream dependencies, and transitive impact.
"""

from __future__ import annotations
from collections import deque
from typing import Dict, List, Set, Optional, Tuple

from aegis.graph.models import GraphNode, GraphEdge, TraversalPath
from aegis.graph.store import GraphStore
from aegis.indexer.base import RelationType


class GraphTraversal:
    """Performs cycle-safe, depth-bounded traversal across the project graph."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def get_downstream_impact(
        self,
        start_node_ids: List[str],
        max_depth: int = 5,
        allowed_relations: Optional[Set[RelationType]] = None,
    ) -> TraversalPath:
        """
        Traverses downstream: finds all nodes that call, import, depend on, test, or render the starting nodes.
        (Follows incoming edges where target is in current frontier, or EXPOSES_API / TESTS outgoing edges).
        """
        visited_nodes: Set[str] = set(start_node_ids)
        result_nodes: List[GraphNode] = []
        result_edges: List[GraphEdge] = []

        # Populate initial nodes
        queue: deque[Tuple[str, int]] = deque([(nid, 0) for nid in start_node_ids])
        for nid in start_node_ids:
            node = self.store.get_node(nid)
            if node:
                result_nodes.append(node)

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            # 1. Incoming edges (callers, importers, dependents)
            incoming = self.store.get_incoming_edges(current_id)
            for edge in incoming:
                if allowed_relations and edge.relation not in allowed_relations:
                    continue
                result_edges.append(edge)
                neighbor_id = edge.source_id
                if neighbor_id not in visited_nodes:
                    visited_nodes.add(neighbor_id)
                    neighbor_node = self.store.get_node(neighbor_id)
                    if neighbor_node:
                        result_nodes.append(neighbor_node)
                    queue.append((neighbor_id, depth + 1))

            # 2. Outgoing API / UI / DB relationships
            outgoing = self.store.get_outgoing_edges(current_id)
            for edge in outgoing:
                if edge.relation in (RelationType.EXPOSES_API, RelationType.RENDERS, RelationType.TESTS, RelationType.ACCESSES_DATABASE):
                    result_edges.append(edge)
                    neighbor_id = edge.target_id
                    if neighbor_id not in visited_nodes:
                        visited_nodes.add(neighbor_id)
                        neighbor_node = self.store.get_node(neighbor_id)
                        if neighbor_node:
                            result_nodes.append(neighbor_node)
                        queue.append((neighbor_id, depth + 1))

        return TraversalPath(
            nodes=result_nodes,
            edges=result_edges,
            depth=max_depth,
        )

    def get_upstream_dependencies(
        self,
        start_node_ids: List[str],
        max_depth: int = 5,
        allowed_relations: Optional[Set[RelationType]] = None,
    ) -> TraversalPath:
        """
        Traverses upstream: finds all nodes that the starting nodes depend on, call, import, or inherit from.
        """
        visited_nodes: Set[str] = set(start_node_ids)
        result_nodes: List[GraphNode] = []
        result_edges: List[GraphEdge] = []

        queue: deque[Tuple[str, int]] = deque([(nid, 0) for nid in start_node_ids])
        for nid in start_node_ids:
            node = self.store.get_node(nid)
            if node:
                result_nodes.append(node)

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            outgoing = self.store.get_outgoing_edges(current_id)
            for edge in outgoing:
                if allowed_relations and edge.relation not in allowed_relations:
                    continue
                result_edges.append(edge)
                neighbor_id = edge.target_id
                if neighbor_id not in visited_nodes:
                    visited_nodes.add(neighbor_id)
                    neighbor_node = self.store.get_node(neighbor_id)
                    if neighbor_node:
                        result_nodes.append(neighbor_node)
                    queue.append((neighbor_id, depth + 1))

        return TraversalPath(
            nodes=result_nodes,
            edges=result_edges,
            depth=max_depth,
        )
