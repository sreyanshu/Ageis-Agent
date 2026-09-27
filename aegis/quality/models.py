"""
Aegis Quality Dimensions Unified Contracts & Models
Defines shared models, enums, findings, measurements, baselines, and results
for Accessibility, Security, Performance, and UX Heuristics.
"""

from __future__ import annotations
import time
import hashlib
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

from aegis.evidence.models import ArtifactRef, TestStatus, TestResult


class QualityDimension(str, Enum):
    ACCESSIBILITY = "accessibility"
    SECURITY = "security"
    PERFORMANCE = "performance"
    UX = "ux"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class QualityStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIPPED = "SKIPPED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EXECUTED = "NOT_EXECUTED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    SIMULATED = "SIMULATED"


class ExecutionMode(str, Enum):
    REAL = "REAL"
    SIMULATED = "SIMULATED"


class ValidationStrength(str, Enum):
    AUTHORITATIVE = "AUTHORITATIVE"
    PARTIAL = "PARTIAL"
    SIMULATED = "SIMULATED"


class EvidenceKind(str, Enum):
    OBSERVED = "OBSERVED"
    MEASURED = "MEASURED"
    SCANNED = "SCANNED"
    DERIVED = "DERIVED"
    SIMULATED = "SIMULATED"


class BaselineStatus(str, Enum):
    NEW = "NEW"
    REGRESSED = "REGRESSED"
    EXISTING = "EXISTING"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"
    WAIVED = "WAIVED"


class PerformanceTrend(str, Enum):
    IMPROVED = "IMPROVED"
    STABLE = "STABLE"
    REGRESSED = "REGRESSED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class QualityEvidence(BaseModel):
    """Concrete evidence record supporting a finding or measurement."""
    evidence_id: str
    kind: EvidenceKind
    description: str
    raw_data: Optional[Dict[str, Any]] = None
    artifact_ref: Optional[ArtifactRef] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class Waiver(BaseModel):
    """Explicit, policy-backed waiver for an existing finding."""
    finding_fingerprint: str
    dimension: QualityDimension
    reason: str
    owner: str
    created_timestamp: float = Field(default_factory=time.time)
    expiration_timestamp: Optional[float] = None
    policy_reference: Optional[str] = None

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        if self.expiration_timestamp is None:
            return False
        now = current_time or time.time()
        return now > self.expiration_timestamp


class QualityFinding(BaseModel):
    """Machine-verifiable quality issue or violation across any dimension."""
    finding_id: str
    dimension: QualityDimension
    severity: FindingSeverity
    category: str
    title: str
    description: str
    affected_target: str
    evidence: List[QualityEvidence] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    remediation_reference: Optional[str] = None
    fingerprint: str = ""
    first_seen: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)
    baseline_status: BaselineStatus = BaselineStatus.NEW
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def compute_fingerprint(self) -> str:
        """Generates deterministic fingerprint based on immutable properties."""
        src_file = self.provenance.get("file_path", "")
        line = str(self.provenance.get("line_start", ""))
        rule = str(self.provenance.get("rule_id", ""))
        raw = f"{self.dimension.value}:{self.category}:{rule}:{src_file}:{line}:{self.affected_target}"
        return f"qf_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


class PerformanceSample(BaseModel):
    iteration: int
    value: float
    timestamp: float = Field(default_factory=time.time)


class QualityMeasurement(BaseModel):
    """Generic quality metric measurement."""
    metric: str
    value: float
    unit: str = ""
    dimension: QualityDimension = QualityDimension.PERFORMANCE
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PerformanceMeasurement(BaseModel):
    """Deterministic performance measurement with sample distribution and environment context."""
    metric: str
    value: float
    unit: str
    sample_count: int = 1
    samples: List[float] = Field(default_factory=list)
    median: float = 0.0
    p95: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    environment_fingerprint: str = ""
    tool_source: str = "native"
    confidence: float = 1.0
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_samples(
        cls,
        metric: str,
        samples: List[float],
        unit: str,
        env_fingerprint: str,
        tool_source: str = "native",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PerformanceMeasurement:
        if not samples:
            return cls(
                metric=metric,
                value=0.0,
                unit=unit,
                sample_count=0,
                environment_fingerprint=env_fingerprint,
                tool_source=tool_source,
                metadata=metadata or {},
            )
        sorted_s = sorted(samples)
        count = len(sorted_s)
        med = sorted_s[count // 2] if count % 2 != 0 else (sorted_s[count // 2 - 1] + sorted_s[count // 2]) / 2.0
        p95_idx = int(0.95 * count)
        p95_val = sorted_s[min(p95_idx, count - 1)]
        return cls(
            metric=metric,
            value=med,
            unit=unit,
            sample_count=count,
            samples=samples,
            median=med,
            p95=p95_val,
            min_value=sorted_s[0],
            max_value=sorted_s[-1],
            environment_fingerprint=env_fingerprint,
            tool_source=tool_source,
            metadata=metadata or {},
        )


class QualityBaseline(BaseModel):
    """Persistent reference baseline for quality comparisons."""
    dimension: QualityDimension
    baseline_id: str
    tree_hash: str
    environment_fingerprint: str = ""
    created_at: float = Field(default_factory=time.time)
    findings_fingerprints: List[str] = Field(default_factory=list)
    measurements: Dict[str, float] = Field(default_factory=dict)
    waivers: List[Waiver] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QualityCapability(BaseModel):
    """Declarative capability of a quality runner."""
    dimension: QualityDimension
    name: str
    version: str = "1.0.0"
    supported_adapters: List[str] = Field(default_factory=list)
    requires_browser: bool = False
    requires_network: bool = False
    supports_baselines: bool = True
    supports_waivers: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QualityResult(BaseModel):
    """Machine-verifiable outcome of a Quality Dimension execution."""
    dimension: QualityDimension
    runner_id: str
    status: QualityStatus
    execution_mode: ExecutionMode = ExecutionMode.REAL
    validation_strength: ValidationStrength = ValidationStrength.AUTHORITATIVE
    findings: List[QualityFinding] = Field(default_factory=list)
    measurements: List[PerformanceMeasurement] = Field(default_factory=list)
    evidence: List[QualityEvidence] = Field(default_factory=list)
    confidence: float = 1.0
    provenance: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    environment: Dict[str, Any] = Field(default_factory=dict)
    tool_version: Optional[str] = None
    baseline_status: Optional[str] = None
    comparison_summary: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None

    def to_test_result(self) -> TestResult:
        """Adapts QualityResult into the global Aegis TestResult contract."""
        test_status_map = {
            QualityStatus.PASS: TestStatus.PASSED,
            QualityStatus.FAIL: TestStatus.FAILED,
            QualityStatus.WARN: TestStatus.PASSED,
            QualityStatus.SKIPPED: TestStatus.SKIPPED,
            QualityStatus.NOT_APPLICABLE: TestStatus.PASSED,
            QualityStatus.NOT_EXECUTED: TestStatus.SKIPPED,
            QualityStatus.UNAVAILABLE: TestStatus.ERROR,
            QualityStatus.ERROR: TestStatus.ERROR,
            QualityStatus.SIMULATED: TestStatus.PASSED,
        }
        st = test_status_map.get(self.status, TestStatus.ERROR)
        critical_count = sum(1 for f in self.findings if f.severity == FindingSeverity.CRITICAL)
        high_count = sum(1 for f in self.findings if f.severity == FindingSeverity.HIGH)
        
        stdout_summary = (
            f"[{self.dimension.value.upper()}] Status: {self.status.value} "
            f"(Mode: {self.execution_mode.value}, Strength: {self.validation_strength.value})\n"
            f"Findings: {len(self.findings)} (Critical: {critical_count}, High: {high_count})\n"
            f"Measurements: {len(self.measurements)}"
        )

        return TestResult(
            test_id=f"quality.{self.dimension.value}",
            name=f"Quality Dimension: {self.dimension.value.capitalize()}",
            suite="quality",
            category=self.dimension.value,
            status=st,
            duration_ms=self.duration_ms,
            runner=self.runner_id,
            raw_stdout=stdout_summary,
            raw_stderr=self.error_message,
            confidence=self.confidence,
            deterministic_verdict=self.validation_strength == ValidationStrength.AUTHORITATIVE,
            metadata={
                "quality_status": self.status.value,
                "execution_mode": self.execution_mode.value,
                "validation_strength": self.validation_strength.value,
                "findings_count": len(self.findings),
                "critical_findings": critical_count,
                "high_findings": high_count,
                "comparison": self.comparison_summary,
            },
        )
