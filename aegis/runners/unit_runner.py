"""
Aegis Universal Unit Test Runner Adapter
Executes native unit tests across Python (pytest), JavaScript/TypeScript (Vitest/Jest),
and Go (go test) with support for full suite and fine-grained targeted execution.
"""

from __future__ import annotations
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from aegis.core.executor import ProcessExecutor, ExecutionResult
from aegis.evidence.models import TestResult, TestStatus, ArtifactRef
from aegis.runners.base import (
    TestRunner,
    RunnerCapability,
    RunnerCategory,
    ExecutionContext,
    RunnerPlan,
)


class UniversalUnitRunner(TestRunner):
    """Universal unit test adapter that executes native test tools."""

    def __init__(self, workspace_root: Path | str, executor: Optional[ProcessExecutor] = None) -> None:
        super().__init__(workspace_root)
        self.executor = executor or ProcessExecutor(default_cwd=str(self.workspace_root))

    @property
    def capability(self) -> RunnerCapability:
        return RunnerCapability(
            name="native_unit_runner",
            version="1.0.0",
            categories=[RunnerCategory.UNIT],
            supported_languages=["python", "javascript", "typescript", "go"],
            supported_frameworks=["pytest", "vitest", "jest", "go_test"],
            supports_parallel=True,
            supports_retry=True,
            supports_targeted_execution=True,
            supports_dry_run=True,
            supports_artifacts=True,
        )

    def supports(self, context: ExecutionContext) -> bool:
        if context.category != RunnerCategory.UNIT:
            return False
        # Check if Python, Node, or Go tests exist in workspace
        root = self.workspace_root
        has_python = (root / "pytest.ini").is_file() or (root / "pyproject.toml").is_file() or list(root.glob("**/test_*.py"))
        has_node = (root / "package.json").is_file() and (list(root.glob("**/*.test.*")) or list(root.glob("**/*.spec.*")))
        has_go = (root / "go.mod").is_file() or list(root.glob("**/*_test.go"))
        return bool(has_python or has_node or has_go)

    def plan(self, context: ExecutionContext) -> RunnerPlan:
        root = self.workspace_root
        cmd: List[str] = []
        is_targeted = bool(context.target_files or context.target_symbols)
        target_descriptors: List[str] = []

        # 1. Python (pytest)
        if (root / "pytest.ini").is_file() or (root / "pyproject.toml").is_file() or list(root.glob("**/test_*.py")):
            cmd = [sys.executable, "-m", "pytest", "-v"]
            if context.target_files:
                # Add specific target files
                py_targets = [f for f in context.target_files if f.endswith(".py")]
                if py_targets:
                    cmd.extend(py_targets)
                    target_descriptors = py_targets
            if context.target_symbols:
                # Filter by test name expression (-k)
                func_names = [s.split(".")[-1] for s in context.target_symbols if "test" in s.lower()]
                if func_names:
                    cmd.extend(["-k", " or ".join(func_names)])
                    target_descriptors.extend(func_names)

        # 2. JS / TS (Vitest / Jest)
        elif (root / "package.json").is_file():
            has_vitest = (root / "vitest.config.ts").is_file() or (root / "vitest.config.js").is_file()
            base_bin = "npx vitest run" if has_vitest else "npm test"
            cmd = base_bin.split()
            if context.target_files:
                js_targets = [f for f in context.target_files if f.endswith((".js", ".ts", ".jsx", ".tsx"))]
                if js_targets:
                    cmd.extend(js_targets)
                    target_descriptors = js_targets

        # 3. Go (go test)
        elif (root / "go.mod").is_file() or list(root.glob("**/*_test.go")):
            cmd = ["go", "test", "-v"]
            if context.target_files:
                go_dirs = list({str(Path(f).parent) for f in context.target_files if f.endswith(".go")})
                if go_dirs:
                    cmd.extend([f"./{d}/..." for d in go_dirs])
                    target_descriptors = go_dirs
                else:
                    cmd.append("./...")
            else:
                cmd.append("./...")

        else:
            cmd = ["echo", "No native unit runner detected"]

        return RunnerPlan(
            runner_name=self.capability.name,
            category=RunnerCategory.UNIT,
            command=cmd,
            cwd=str(self.workspace_root),
            timeout_seconds=context.timeout_seconds,
            is_targeted=is_targeted,
            target_descriptors=target_descriptors,
        )

    def execute(self, plan: RunnerPlan, context: ExecutionContext) -> List[TestResult]:
        res: ExecutionResult = self.executor.run(
            command=plan.command,
            cwd=plan.cwd,
            timeout_seconds=plan.timeout_seconds,
            dry_run=context.dry_run,
        )

        results: List[TestResult] = []

        if context.dry_run:
            results.append(
                TestResult(
                    test_id="unit.dry_run",
                    name="Unit Tests (Dry Run)",
                    category="unit",
                    status=TestStatus.PASSED,
                    duration_ms=0.0,
                    runner=self.capability.name,
                    raw_stdout=res.stdout,
                )
            )
            return results

        if res.timed_out:
            results.append(
                TestResult(
                    test_id="unit.timeout",
                    name="Unit Test Execution Timed Out",
                    category="unit",
                    status=TestStatus.TIMEOUT,
                    duration_ms=res.duration_ms,
                    runner=self.capability.name,
                    raw_stdout=res.stdout,
                    raw_stderr=res.stderr or f"Execution exceeded timeout limit of {plan.timeout_seconds}s",
                )
            )
            return results

        # Parse output for individual test cases if possible (pytest output format: "path::test_name PASSED/FAILED")
        parsed_cases = self._parse_test_outputs(res.stdout, res.stderr)
        if parsed_cases:
            for c_id, c_name, c_status, c_dur in parsed_cases:
                results.append(
                    TestResult(
                        test_id=c_id,
                        name=c_name,
                        category="unit",
                        status=c_status,
                        duration_ms=c_dur,
                        runner=self.capability.name,
                        raw_stdout=res.stdout if c_status == TestStatus.FAILED else None,
                        raw_stderr=res.stderr if c_status == TestStatus.FAILED else None,
                    )
                )
        else:
            # Fallback to suite-level outcome
            suite_status = TestStatus.PASSED if res.is_success else TestStatus.FAILED
            results.append(
                TestResult(
                    test_id=f"unit.suite.{Path(plan.cwd).name}",
                    name=f"Unit Test Suite ({' '.join(plan.command[:2])})",
                    category="unit",
                    status=suite_status,
                    duration_ms=res.duration_ms,
                    runner=self.capability.name,
                    raw_stdout=res.stdout,
                    raw_stderr=res.stderr,
                )
            )

        return results

    def _parse_test_outputs(self, stdout: str, stderr: str) -> List[tuple[str, str, TestStatus, float]]:
        """Parses individual test items from standard test runners (pytest / vitest / go test)."""
        items: List[tuple[str, str, TestStatus, float]] = []
        combined = stdout + "\n" + stderr

        # 1. Pytest format: "tests/test_foo.py::test_bar PASSED" or "FAILED"
        pytest_pattern = re.compile(r'^(\S+::\S+)\s+(PASSED|FAILED|SKIPPED|ERROR)', re.MULTILINE)
        for m in pytest_pattern.finditer(combined):
            t_id = m.group(1)
            t_name = t_id.split("::")[-1]
            raw_status = m.group(2).upper()
            status_map = {
                "PASSED": TestStatus.PASSED,
                "FAILED": TestStatus.FAILED,
                "SKIPPED": TestStatus.SKIPPED,
                "ERROR": TestStatus.ERROR,
            }
            items.append((t_id, t_name, status_map.get(raw_status, TestStatus.FAILED), 10.0))

        # 2. Go test format: "--- PASS: TestName (0.00s)" or "--- FAIL: TestName"
        go_pattern = re.compile(r'^---\s+(PASS|FAIL|SKIP):\s+([A-Za-z0-9_]+)(?:\s+\(([0-9\.]+)s\))?', re.MULTILINE)
        for m in go_pattern.finditer(combined):
            outcome = m.group(1)
            t_name = m.group(2)
            dur_s = float(m.group(3)) if m.group(3) else 0.01
            st = TestStatus.PASSED if outcome == "PASS" else (TestStatus.SKIPPED if outcome == "SKIP" else TestStatus.FAILED)
            items.append((f"go.{t_name}", t_name, st, dur_s * 1000.0))

        return items
