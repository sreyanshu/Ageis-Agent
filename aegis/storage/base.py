"""
Aegis Storage Abstraction Interface
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from pathlib import Path


class StorageBackend(ABC):
    """Abstract interface for all metadata, evidence, and artifact persistence."""

    @abstractmethod
    def save_json(self, relative_path: str, data: Dict[str, Any] | List[Any]) -> Path:
        """Persists JSON-serializable data to storage."""
        pass

    @abstractmethod
    def load_json(self, relative_path: str) -> Optional[Dict[str, Any] | List[Any]]:
        """Loads JSON data from storage if it exists, otherwise None."""
        pass

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Checks if an artifact or metadata entry exists."""
        pass

    @abstractmethod
    def save_raw_artifact(self, relative_path: str, content: bytes | str) -> Path:
        """Stores a raw artifact (logs, dumps, screenshots)."""
        pass

    @abstractmethod
    def load_raw_artifact(self, relative_path: str) -> Optional[bytes]:
        """Reads raw artifact bytes."""
        pass

    @abstractmethod
    def get_artifact_path(self, relative_path: str) -> Path:
        """Returns the full absolute path for a relative storage key."""
        pass
