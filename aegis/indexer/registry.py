"""
Aegis Polyglot Indexer Registry
Dispatches files to language-specific AST and semantic indexers.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional

from aegis.indexer.base import LanguageIndexer, IndexedFile
from aegis.indexer.python_indexer import PythonASTIndexer
from aegis.indexer.js_ts_indexer import JavaScriptTypeScriptIndexer
from aegis.indexer.go_indexer import GoIndexer


class IndexerRegistry:
    """Registry maintaining active language indexers with extension-based dispatching."""

    def __init__(self) -> None:
        self._indexers: List[LanguageIndexer] = []
        self._ext_map: Dict[str, LanguageIndexer] = {}
        self._register_default_indexers()

    def _register_default_indexers(self) -> None:
        self.register(PythonASTIndexer())
        self.register(JavaScriptTypeScriptIndexer())
        self.register(GoIndexer())

    def register(self, indexer: LanguageIndexer) -> None:
        self._indexers.append(indexer)
        for ext in indexer.supported_extensions:
            self._ext_map[ext.lower()] = indexer

    def get_indexer_for_file(self, file_path: Path | str) -> Optional[LanguageIndexer]:
        ext = Path(file_path).suffix.lower()
        return self._ext_map.get(ext)

    def can_index(self, file_path: Path | str) -> bool:
        return self.get_indexer_for_file(file_path) is not None

    def index_file(self, workspace_root: Path | str, relative_path: Path | str, content: Optional[str] = None) -> Optional[IndexedFile]:
        indexer = self.get_indexer_for_file(relative_path)
        if not indexer:
            return None
        return indexer.index_file(workspace_root=workspace_root, relative_path=relative_path, content=content)


# Global default registry
default_indexer_registry = IndexerRegistry()
