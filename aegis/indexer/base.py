"""
Aegis Indexer Base Interfaces & Data Models
Defines symbol types, relationship types, provenance confidence levels,
and the LanguageIndexer abstract interface.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field


class SymbolType(str, Enum):
    MODULE = "module"
    PACKAGE = "package"
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    COMPONENT = "component"
    ROUTE = "route"
    DB_MODEL = "db_model"
    TEST = "test"


class RelationType(str, Enum):
    CONTAINS = "contains"
    IMPORTS = "imports"
    DEPENDS_ON = "depends_on"
    CALLS = "calls"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    EXPORTS = "exports"
    EXPOSES_API = "exposes_api"
    CONSUMES_API = "consumes_api"
    RENDERS = "renders"
    ACCESSES_DATABASE = "accesses_database"
    PUBLISHES_EVENT = "publishes_event"
    CONSUMES_EVENT = "consumes_event"
    TESTED_BY = "tested_by"
    TESTS = "tests"
    CONFIGURED_BY = "configured_by"


class ConfidenceLevel(str, Enum):
    DIRECT = "DIRECT"                  # Extracted directly from AST syntax (e.g. import, class definition)
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"# Strongly inferred from deterministic static patterns
    INFERRED = "INFERRED"              # Resolved via symbol lookup and scope resolution
    HEURISTIC = "HEURISTIC"            # Pattern-based heuristic match (e.g. route string match)
    UNKNOWN = "UNKNOWN"


class Provenance(BaseModel):
    """Explains why and where a symbol or relationship was identified."""
    file_path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    snippet: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.DIRECT
    rationale: Optional[str] = None


class Symbol(BaseModel):
    """Represents a discrete semantic entity in code with stable identity."""
    id: str                                  # E.g. "python:app.services.UserService.get_user"
    name: str                                # E.g. "get_user"
    qualified_name: str                      # E.g. "UserService.get_user"
    symbol_type: SymbolType
    language: str                            # E.g. "python", "typescript", "go"
    file_path: str                           # Relative path in workspace
    line_start: int
    line_end: int
    signature: Optional[str] = None          # E.g. "def get_user(self, user_id: int) -> User:"
    docstring: Optional[str] = None
    content_hash: str = ""                   # SHA-256 hash of the symbol's AST/source representation
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Relationship(BaseModel):
    """Represents a directed typed dependency between two entities."""
    source_id: str
    relation: RelationType
    target_id: str
    provenance: Provenance
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IndexedFile(BaseModel):
    """Complete semantic extraction of a single source file."""
    file_path: str
    language: str
    file_hash: str
    ast_hash: str
    symbol_hash: str                         # Combined hash of all symbols and signatures in this file
    symbols: List[Symbol] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    imports: List[str] = Field(default_factory=list)
    exports: List[str] = Field(default_factory=list)


class LanguageIndexer(ABC):
    """Abstract contract for language-specific AST and semantic indexers."""

    @property
    @abstractmethod
    def language(self) -> str:
        """Language name (e.g. 'python', 'typescript', 'javascript', 'go')."""
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> Set[str]:
        """File extensions handled by this indexer (e.g. {'.py'})."""
        pass

    def supports(self, file_path: Path | str) -> bool:
        """Determines if this indexer can parse the given file."""
        return Path(file_path).suffix.lower() in self.supported_extensions

    @abstractmethod
    def index_file(self, workspace_root: Path | str, relative_path: Path | str, content: Optional[str] = None) -> IndexedFile:
        """Parses the file and extracts all symbols and relationships."""
        pass
