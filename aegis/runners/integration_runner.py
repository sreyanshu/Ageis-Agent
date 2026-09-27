"""
Aegis Integration Test Runner Adapter
Executes integration tests validating interactions between services, databases,
caches, and external dependencies with strict environment boundary enforcement.
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import List, Optional

from aegis.core.executor import ProcessExecutor, ExecutionResult
from aegis.evidence.models import TestResult, TestStatus
from aegis.runners.base import (
    TestRunner,
    RunnerCapability,
    RunnerCategory,
    ExecutionContext,
    RunnerPlan,
)


class IntegrationRunner(TestRunner):
    """Executes multi-component integration tests."""

    def __init__(self, workspace_root: Path | str, executor: Optional[ProcessExecutor] = None) -> None:
        super().__init__(workspace_root)
        self.executor = executor or ProcessExecutor(default_cwd=str(self.workspace_root))

    @property
    def capability(self) -> RunnerCapability:
        return RunnerCapability(
            name="aegis_integration_runner",
            version="1.0.0",
            categories=[RunnerCategory.INTEGRATION],
            supported_languages=["python", "javascript", "typescript", "go"],
            supported_frameworks=["pytest", "vitest", "jest", "go_test"],
            supports_parallel=False,
            supports_retry=True,
            supports_targeted_execution=True,
            supports_dry_run=True,
            supports_artifacts=True,
        )

    def supports(self, context: ExecutionContext) -> bool:
        return context.category == RunnerCategory.INTEGRATION or context.category == "all"

    def plan(self, context: ExecutionContext) -> RunnerPlan:
        root = self.workspace_root
        cmd = [sys.executable, "-m", "pytest", "-v", "-m", "integration"]
        return RunnerPlan(
            runner_name=self.capability.name,
            category=RunnerCategory.INTEGRATION,
            command=cmd,
            cwd=str(self.workspace_root),
            timeout_seconds=context.timeout_seconds,
        )

    def execute(self, plan: RunnerPlan, context: ExecutionContext) -> List[TestResult]:
        if context.dry_run:
            return [
                TestResult(
                    test_id="integration.dry_run",
                    name="Integration Test Suite (Dry Run)",
                    category="integration",
                    status=TestStatus.PASSED,
                    duration_ms=0.0,
                    runner=self.capability.name,
                    raw_stdout=f"[DRY_RUN] Simulated integration verification: {' '.join(plan.command)}",
                )
            ]

        # Prevent unsafe mutations if in safe mode and environment is production
        if context.environment.get("ENV") == "production":
            return [
                TestResult(
                    test_id="integration.blocked_production",
                    name="Production Integration Boundary Protection",
                    category="integration",
                    status=TestStatus.FAILED,
                    duration_ms=0.0,
                    runner=self.capability.name,
                    raw_stderr="Integration runner refused execution against production environment.",
                )
            ]

        res: ExecutionResult = self.executor.run(
            command=plan.command,
            cwd=plan.cwd,
            timeout_seconds=plan.timeout_seconds,
        )

        status = TestStatus.PASSED if res.is_success else TestStatus.FAILED
        return [
            TestResult(
                test_id=f"integration.suite.{Path(plan.cwd).name}",
                name="Integration Test Suite",
                category="integration",
                status=status,
                duration_ms=res.duration_ms,
                runner=self.capability.name,
                raw_stdout=res.stdout,
                raw_stderr=res.stderr,
            )
        ]
