"""
Aegis Runner & Adapter Base Interfaces
Defines abstract contracts for test runners, quality dimension evaluators, protocol adapters,
and universal repository technology adapters.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from aegis.core.exceptions import NotImplementedCapabilityError
from aegis.evidence.models import TestResult, TestStatus
from aegis.adapters.capabilities import ProjectCapability, CapabilityType, CapabilityStatus


class RunnerCapability(BaseModel):
    category: str  # unit, api, sanity, integration, e2e, ui, ux, a11y, security, perf, compatibility
    supports_parallel: bool = True
    supports_filtering: bool = True
    requires_browser: bool = False
    requires_database: bool = False


class BaseRunner(ABC):
    """Abstract interface for all deterministic test and quality dimension runners."""

    def __init__(self, workspace_root: str, config: Optional[Dict[str, Any]] = None) -> None:
        self.workspace_root = workspace_root
        self.config = config or {}

    @property
    @abstractmethod
    def category(self) -> str:
        """Returns runner category: unit, api, sanity, etc."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> RunnerCapability:
        """Declares runner capabilities."""
        pass

    @abstractmethod
    def run(self, filter_patterns: Optional[List[str]] = None, dry_run: bool = False) -> List[TestResult]:
        """
        Executes tests within this runner's domain.
        Must raise NotImplementedCapabilityError if implementation is deferred.
        """
        raise NotImplementedCapabilityError(f"Runner for '{self.category}' is not yet implemented in this phase.")


class BaseAdapter(ABC):
    """Abstract protocol adapter (MCP, REST, CLI, IDE plugin)."""

    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def handle_request(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedCapabilityError(f"Adapter action '{action}' is not yet implemented.")


# ==============================================================================
# UNIVERSAL ADAPTER CONTRACTS (Phase 6)
# ==============================================================================

class DetectionResult(BaseModel):
    """Outcome of an adapter's detection scan over a workspace."""
    detected: bool = False
    confidence: float = 0.0          # 0.0 (uncertain) to 1.0 (certain)
    evidence: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DiscoveryResult(BaseModel):
    """Structured assets and capabilities discovered by an active adapter."""
    capabilities: List[ProjectCapability] = Field(default_factory=list)
    configuration_files: List[str] = Field(default_factory=list)
    test_suites: List[Any] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Health and hygiene determination for an adapter's domain."""
    valid: bool = True
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class AegisAdapter(ABC):
    """Universal repository technology and capability adapter interface."""

    def __init__(self, adapter_id: str, name: str, category: str, version: str = "1.0.0") -> None:
        self.adapter_id = adapter_id
        self.name = name
        self.category = category     # language, framework, build, testing, infrastructure, quality, ci
        self.version = version

    @abstractmethod
    def detect(self, workspace_root: Path) -> DetectionResult:
        """Determines if this technology/framework is present in the workspace."""
        pass

    @abstractmethod
    def capabilities(self, workspace_root: Path) -> List[ProjectCapability]:
        """Returns the list of capabilities provided by this adapter."""
        pass

    @abstractmethod
    def discover(self, workspace_root: Path) -> DiscoveryResult:
        """Discovers detailed configuration, entry points, and test surfaces."""
        pass

    def validate(self, workspace_root: Path) -> ValidationResult:
        """Validates configuration hygiene and compatibility."""
        return ValidationResult(valid=True)
