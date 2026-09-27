"""
Aegis Runner & Adapter Base Interfaces
Defines abstract contracts for test runners, quality dimension evaluators, and protocol adapters.
Future runners (Unit, API, E2E, UI, Perf, A11y, Security) inherit from BaseRunner.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from aegis.core.exceptions import NotImplementedCapabilityError
from aegis.evidence.models import TestResult, TestStatus


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
