"""
Aegis Hashing & Incremental Change Caching Engine
Provides deterministic SHA-256 file hashing, tree hashing, AST hashing, and change detection.
"""

from __future__ import annotations
import ast
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from pydantic import BaseModel, Field

from aegis.storage.base import StorageBackend


class ChangeSet(BaseModel):
    """Encapsulates detected file modifications between analysis cycles."""
    added_files: List[str] = Field(default_factory=list)
    modified_files: List[str] = Field(default_factory=list)
    deleted_files: List[str] = Field(default_factory=list)
    unchanged_files: List[str] = Field(default_factory=list)
    total_scanned: int = 0
    tree_hash: str = ""

    @property
    def has_changes(self) -> bool:
        return bool(self.added_files or self.modified_files or self.deleted_files)


class ContentHasher:
    """Computes cryptographic hashes for files, directories, and ASTs."""

    IGNORED_DIRS: Set[str] = {
        ".git", ".aegis", "node_modules", ".venv", "venv", "__pycache__",
        ".pytest_cache", "target", "build", "dist", ".idea", ".vscode",
        ".turbo", ".next", ".nuxt", "coverage", ".tox"
    }

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def hash_file(file_path: Path | str) -> str:
        """Computes SHA-256 hash of a single file."""
        p = Path(file_path)
        if not p.is_file():
            return ""
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def hash_python_ast(source_code: str) -> str:
        """
        Computes an AST-level hash ignoring whitespace and comments for Python files.
        Falls back to normalized text hash if syntax errors occur.
        """
        try:
            tree = ast.parse(source_code)
            dumped = ast.dump(tree, annotate_fields=False, include_attributes=False)
            return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
        except Exception:
            return hashlib.sha256(source_code.strip().encode("utf-8")).hexdigest()

    @classmethod
    def hash_directory_tree(cls, root_dir: Path | str) -> Tuple[str, Dict[str, str]]:
        """
        Scans a directory recursively (respecting ignore lists) and generates:
        1. Aggregate tree hash
        2. Mapping of relative file path -> file content hash
        """
        root = Path(root_dir).resolve()
        file_hashes: Dict[str, str] = {}

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune ignored directories in-place
            dirnames[:] = [d for d in dirnames if d not in cls.IGNORED_DIRS and not d.startswith(".")]

            for filename in sorted(filenames):
                if filename.startswith("."):
                    continue
                full_path = Path(dirpath) / filename
                rel_path = str(full_path.relative_to(root))
                file_hashes[rel_path] = cls.hash_file(full_path)

        # Compute deterministic tree hash from sorted list of relative paths and hashes
        tree_hasher = hashlib.sha256()
        for rel_path in sorted(file_hashes.keys()):
            tree_hasher.update(rel_path.encode("utf-8"))
            tree_hasher.update(file_hashes[rel_path].encode("utf-8"))

        return tree_hasher.hexdigest(), file_hashes


class IncrementalChangeEngine:
    """Manages incremental change detection against previous indexed state."""

    CACHE_FILE = "cache/file_hashes.json"

    def __init__(self, workspace_root: Path | str, storage: StorageBackend) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.storage = storage

    def detect_changes(self) -> ChangeSet:
        """
        Compares current workspace file hashes against last recorded hashes in storage.
        """
        tree_hash, current_hashes = ContentHasher.hash_directory_tree(self.workspace_root)
        previous_data = self.storage.load_json(self.CACHE_FILE) or {}
        previous_hashes: Dict[str, str] = previous_data.get("files", {}) if isinstance(previous_data, dict) else {}

        added: List[str] = []
        modified: List[str] = []
        deleted: List[str] = []
        unchanged: List[str] = []

        # Find added, modified, unchanged
        for path, curr_h in current_hashes.items():
            if path not in previous_hashes:
                added.append(path)
            elif previous_hashes[path] != curr_h:
                modified.append(path)
            else:
                unchanged.append(path)

        # Find deleted
        for path in previous_hashes.keys():
            if path not in current_hashes:
                deleted.append(path)

        return ChangeSet(
            added_files=sorted(added),
            modified_files=sorted(modified),
            deleted_files=sorted(deleted),
            unchanged_files=sorted(unchanged),
            total_scanned=len(current_hashes),
            tree_hash=tree_hash,
        )

    def commit_hashes(self) -> str:
        """Persists current workspace hashes to cache after successful analysis or testing."""
        tree_hash, current_hashes = ContentHasher.hash_directory_tree(self.workspace_root)
        self.storage.save_json(
            self.CACHE_FILE,
            {
                "tree_hash": tree_hash,
                "file_count": len(current_hashes),
                "files": current_hashes,
            },
        )
        return tree_hash
