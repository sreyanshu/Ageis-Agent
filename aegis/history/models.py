"""
Aegis Historical Intelligence & Optimization Engine Models
Defines execution history records, failure clusters, flakiness metrics, test effectiveness,
redundancy analysis, and change-to-failure correlation schemas.
"""

from __future__ import annotations
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    PRODUCT_DEFECT = "PRODUCT_DEFECT"
    TEST_DEFECT = "TEST_DEFECT"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    ENVIRONMENT = "ENVIRONMENT"
    DEPENDENCY = "DEPENDENCY"
    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    CONFIGURATION = "CONFIGURATION"
    UNKNOWN = "UNKNOWN"


class FailureStatus(str, Enum):
    NEW_FAILURE = "NEW_FAILURE"
    RECURRING_FAILURE = "RECURRING_FAILURE"
    RESOLVED_FAILURE = "RESOLVED_FAILURE"
    REGRESSED_FAILURE = "REGRESSED_FAILURE"
    FLAKY_FAILURE = "FLAKY_FAILURE"


class FlakinessStatus(str, Enum):
    STABLE = "STABLE"
    SUSPECTED_FLAKY = "SUSPECTED_FLAKY"
    FLAKY = "FLAKY"
    UNKNOWN = "UNKNOWN"


class QualityFindingStatus(str, Enum):
    NEW = "NEW"
    EXISTING = "EXISTING"
    RESOLVED = "RESOLVED"
    REGRESSED = "REGRESSED"
    REINTRODUCED = "REINTRODUCED"


class ExecutionRecord(BaseModel):
    """Normalized, compact record of a single test or quality execution."""
    execution_id: str
    run_id: str
    timestamp: float = Field(default_factory=time.time)
    project_name: str
    commit_or_tree_hash: str
    test_id: str
    category: str
    status: str  # PASSED, FAILED, ERROR, TIMEOUT, SKIPPED, etc.
    duration_ms: float = 0.0
    retry_count: int = 0
    execution_mode: str = "REAL"
    environment_fingerprint: str = ""
    failure_fingerprint: Optional[str] = None
    failure_category: Optional[FailureCategory] = None
    risk_level: Optional[str] = None
    affected_symbols: List[str] = Field(default_factory=list)
    evidence_ref: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FailureCluster(BaseModel):
    """Group of failures sharing an identical normalized failure fingerprint."""
    fingerprint: str
    first_seen: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)
    occurrences: int = 1
    status: FailureStatus = FailureStatus.NEW_FAILURE
    classification: FailureCategory = FailureCategory.UNKNOWN
    confidence: float = 1.0
    affected_tests: List[str] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)
    environments: List[str] = Field(default_factory=list)
    sample_message: str = ""
    sample_stack_frame: Optional[str] = None
    resolved_at: Optional[float] = None


class FlakinessRecord(BaseModel):
    """Deterministic flakiness metrics for a specific test across history."""
    test_id: str
    total_runs: int = 0
    pass_count: int = 0
    fail_count: int = 0
    retry_count: int = 0
    instability_rate: float = 0.0
    status: FlakinessStatus = FlakinessStatus.UNKNOWN
    confidence: float = 1.0
    recent_outcomes: List[str] = Field(default_factory=list)  # E.g. ["P", "F", "P", "P"]
    environments_affected: List[str] = Field(default_factory=list)


class TestEffectivenessRecord(BaseModel):
    """Quantified historical defect-detection value and execution cost of a test."""
    __test__ = False
    test_id: str
    category: str
    total_executions: int = 0
    total_failures: int = 0
    defects_detected: int = 0
    regressions_detected: int = 0
    false_infra_failures: int = 0
    avg_duration_ms: float = 0.0
    cost_score: float = 0.0           # 0.0 (fastest) - 1.0 (slowest)
    defect_yield_rate: float = 0.0    # defects_detected / max(1, total_executions)
    value_score: float = 0.0          # Multi-factor ranking score (0.0 - 100.0)
    last_defect_timestamp: Optional[float] = None


class RedundancyRecord(BaseModel):
    """Identifies overlapping test validations providing redundant coverage."""
    test_id_a: str
    test_id_b: str
    overlap_score: float = 0.0  # 0.0 - 1.0
    shared_symbols: List[str] = Field(default_factory=list)
    shared_failure_fingerprints: List[str] = Field(default_factory=list)
    recommendation: str = "Keep both or review for consolidation"


class ChangeFailureCorrelation(BaseModel):
    """Statistical association between modified code symbols and test failures."""
    symbol_name: str
    file_path: str
    failure_fingerprint: str
    test_id: str
    co_occurrence_count: int = 1
    confidence: float = 1.0
    last_observed: float = Field(default_factory=time.time)


class QualityHistoryRecord(BaseModel):
    """Lifecycle tracking of a quality dimension finding across multiple runs."""
    finding_fingerprint: str
    dimension: str
    rule_id: str
    affected_target: str
    severity: str
    status: QualityFindingStatus = QualityFindingStatus.NEW
    first_seen: float = Field(default_factory=time.time)
    last_seen: float = Field(default_factory=time.time)
    occurrences: int = 1
    history_events: List[Dict[str, Any]] = Field(default_factory=list)


class RiskCalibrationRecord(BaseModel):
    """Comparison of predicted risk score vs observed validation outcomes."""
    risk_level: str
    predicted_count: int = 0
    observed_failure_count: int = 0
    failure_rate: float = 0.0
    calibration_factor: float = 1.0  # 1.0 = balanced, >1 = under-predicting, <1 = over-predicting


class SelectionExplanation(BaseModel):
    """Explainable rationale for test selection or skipping in Adaptive Planner 2.0."""
    test_id: str
    selected: bool
    priority: int
    value_score: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    skip_reason: Optional[str] = None
    estimated_duration_ms: float = 0.0
