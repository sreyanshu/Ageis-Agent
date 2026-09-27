"""
Unit Tests for Aegis Quality Dimensions Contracts & Core Models
"""

import time
import pytest
from aegis.quality.models import (
    QualityDimension,
    QualityFinding,
    QualityEvidence,
    QualityResult,
    QualityStatus,
    ExecutionMode,
    ValidationStrength,
    FindingSeverity,
    BaselineStatus,
    PerformanceMeasurement,
    QualityBaseline,
    Waiver,
    EvidenceKind,
)
from aegis.evidence.models import TestStatus


def test_quality_finding_fingerprint_deterministic():
    f1 = QualityFinding(
        finding_id="f1",
        dimension=QualityDimension.SECURITY,
        severity=FindingSeverity.HIGH,
        category="sast",
        title="SQL Injection",
        description="Possible unescaped parameter in query",
        affected_target="users.py:45",
        provenance={"file_path": "users.py", "line_start": 45, "rule_id": "SEC001"},
    )
    fp1 = f1.compute_fingerprint()
    assert fp1.startswith("qf_")

    f2 = QualityFinding(
        finding_id="f2_diff_id",
        dimension=QualityDimension.SECURITY,
        severity=FindingSeverity.HIGH,
        category="sast",
        title="SQL Injection",
        description="Different description text",
        affected_target="users.py:45",
        provenance={"file_path": "users.py", "line_start": 45, "rule_id": "SEC001"},
    )
    fp2 = f2.compute_fingerprint()
    assert fp1 == fp2  # Same immutable properties generate identical fingerprint


def test_waiver_lifecycle_and_expiration():
    now = time.time()
    valid_waiver = Waiver(
        finding_fingerprint="qf_test123",
        dimension=QualityDimension.SECURITY,
        reason="Legacy internal endpoint pending refactor",
        owner="sec-team@example.com",
        created_timestamp=now,
        expiration_timestamp=now + 3600,  # 1 hour in future
    )
    assert not valid_waiver.is_expired()

    expired_waiver = Waiver(
        finding_fingerprint="qf_test456",
        dimension=QualityDimension.ACCESSIBILITY,
        reason="Temporary waiver for promo banner",
        owner="frontend-lead",
        created_timestamp=now - 7200,
        expiration_timestamp=now - 3600,  # Expired 1 hour ago
    )
    assert expired_waiver.is_expired()


def test_performance_measurement_statistics():
    samples = [100.0, 105.0, 102.0, 110.0, 98.0]
    pm = PerformanceMeasurement.from_samples(
        metric="api_latency_ms",
        samples=samples,
        unit="ms",
        env_fingerprint="env_abc123",
        tool_source="benchmark",
    )
    assert pm.sample_count == 5
    assert pm.median == 102.0
    assert pm.min_value == 98.0
    assert pm.max_value == 110.0
    assert pm.p95 == 110.0


def test_quality_result_to_test_result_conversion():
    qr = QualityResult(
        dimension=QualityDimension.ACCESSIBILITY,
        runner_id="aegis_accessibility_runner",
        status=QualityStatus.FAIL,
        execution_mode=ExecutionMode.REAL,
        validation_strength=ValidationStrength.AUTHORITATIVE,
        findings=[
            QualityFinding(
                finding_id="a1",
                dimension=QualityDimension.ACCESSIBILITY,
                severity=FindingSeverity.CRITICAL,
                category="accessibility",
                title="Missing Alt",
                description="Image missing alt attribute",
                affected_target="img.logo",
            )
        ],
        duration_ms=42.0,
    )
    tr = qr.to_test_result()
    assert tr.test_id == "quality.accessibility"
    assert tr.status == TestStatus.FAILED
    assert tr.deterministic_verdict is True
    assert tr.metadata["critical_findings"] == 1
