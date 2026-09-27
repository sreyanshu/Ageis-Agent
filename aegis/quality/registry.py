"""
Aegis Quality Dimensions Registry & Coordinator
Registers and coordinates Accessibility, Security, Performance, and UX Quality Runners.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional

from aegis.runners.base import ExecutionContext
from aegis.quality.base import QualityRunner
from aegis.quality.models import QualityDimension, QualityCapability, QualityResult
from aegis.quality.accessibility.runner import AccessibilityRunner
from aegis.quality.security.runner import SecurityRunner
from aegis.quality.performance.runner import PerformanceRunner
from aegis.quality.ux.runner import UXRunner


class QualityRegistry:
    """Central registry for quality dimension runners."""

    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self._runners: Dict[QualityDimension, QualityRunner] = {
            QualityDimension.ACCESSIBILITY: AccessibilityRunner(self.workspace_root),
            QualityDimension.SECURITY: SecurityRunner(self.workspace_root),
            QualityDimension.PERFORMANCE: PerformanceRunner(self.workspace_root),
            QualityDimension.UX: UXRunner(self.workspace_root),
        }

    def register_runner(self, runner: QualityRunner) -> None:
        self._runners[runner.dimension] = runner

    def get_runner(self, dimension: QualityDimension) -> Optional[QualityRunner]:
        return self._runners.get(dimension)

    def list_runners(self) -> List[QualityRunner]:
        return list(self._runners.values())

    def list_capabilities(self) -> List[QualityCapability]:
        return [r.capability for r in self._runners.values()]

    def execute_dimension(self, dimension: QualityDimension, context: ExecutionContext) -> QualityResult:
        runner = self.get_runner(dimension)
        if not runner:
            raise KeyError(f"No runner registered for quality dimension: {dimension}")
        return runner.execute(context)

    def execute_all(self, context: ExecutionContext) -> Dict[QualityDimension, QualityResult]:
        results: Dict[QualityDimension, QualityResult] = {}
        for dim, runner in self._runners.items():
            results[dim] = runner.execute(context)
        return results
