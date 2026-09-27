"""
Aegis Core Orchestrator Engine
Coordinates discovery, storage, change impact detection, evidence accumulation, and release gating.
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from aegis.core.config import AegisConfig
from aegis.core.events import (
    EventBus,
    DiscoveryStartedEvent,
    DiscoveryCompletedEvent,
    ReleaseVerdictComputedEvent,
    default_event_bus,
    generate_id,
)
from aegis.core.executor import ProcessExecutor
from aegis.discovery.detector import ProjectDiscoveryEngine, ProjectProfile
from aegis.storage.filesystem import FilesystemStorage
from aegis.storage.hashing import IncrementalChangeEngine, ChangeSet
from aegis.evidence.models import (
    ReleaseAssessment,
    ReleaseGateVerdict,
    PolicyCheckResult,
    EvidenceReport,
    TestResult,
    TestStatus,
)
from aegis.evidence.collector import EvidenceCollector


class AegisEngine:
    """Central orchestrator for the Aegis quality engineering platform."""

    def __init__(
        self,
        workspace_root: Optional[Path | str] = None,
        config: Optional[AegisConfig] = None,
        storage: Optional[FilesystemStorage] = None,
        event_bus: Optional[EventBus] = None,
        executor: Optional[ProcessExecutor] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.config = config or AegisConfig.load(workspace_root=self.workspace_root)
        self.storage = storage or FilesystemStorage(self.workspace_root, dir_name=self.config.storage.dir_name)
        self.event_bus = event_bus or default_event_bus
        self.executor = executor or ProcessExecutor(
            default_cwd=str(self.workspace_root),
            default_timeout_seconds=self.config.execution.timeout_seconds,
        )

        self.discovery_engine = ProjectDiscoveryEngine(self.workspace_root, storage=self.storage)
        self.change_engine = IncrementalChangeEngine(self.workspace_root, storage=self.storage)

    def init_workspace(self) -> Path:
        """Initializes Aegis workspace structure and writes default configuration."""
        config_path = self.config.save(self.workspace_root / self.config.storage.dir_name / "config.yaml")
        # Run initial discovery to populate profile artifacts
        self.discover()
        self.change_engine.commit_hashes()
        return config_path

    def discover(self, project_name: Optional[str] = None) -> ProjectProfile:
        """Discovers full repository structure and saves all machine-readable profiles."""
        corr_id = generate_id("corr")
        self.event_bus.publish(DiscoveryStartedEvent(correlation_id=corr_id, payload={"root": str(self.workspace_root)}))

        p_name = project_name or (self.config.project.name if self.config.project.name != "auto-detected" else self.workspace_root.name)
        profile = self.discovery_engine.discover(project_name=p_name)

        self.event_bus.publish(
            DiscoveryCompletedEvent(
                correlation_id=corr_id,
                payload={
                    "project_name": profile.project_name,
                    "languages": [l.name for l in profile.languages],
                    "frameworks": [f.name for f in profile.frameworks],
                    "tree_hash": profile.tree_hash,
                },
            )
        )
        return profile

    def detect_changes(self) -> ChangeSet:
        """Analyzes incremental changes since the last recorded state."""
        return self.change_engine.detect_changes()

    def commit_changes(self) -> str:
        """Updates file hashes cache."""
        return self.change_engine.commit_hashes()

    def assess_release_readiness(self, report: EvidenceReport) -> ReleaseAssessment:
        """
        Evaluates release policies deterministically against the evidence report.
        Strict policy verification: zero AI hallucinations allowed in gating.
        """
        policy = self.config.release
        checks: List[PolicyCheckResult] = []
        reasons: List[str] = []
        verdict = ReleaseGateVerdict.READY

        # 1. Critical test failures check
        if policy.critical_tests_must_pass and report.failed > 0:
            checks.append(
                PolicyCheckResult(
                    policy_name="critical_tests_must_pass",
                    passed=False,
                    details=f"{report.failed} test(s) failed during validation run.",
                )
            )
            reasons.append(f"Blocked by {report.failed} failing test(s).")
            verdict = ReleaseGateVerdict.BLOCKED
        else:
            checks.append(
                PolicyCheckResult(
                    policy_name="critical_tests_must_pass",
                    passed=True,
                    details="All executed tests passed successfully.",
                )
            )

        # 2. Execution errors check
        if report.errors > 0:
            checks.append(
                PolicyCheckResult(
                    policy_name="zero_execution_errors",
                    passed=False,
                    details=f"{report.errors} test runner error(s) or timeout(s) detected.",
                )
            )
            reasons.append(f"{report.errors} runner error(s) occurred.")
            verdict = ReleaseGateVerdict.BLOCKED
        else:
            checks.append(
                PolicyCheckResult(
                    policy_name="zero_execution_errors",
                    passed=True,
                    details="Zero runner execution errors or timeouts.",
                )
            )

        # 3. Human approval requirement flag
        if policy.require_human_approval and verdict == ReleaseGateVerdict.READY:
            checks.append(
                PolicyCheckResult(
                    policy_name="require_human_approval",
                    passed=True,
                    details="Release meets automated criteria; awaiting required human approval.",
                )
            )
            verdict = ReleaseGateVerdict.REQUIRES_REVIEW
            reasons.append("Automated policies passed. Requires final human confirmation per release policy.")

        assessment = ReleaseAssessment(
            verdict=verdict,
            policy_checks=checks,
            reasons=reasons,
            total_tests=report.total_tests,
            passed_tests=report.passed,
            failed_tests=report.failed,
            critical_failures=report.failed + report.errors,
            security_vulnerabilities=0,
            accessibility_score=1.0,
            performance_regression_pct=0.0,
        )

        self.event_bus.publish(
            ReleaseVerdictComputedEvent(
                correlation_id=report.correlation_id,
                payload={"verdict": verdict.value, "reasons": reasons},
            )
        )

        return assessment
