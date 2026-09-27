"""
Aegis Evidence Collector
Aggregates individual test results, correlates traces, stores raw artifacts, and generates reproducible reports.
"""

from __future__ import annotations
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from aegis.core.events import EventBus, EvidenceRecordedEvent, FailureFingerprintedEvent, generate_id
from aegis.evidence.models import TestResult, TestStatus, EvidenceReport, ReleaseAssessment, ArtifactRef
from aegis.evidence.normalizer import FailureNormalizer
from aegis.storage.base import StorageBackend


class EvidenceCollector:
    """Collects and correlates raw evidence and test executions."""

    def __init__(
        self,
        project_name: str,
        correlation_id: Optional[str] = None,
        storage: Optional[StorageBackend] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.project_name = project_name
        self.correlation_id = correlation_id or generate_id("corr")
        self.storage = storage
        self.event_bus = event_bus
        self.results: List[TestResult] = []
        self._fingerprints: Set[str] = set()

    def record_result(self, result: TestResult) -> None:
        """Processes and records a single test result, computing fingerprints if failed."""
        if result.status in (TestStatus.FAILED, TestStatus.ERROR, TestStatus.TIMEOUT):
            if not result.normalized_error and (result.raw_stderr or result.raw_stdout):
                err_text = result.raw_stderr or result.raw_stdout or "Unknown failure"
                norm_err = FailureNormalizer.normalize_failure(err_text, category=result.category)
                result.normalized_error = norm_err
                result.failure_fingerprint = norm_err.fingerprint

            if result.failure_fingerprint:
                self._fingerprints.add(result.failure_fingerprint)
                if self.event_bus:
                    self.event_bus.publish(
                        FailureFingerprintedEvent(
                            correlation_id=self.correlation_id,
                            payload={"fingerprint": result.failure_fingerprint, "test_id": result.test_id},
                        )
                    )

        # Store stdout/stderr as artifacts if present and storage is attached
        if self.storage and (result.raw_stdout or result.raw_stderr):
            safe_id = "".join(c if c.isalnum() or c in "_-" else "_" for c in result.test_id)
            if result.raw_stdout:
                stdout_rel = f"artifacts/{safe_id}_stdout.log"
                self.storage.save_raw_artifact(stdout_rel, result.raw_stdout)
                result.artifacts.append(
                    ArtifactRef(kind="stdout", path=stdout_rel, size_bytes=len(result.raw_stdout.encode("utf-8")))
                )
            if result.raw_stderr:
                stderr_rel = f"artifacts/{safe_id}_stderr.log"
                self.storage.save_raw_artifact(stderr_rel, result.raw_stderr)
                result.artifacts.append(
                    ArtifactRef(kind="stderr", path=stderr_rel, size_bytes=len(result.raw_stderr.encode("utf-8")))
                )

        self.results.append(result)

        if self.event_bus:
            self.event_bus.publish(
                EvidenceRecordedEvent(
                    correlation_id=self.correlation_id,
                    payload={"test_id": result.test_id, "status": result.status.value},
                )
            )

    def generate_report(
        self,
        tree_hash: str = "",
        release_assessment: Optional[ReleaseAssessment] = None,
    ) -> EvidenceReport:
        """Compiles recorded test outcomes into a machine-readable summary EvidenceReport."""
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)
        errors = sum(1 for r in self.results if r.status in (TestStatus.ERROR, TestStatus.TIMEOUT))
        total_duration = sum(r.duration_ms for r in self.results)

        report = EvidenceReport(
            report_id=generate_id("rep"),
            correlation_id=self.correlation_id,
            project_name=self.project_name,
            tree_hash=tree_hash,
            total_tests=len(self.results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration_ms=total_duration,
            test_results=self.results,
            failure_fingerprints=sorted(list(self._fingerprints)),
            release_assessment=release_assessment,
        )

        if self.storage:
            self.storage.save_json("report.json", report.model_dump())

        return report
