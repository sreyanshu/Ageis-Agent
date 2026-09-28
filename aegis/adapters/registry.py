"""
Aegis Universal Adapter Registry
Registers, queries, and dispatches language, testing, framework, infrastructure,
and quality adapters across repositories.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Type

from aegis.adapters.base import AegisAdapter, DetectionResult, DiscoveryResult
from aegis.adapters.capabilities import ProjectCapability, CapabilityType, CapabilityStatus
from aegis.adapters.builtin.languages import PythonAdapter, JavaScriptTypeScriptAdapter, GoAdapter
from aegis.adapters.builtin.testing import PytestTestAdapter, VitestJestAdapter, GoTestAdapter
from aegis.adapters.builtin.frameworks_infra import (
    WebFrameworkAdapter,
    DockerInfrastructureAdapter,
    QualityToolAdapter,
)


class AdapterRegistry:
    """Universal registry managing technology adapters and capability detection."""

    def __init__(self) -> None:
        self._adapters: Dict[str, AegisAdapter] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Registers all standard built-in adapters."""
        builtins: List[AegisAdapter] = [
            PythonAdapter(),
            JavaScriptTypeScriptAdapter(),
            GoAdapter(),
            PytestTestAdapter(),
            VitestJestAdapter(),
            GoTestAdapter(),
            WebFrameworkAdapter(),
            DockerInfrastructureAdapter(),
            QualityToolAdapter(),
        ]
        for adapter in builtins:
            self.register(adapter)

    def register(self, adapter: AegisAdapter) -> None:
        """Registers an adapter instance."""
        self._adapters[adapter.adapter_id] = adapter

    def get_adapter(self, adapter_id: str) -> Optional[AegisAdapter]:
        """Retrieves an adapter by ID."""
        return self._adapters.get(adapter_id)

    def list_adapters(self, category: Optional[str] = None) -> List[AegisAdapter]:
        """Lists all registered adapters, optionally filtered by category."""
        if category:
            return [a for a in self._adapters.values() if a.category == category]
        return list(self._adapters.values())

    def detect_active_adapters(self, workspace_root: Path | str) -> List[AegisAdapter]:
        """Runs detection across all adapters and returns those matching the workspace."""
        root = Path(workspace_root).resolve()
        active = []
        for adapter in self._adapters.values():
            result = adapter.detect(root)
            if result.detected:
                active.append(adapter)
        return active

    def resolve_capabilities(self, workspace_root: Path | str) -> List[ProjectCapability]:
        """Resolves and deduplicates all capabilities across all detected adapters."""
        root = Path(workspace_root).resolve()
        active = self.detect_active_adapters(root)
        caps_by_id: Dict[str, ProjectCapability] = {}

        for adapter in active:
            for cap in adapter.capabilities(root):
                if cap.id not in caps_by_id:
                    caps_by_id[cap.id] = cap
                else:
                    # Merge evidence and keep highest confidence
                    existing = caps_by_id[cap.id]
                    existing.evidence = list(set(existing.evidence + cap.evidence))
                    existing.confidence = max(existing.confidence, cap.confidence)

        return list(caps_by_id.values())


# Global default instance
default_adapter_registry = AdapterRegistry()
