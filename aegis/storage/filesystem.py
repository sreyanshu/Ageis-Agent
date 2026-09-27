"""
Aegis Filesystem Storage Engine
Implements storage backend on the local filesystem under the .aegis/ directory.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from aegis.core.exceptions import StorageError
from aegis.storage.base import StorageBackend


class FilesystemStorage(StorageBackend):
    """Stores all Aegis artifacts, metadata, maps, and caches in the workspace .aegis directory."""

    def __init__(self, workspace_root: Path | str, dir_name: str = ".aegis") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.base_dir = self.workspace_root / dir_name
        self.artifacts_dir = self.base_dir / "artifacts"
        self.cache_dir = self.base_dir / "cache"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise StorageError(f"Failed to initialize storage directories at {self.base_dir}: {e}") from e

    def get_artifact_path(self, relative_path: str) -> Path:
        return self.base_dir / relative_path

    def save_json(self, relative_path: str, data: Dict[str, Any] | List[Any]) -> Path:
        target = self.get_artifact_path(relative_path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return target
        except Exception as e:
            raise StorageError(f"Failed to save JSON to {target}: {e}") from e

    def load_json(self, relative_path: str) -> Optional[Dict[str, Any] | List[Any]]:
        target = self.get_artifact_path(relative_path)
        if not target.exists():
            return None
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise StorageError(f"Failed to load JSON from {target}: {e}") from e

    def exists(self, relative_path: str) -> bool:
        return self.get_artifact_path(relative_path).exists()

    def save_raw_artifact(self, relative_path: str, content: bytes | str) -> Path:
        target = self.artifacts_dir / relative_path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                with open(target, "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                with open(target, "wb") as f:
                    f.write(content)
            return target
        except Exception as e:
            raise StorageError(f"Failed to write raw artifact to {target}: {e}") from e

    def load_raw_artifact(self, relative_path: str) -> Optional[bytes]:
        target = self.artifacts_dir / relative_path
        if not target.exists():
            return None
        try:
            with open(target, "rb") as f:
                return f.read()
        except Exception as e:
            raise StorageError(f"Failed to read raw artifact from {target}: {e}") from e
