"""
Aegis Evidence & Machine-Verifiable Result Models
"""

from __future__ import annotations
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TestStatus(str, Enum):
    __test__ = False
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class ReleaseGateVerdict(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class ArtifactRef(BaseModel):
    """Reference to an external artifact stored in .aegis/artifacts/."""
    kind: str  # stdout, stderr, screenshot, trace, http_dump, har, a11y_tree, sarif
    path: str
    size_bytes: int = 0
    mime_type: str = "text/plain"


class NormalizedError(BaseModel):
    """Normalized, deduplicated failure representation."""
    exception_type: str
    message: str
    top_stack_frame: Optional[str] = None
    fingerprint: str = ""


class TestResult(BaseModel):
    """Machine-verifiable outcome of a single test or validation step."""
    __test__ = False
    test_id: str
    name: str
    suite: str = "default"
    category: str = "unit"  # unit, api, sanity, integration, e2e, ui, ux, a11y, security, perf
    status: TestStatus
    duration_ms: float = 0.0
    runner: str = "native"
    failure_fingerprint: Optional[str] = None
    normalized_error: Optional[NormalizedError] = None
    raw_stdout: Optional[str] = None
    raw_stderr: Optional[str] = None
    artifacts: List[ArtifactRef] = Field(default_factory=list)
    confidence: float = 1.0
    deterministic_verdict: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PolicyCheckResult(BaseModel):
    policy_name: str
    passed: bool
    details: str
    evidence_ref: Optional[str] = None


class ReleaseAssessment(BaseModel):
    """Deterministic release readiness determination."""
    verdict: ReleaseGateVerdict
    generated_at: float = Field(default_factory=time.time)
    policy_checks: List[PolicyCheckResult] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    critical_failures: int = 0
    security_vulnerabilities: int = 0
    accessibility_score: float = 1.0
    performance_regression_pct: float = 0.0


class EvidenceReport(BaseModel):
    """Consolidated report artifact summarizing complete test execution and release readiness."""
    report_id: str
    correlation_id: str
    project_name: str
    created_at: float = Field(default_factory=time.time)
    tree_hash: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: float = 0.0
    test_results: List[TestResult] = Field(default_factory=list)
    failure_fingerprints: List[str] = Field(default_factory=list)
    release_assessment: Optional[ReleaseAssessment] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
