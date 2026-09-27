"""
Aegis Change Impact Data Models
Defines machine-readable structures for changed symbols, downstream affected entities,
blast radius, and complete impact reports.
"""

from __future__ import annotations
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from aegis.indexer.base import ConfidenceLevel


class SymbolChangeType(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    SIGNATURE_CHANGED = "SIGNATURE_CHANGED"
    BODY_CHANGED = "BODY_CHANGED"
    COMMENTS_ONLY = "COMMENTS_ONLY"


class ChangedSymbol(BaseModel):
    symbol_id: str
    name: str
    change_type: SymbolChangeType
    symbol_type: str
    file_path: str
    line_start: Optional[int] = None
    signature: Optional[str] = None
    previous_signature: Optional[str] = None


class AffectedEntity(BaseModel):
    id: str
    name: str
    entity_type: str                         # api, ui, test, db, component
    file_path: str
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH_CONFIDENCE
    hop_distance: int = 1
    provenance_reason: Optional[str] = None


class BlastRadius(BaseModel):
    direct_count: int = 0
    indirect_count: int = 0
    total_affected: int = 0
    max_depth: int = 0


class ImpactReport(BaseModel):
    """Complete structured assessment of change blast radius and affected downstream components."""
    report_id: str
    timestamp: float = Field(default_factory=time.time)
    tree_hash: str
    has_changes: bool = False
    changed_files_count: int = 0
    changed_files: List[str] = Field(default_factory=list)
    changed_symbols: List[ChangedSymbol] = Field(default_factory=list)
    affected_components: List[AffectedEntity] = Field(default_factory=list)
    affected_apis: List[AffectedEntity] = Field(default_factory=list)
    affected_ui: List[AffectedEntity] = Field(default_factory=list)
    affected_tests: List[AffectedEntity] = Field(default_factory=list)
    affected_databases: List[AffectedEntity] = Field(default_factory=list)
    blast_radius: BlastRadius = Field(default_factory=BlastRadius)
    metadata: Dict[str, Any] = Field(default_factory=dict)
