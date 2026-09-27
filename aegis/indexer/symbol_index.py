"""
Aegis Incremental Symbol Index
Tracks symbols across all source files, detects symbol-level signature changes,
and persists symbol index state for fast incremental re-indexing.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from aegis.indexer.base import Symbol, IndexedFile, Relationship
from aegis.indexer.registry import IndexerRegistry, default_indexer_registry
from aegis.storage.base import StorageBackend
from aegis.storage.hashing import ContentHasher


class SymbolFileMeta(BaseModel):
    file_path: str
    language: str
    file_hash: str
    ast_hash: str
    symbol_hash: str
    symbol_count: int = 0
    relationship_count: int = 0


class SymbolIndexSnapshot(BaseModel):
    schema_version: str = "1.0.0"
    total_symbols: int = 0
    total_relationships: int = 0
    files: Dict[str, SymbolFileMeta] = Field(default_factory=dict)
    symbols: Dict[str, Symbol] = Field(default_factory=dict)
    relationships: List[Relationship] = Field(default_factory=list)


class SymbolIndex:
    """Persistent incremental symbol index."""

    INDEX_CACHE_KEY = "cache/symbol_index.json"

    def __init__(
        self,
        workspace_root: Path | str,
        storage: Optional[StorageBackend] = None,
        registry: Optional[IndexerRegistry] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.storage = storage
        self.registry = registry or default_indexer_registry
        self.files_meta: Dict[str, SymbolFileMeta] = {}
        self.symbols: Dict[str, Symbol] = {}
        self.relationships: List[Relationship] = []
        self._file_to_symbols: Dict[str, Set[str]] = {}
        self._file_to_relationships: Dict[str, List[Relationship]] = {}
        self._load_cached_index()

    def _load_cached_index(self) -> None:
        """Loads previous snapshot from storage if available."""
        if not self.storage:
            return
        data = self.storage.load_json(self.INDEX_CACHE_KEY)
        if not data or not isinstance(data, dict):
            return

        try:
            snapshot = SymbolIndexSnapshot(**data)
            self.files_meta = snapshot.files
            self.symbols = snapshot.symbols
            self.relationships = snapshot.relationships

            # Reconstruct file lookup indices
            for sym_id, sym in self.symbols.items():
                if sym.file_path not in self._file_to_symbols:
                    self._file_to_symbols[sym.file_path] = set()
                self._file_to_symbols[sym.file_path].add(sym_id)

            for rel in self.relationships:
                fpath = rel.provenance.file_path
                if fpath not in self._file_to_relationships:
                    self._file_to_relationships[fpath] = []
                self._file_to_relationships[fpath].append(rel)
        except Exception:
            pass

    def save(self) -> None:
        """Persists current symbol index snapshot to storage."""
        if not self.storage:
            return
        snapshot = SymbolIndexSnapshot(
            total_symbols=len(self.symbols),
            total_relationships=len(self.relationships),
            files=self.files_meta,
            symbols=self.symbols,
            relationships=self.relationships,
        )
        self.storage.save_json(self.INDEX_CACHE_KEY, snapshot.model_dump())

    def update_file(self, relative_path: str, content: Optional[str] = None) -> Optional[IndexedFile]:
        """Indexes or re-indexes a single file, replacing its prior symbols and relationships."""
        indexed = self.registry.index_file(
            workspace_root=self.workspace_root,
            relative_path=relative_path,
            content=content,
        )
        if not indexed:
            return None

        # Remove previous symbols and relations for this file
        old_sym_ids = self._file_to_symbols.pop(relative_path, set())
        for sid in old_sym_ids:
            self.symbols.pop(sid, None)

        self.relationships = [r for r in self.relationships if r.provenance.file_path != relative_path]

        # Insert new symbols and relations
        self._file_to_symbols[relative_path] = set()
        for sym in indexed.symbols:
            self.symbols[sym.id] = sym
            self._file_to_symbols[relative_path].add(sym.id)

        self.relationships.extend(indexed.relationships)
        self._file_to_relationships[relative_path] = indexed.relationships

        # Update file metadata
        self.files_meta[relative_path] = SymbolFileMeta(
            file_path=relative_path,
            language=indexed.language,
            file_hash=indexed.file_hash,
            ast_hash=indexed.ast_hash,
            symbol_hash=indexed.symbol_hash,
            symbol_count=len(indexed.symbols),
            relationship_count=len(indexed.relationships),
        )

        return indexed

    def remove_file(self, relative_path: str) -> None:
        """Removes a file and its symbols/relationships from the index."""
        old_sym_ids = self._file_to_symbols.pop(relative_path, set())
        for sid in old_sym_ids:
            self.symbols.pop(sid, None)

        self.relationships = [r for r in self.relationships if r.provenance.file_path != relative_path]
        self._file_to_relationships.pop(relative_path, None)
        self.files_meta.pop(relative_path, None)

    def index_workspace(self, force_full: bool = False) -> Tuple[int, int]:
        """
        Incrementally indexes the workspace.
        Only re-indexes files whose file_hash has changed.
        Returns: (reindexed_count, skipped_count)
        """
        reindexed_count = 0
        skipped_count = 0
        current_files: Set[str] = set()

        for dirpath, dirnames, filenames in os.walk(self.workspace_root):
            # Respect standard exclusions
            dirnames[:] = [d for d in dirnames if d not in ContentHasher.IGNORED_DIRS and not d.startswith(".")]

            for f in filenames:
                if f.startswith("."):
                    continue
                full_path = Path(dirpath) / f
                rel_path = str(full_path.relative_to(self.workspace_root)).replace("\\", "/")

                if not self.registry.can_index(rel_path):
                    continue

                current_files.add(rel_path)
                current_file_hash = ContentHasher.hash_file(full_path)

                # Check if cached and unchanged
                if (
                    not force_full
                    and rel_path in self.files_meta
                    and self.files_meta[rel_path].file_hash == current_file_hash
                ):
                    skipped_count += 1
                    continue

                # Re-index
                self.update_file(rel_path)
                reindexed_count += 1

        # Remove deleted files
        indexed_files = set(self.files_meta.keys())
        deleted_files = indexed_files - current_files
        for df in deleted_files:
            self.remove_file(df)

        self.save()
        return reindexed_count, skipped_count
