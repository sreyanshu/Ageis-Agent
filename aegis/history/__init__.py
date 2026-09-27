"""
Aegis Historical Intelligence & Optimization Engine Package
"""

from aegis.history.models import (
    FailureCategory,
    FailureStatus,
    FlakinessStatus,
    QualityFindingStatus,
    ExecutionRecord,
    FailureCluster,
    FlakinessRecord,
    TestEffectivenessRecord,
    RedundancyRecord,
    ChangeFailureCorrelation,
    QualityHistoryRecord,
    RiskCalibrationRecord,
    SelectionExplanation,
)
from aegis.history.store import HistoryStore
from aegis.history.failures import FailureClassifier, FailureIntelligenceEngine
from aegis.history.flakiness import FlakinessEngine
from aegis.history.effectiveness import TestEffectivenessEngine
from aegis.history.redundancy import RedundancyEngine
from aegis.history.correlations import CorrelationEngine
from aegis.history.quality_history import QualityHistoryEngine
from aegis.history.retention import RetentionManager
from aegis.history.reasoning import ReasoningProvider, DeterministicReasoningProvider

__all__ = [
    "FailureCategory",
    "FailureStatus",
    "FlakinessStatus",
    "QualityFindingStatus",
    "ExecutionRecord",
    "FailureCluster",
    "FlakinessRecord",
    "TestEffectivenessRecord",
    "RedundancyRecord",
    "ChangeFailureCorrelation",
    "QualityHistoryRecord",
    "RiskCalibrationRecord",
    "SelectionExplanation",
    "HistoryStore",
    "FailureClassifier",
    "FailureIntelligenceEngine",
    "FlakinessEngine",
    "TestEffectivenessEngine",
    "RedundancyEngine",
    "CorrelationEngine",
    "QualityHistoryEngine",
    "RetentionManager",
    "ReasoningProvider",
    "DeterministicReasoningProvider",
]
