"""
Aegis Test Runner Registry
Manages discovery, registration, and dispatching of test and validation runners.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Type

from aegis.runners.base import TestRunner, RunnerCategory, ExecutionContext


class RunnerRegistry:
    """Central registry of universal test runners."""

    def __init__(self) -> None:
        self._runners: Dict[str, TestRunner] = {}

    def register(self, runner: TestRunner) -> None:
        """Registers a runner instance."""
        self._runners[runner.capability.name] = runner

    def get_runner(self, name: str) -> Optional[TestRunner]:
        """Retrieves runner by exact name."""
        return self._runners.get(name)

    def find_runners_for_category(self, category: RunnerCategory) -> List[TestRunner]:
        """Returns all runners supporting a given category."""
        return [r for r in self._runners.values() if category in r.capability.categories]

    def find_best_runner(self, context: ExecutionContext) -> Optional[TestRunner]:
        """Selects the most suitable runner for the execution context."""
        matching = [r for r in self.find_runners_for_category(context.category) if r.supports(context)]
        if not matching:
            return None
        # Prefer targeted runners if target files are specified
        if context.target_files:
            targeted = [r for r in matching if r.capability.supports_targeted_execution]
            if targeted:
                return targeted[0]
        return matching[0]

    def list_all(self) -> List[TestRunner]:
        return list(self._runners.values())
