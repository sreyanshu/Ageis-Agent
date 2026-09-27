"""
Aegis Adaptive Planning and Risk Data Models
"""

from __future__ import annotations
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskFactor(BaseModel):
    """An individual explainable factor contributing to the aggregate risk score."""
    factor_name: str
    weight: float
    raw_score: float                         # Normalized score (0.0 to 1.0)
    weighted_score: float                    # weight * raw_score
    evidence: str                            # Concrete provenance proof


class RiskAssessment(BaseModel):
    """Deterministic, explainable risk assessment for a software change."""
    level: RiskLevel
    composite_score: float                   # 0.0 (minimal risk) to 1.0 (extreme risk)
    generated_at: float = Field(default_factory=time.time)
    factors: List[RiskFactor] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    recommendation: str


class PlannedTest(BaseModel):
    """A test selected for execution with priority and selection rationale."""
    __test__ = False
    test_id: str
    name: str
    category: str                            # unit, api, sanity, integration, e2e, ui
    runner_cmd: str
    priority: int = 50                       # 0 (lowest) to 100 (highest)
    selection_reason: str = "Planned validation"
    estimated_duration_ms: float = 100.0


class SkippedTest(BaseModel):
    """A test safely deferred/skipped based on lack of impact and low risk."""
    __test__ = False
    test_id: str
    name: str
    category: str
    skip_reason: str


class TestPlan(BaseModel):
    """Deterministic, risk-weighted test execution plan."""
    __test__ = False
    plan_id: str
    timestamp: float = Field(default_factory=time.time)
    risk_level: RiskLevel
    selected_tests: List[PlannedTest] = Field(default_factory=list)
    skipped_tests: List[SkippedTest] = Field(default_factory=list)
    total_planned: int = 0
    total_skipped: int = 0
    estimated_total_time_ms: float = 0.0
    explanations: List[Any] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
