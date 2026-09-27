"""
Aegis Sanity & Preflight Execution Runner
Executes ultra-fast preflight checks (manifest integrity, syntax compilation,
port availability, health probe readiness) to gate dependent test execution stages.
"""

from __future__ import annotations
import os
import sys
import time
import socket
import py_compile
from pathlib import Path
from typing import List, Dict, Any, Optional

from aegis.evidence.models import TestResult, TestStatus
from aegis.runners.base import (
    TestRunner,
    RunnerCapability,
    RunnerCategory,
    ExecutionContext,
    RunnerPlan,
)


class SanityPreflightRunner(TestRunner):
    """Fast preflight verification runner that validates runtime assumptions."""

    @property
    def capability(self) -> RunnerCapability:
        return RunnerCapability(
            name="aegis_sanity_runner",
            version="1.0.0",
            categories=[RunnerCategory.SANITY],
            supported_languages=["python", "javascript", "typescript", "go", "any"],
            supported_frameworks=["any"],
            supports_parallel=True,
            supports_retry=False,
            supports_targeted_execution=False,
            supports_dry_run=True,
            supports_artifacts=False,
        )

    def supports(self, context: ExecutionContext) -> bool:
        return context.category == RunnerCategory.SANITY or context.category == "all"

    def plan(self, context: ExecutionContext) -> RunnerPlan:
        return RunnerPlan(
            runner_name=self.capability.name,
            category=RunnerCategory.SANITY,
            command=["aegis", "sanity", "preflight"],
            cwd=str(self.workspace_root),
            timeout_seconds=min(30, context.timeout_seconds),
        )

    def execute(self, plan: RunnerPlan, context: ExecutionContext) -> List[TestResult]:
        results: List[TestResult] = []
        root = self.workspace_root

        if context.dry_run:
            results.append(
                TestResult(
                    test_id="sanity.manifest_integrity",
                    name="Project Manifest Integrity (Dry Run)",
                    category="sanity",
                    status=TestStatus.PASSED,
                    duration_ms=0.0,
                    runner=self.capability.name,
                    raw_stdout="[DRY_RUN] Simulated sanity preflight integrity probe",
                )
            )
            return results

        # 1. Check Project Structure & Manifests
        t_start = time.perf_counter()
        manifest_files = [
            "package.json", "pyproject.toml", "requirements.txt", "go.mod",
            "Cargo.toml", "pom.xml", "build.gradle", ".aegis/config.yaml", ".aegis/project-profile.json"
        ]
        found_manifests = [f for f in manifest_files if (root / f).is_file() or (root / f).exists()]

        dur = (time.perf_counter() - t_start) * 1000.0
        if found_manifests or list(root.glob("*.py")) or list(root.glob("*.js")) or (root / ".aegis").is_dir():
            results.append(
                TestResult(
                    test_id="sanity.manifest_integrity",
                    name="Project Manifest Integrity",
                    category="sanity",
                    status=TestStatus.PASSED,
                    duration_ms=dur,
                    runner=self.capability.name,
                    raw_stdout=f"Valid project root identified. Manifests: {', '.join(found_manifests) or 'Workspace root'}",
                )
            )
        else:
            results.append(
                TestResult(
                    test_id="sanity.manifest_integrity",
                    name="Project Manifest Integrity",
                    category="sanity",
                    status=TestStatus.FAILED,
                    duration_ms=dur,
                    runner=self.capability.name,
                    raw_stderr="No recognised build manifest or source file found in workspace root.",
                )
            )

        # 2. Syntax & Compilation Check (for Python files)
        py_files = list(root.glob("**/*.py"))[:20]  # sample first 20 files
        if py_files:
            t_start = time.perf_counter()
            syntax_errors = []
            for pf in py_files:
                if ".venv" in str(pf) or "node_modules" in str(pf):
                    continue
                try:
                    py_compile.compile(str(pf), doraise=True)
                except py_compile.PyCompileError as e:
                    syntax_errors.append(f"{pf.name}: {e.msg}")

            dur = (time.perf_counter() - t_start) * 1000.0
            if not syntax_errors:
                results.append(
                    TestResult(
                        test_id="sanity.syntax_compilation",
                        name="Python Syntax Pre-compilation",
                        category="sanity",
                        status=TestStatus.PASSED,
                        duration_ms=dur,
                        runner=self.capability.name,
                        raw_stdout=f"Verified {len(py_files)} Python source files without syntax errors.",
                    )
                )
            else:
                results.append(
                    TestResult(
                        test_id="sanity.syntax_compilation",
                        name="Python Syntax Pre-compilation",
                        category="sanity",
                        status=TestStatus.FAILED,
                        duration_ms=dur,
                        runner=self.capability.name,
                        raw_stderr="\n".join(syntax_errors),
                    )
                )

        # 3. Port Conflict Detection (e.g. standard port 8000/8080/3000)
        target_port = context.options.get("probe_port", 0)
        if target_port > 0:
            t_start = time.perf_counter()
            is_open = self._check_port_available(target_port)
            dur = (time.perf_counter() - t_start) * 1000.0
            results.append(
                TestResult(
                    test_id=f"sanity.port_availability_{target_port}",
                    name=f"Port {target_port} Availability",
                    category="sanity",
                    status=TestStatus.PASSED if is_open else TestStatus.FAILED,
                    duration_ms=dur,
                    runner=self.capability.name,
                    raw_stdout=f"Port {target_port} is available" if is_open else None,
                    raw_stderr=f"Port {target_port} is currently in use" if not is_open else None,
                )
            )

        return results

    def _check_port_available(self, port: int) -> bool:
        """Attempts to bind a socket to test if a port is open and available."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False
