"""
Aegis Change Impact Analysis Engine
Calculates AST symbol diffs, traverses the project graph for downstream blast radius,
and identifies affected APIs, UI, databases, and relevant test targets.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from aegis.core.events import generate_id
from aegis.graph.models import GraphNode
from aegis.graph.project_graph import ProjectGraph
from aegis.impact.models import (
    ImpactReport,
    ChangedSymbol,
    SymbolChangeType,
    AffectedEntity,
    BlastRadius,
)
from aegis.indexer.base import Symbol, SymbolType, ConfidenceLevel
from aegis.indexer.registry import IndexerRegistry, default_indexer_registry
from aegis.indexer.symbol_index import SymbolIndex
from aegis.storage.hashing import ContentHasher, IncrementalChangeEngine, ChangeSet


class ChangeImpactEngine:
    """Computes exact symbol modifications and traverses the dependency graph for downstream impact."""

    def __init__(
        self,
        workspace_root: Path | str,
        graph: ProjectGraph,
        symbol_index: SymbolIndex,
        change_engine: IncrementalChangeEngine,
        registry: Optional[IndexerRegistry] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.graph = graph
        self.symbol_index = symbol_index
        self.change_engine = change_engine
        self.registry = registry or default_indexer_registry

    def analyze_impact(self, max_depth: int = 5) -> ImpactReport:
        """
        Executes full change impact analysis:
        1. Identifies added, modified, deleted files.
        2. Computes fine-grained symbol AST differences.
        3. Traverses project graph to determine affected APIs, UI, DB, and Tests.
        4. Calculates direct and indirect blast radius.
        """
        changes: ChangeSet = self.change_engine.detect_changes()
        tree_hash = changes.tree_hash

        changed_symbols: List[ChangedSymbol] = []
        changed_symbol_ids: List[str] = []

        # 1. Inspect added and modified files
        for fpath in changes.added_files:
            new_indexed = self.registry.index_file(self.workspace_root, fpath)
            if new_indexed:
                for sym in new_indexed.symbols:
                    changed_symbols.append(
                        ChangedSymbol(
                            symbol_id=sym.id,
                            name=sym.name,
                            change_type=SymbolChangeType.ADDED,
                            symbol_type=sym.symbol_type.value,
                            file_path=fpath,
                            line_start=sym.line_start,
                            signature=sym.signature,
                        )
                    )
                    changed_symbol_ids.append(sym.id)

        for fpath in changes.modified_files:
            old_meta = self.symbol_index.files_meta.get(fpath)
            new_indexed = self.registry.index_file(self.workspace_root, fpath)

            if not new_indexed:
                continue

            if old_meta and old_meta.ast_hash == new_indexed.ast_hash:
                # AST is identical (e.g. comment or whitespace only change)
                changed_symbols.append(
                    ChangedSymbol(
                        symbol_id=f"file:{fpath}",
                        name=Path(fpath).name,
                        change_type=SymbolChangeType.COMMENTS_ONLY,
                        symbol_type="file",
                        file_path=fpath,
                    )
                )
                continue

            # Compare symbols in this file
            old_syms = {
                s.id: s
                for s in self.symbol_index.symbols.values()
                if s.file_path == fpath
            }
            new_syms = {s.id: s for s in new_indexed.symbols}

            for sid, sym in new_syms.items():
                if sid not in old_syms:
                    changed_symbols.append(
                        ChangedSymbol(
                            symbol_id=sym.id,
                            name=sym.name,
                            change_type=SymbolChangeType.ADDED,
                            symbol_type=sym.symbol_type.value,
                            file_path=fpath,
                            line_start=sym.line_start,
                            signature=sym.signature,
                        )
                    )
                    changed_symbol_ids.append(sym.id)
                elif old_syms[sid].content_hash != sym.content_hash:
                    # Check if signature changed vs body changed
                    if old_syms[sid].signature != sym.signature:
                        ch_type = SymbolChangeType.SIGNATURE_CHANGED
                    else:
                        ch_type = SymbolChangeType.BODY_CHANGED

                    changed_symbols.append(
                        ChangedSymbol(
                            symbol_id=sym.id,
                            name=sym.name,
                            change_type=ch_type,
                            symbol_type=sym.symbol_type.value,
                            file_path=fpath,
                            line_start=sym.line_start,
                            signature=sym.signature,
                            previous_signature=old_syms[sid].signature,
                        )
                    )
                    changed_symbol_ids.append(sym.id)

            for sid, old_sym in old_syms.items():
                if sid not in new_syms:
                    changed_symbols.append(
                        ChangedSymbol(
                            symbol_id=old_sym.id,
                            name=old_sym.name,
                            change_type=SymbolChangeType.DELETED,
                            symbol_type=old_sym.symbol_type.value,
                            file_path=fpath,
                            signature=old_sym.signature,
                        )
                    )
                    changed_symbol_ids.append(old_sym.id)

        # 2. Inspect deleted files
        for fpath in changes.deleted_files:
            old_syms = [
                s for s in self.symbol_index.symbols.values() if s.file_path == fpath
            ]
            for s in old_syms:
                changed_symbols.append(
                    ChangedSymbol(
                        symbol_id=s.id,
                        name=s.name,
                        change_type=SymbolChangeType.DELETED,
                        symbol_type=s.symbol_type.value,
                        file_path=fpath,
                        signature=s.signature,
                    )
                )
                changed_symbol_ids.append(s.id)

        # 3. Traversal for downstream impact if changes detected
        affected_components: List[AffectedEntity] = []
        affected_apis: List[AffectedEntity] = []
        affected_ui: List[AffectedEntity] = []
        affected_tests: List[AffectedEntity] = []
        affected_databases: List[AffectedEntity] = []

        direct_set: Set[str] = set()
        indirect_set: Set[str] = set()

        if changed_symbol_ids:
            traversal_path = self.graph.get_affected_downstream(changed_symbol_ids, max_depth=max_depth)
            
            # Map start symbols to identify direct vs indirect
            start_ids_set = set(changed_symbol_ids)

            # Direct neighbors from edges
            for edge in traversal_path.edges:
                if edge.source_id in start_ids_set or edge.target_id in start_ids_set:
                    direct_set.add(edge.source_id)
                    direct_set.add(edge.target_id)
                else:
                    indirect_set.add(edge.source_id)
                    indirect_set.add(edge.target_id)

            # Clean sets (exclude the origin changed symbols themselves)
            direct_set -= start_ids_set
            indirect_set -= start_ids_set
            indirect_set -= direct_set

            seen_entities: Set[str] = set()

            for node in traversal_path.nodes:
                if node.id in start_ids_set or node.id in seen_entities:
                    continue
                seen_entities.add(node.id)

                hop = 1 if node.id in direct_set else 2
                conf = ConfidenceLevel.HIGH_CONFIDENCE if hop == 1 else ConfidenceLevel.INFERRED

                entity = AffectedEntity(
                    id=node.id,
                    name=node.name,
                    entity_type=node.symbol_type.value,
                    file_path=node.file_path,
                    confidence=conf,
                    hop_distance=hop,
                    provenance_reason=f"Downstream dependent of changed symbol at hop distance {hop}",
                )

                if node.symbol_type in (SymbolType.ROUTE,) or node.id.startswith("api:"):
                    affected_apis.append(entity)
                elif node.symbol_type == SymbolType.COMPONENT:
                    affected_ui.append(entity)
                elif node.symbol_type == SymbolType.TEST or "test" in node.file_path.lower():
                    affected_tests.append(entity)
                elif node.symbol_type == SymbolType.DB_MODEL or node.id.startswith("db_table:"):
                    affected_databases.append(entity)
                else:
                    affected_components.append(entity)

        all_changed_files = sorted(changes.added_files + changes.modified_files + changes.deleted_files)

        blast = BlastRadius(
            direct_count=len(direct_set),
            indirect_count=len(indirect_set),
            total_affected=len(direct_set) + len(indirect_set),
            max_depth=max_depth if changed_symbol_ids else 0,
        )

        return ImpactReport(
            report_id=generate_id("imp"),
            tree_hash=tree_hash,
            has_changes=changes.has_changes,
            changed_files_count=len(all_changed_files),
            changed_files=all_changed_files,
            changed_symbols=changed_symbols,
            affected_components=affected_components,
            affected_apis=affected_apis,
            affected_ui=affected_ui,
            affected_tests=affected_tests,
            affected_databases=affected_databases,
            blast_radius=blast,
        )
