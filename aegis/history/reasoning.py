"""
Aegis AI Reasoning Boundary & Investigation Provider
Defines the clean boundary interface for future LLM integration with token-efficient compression.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from aegis.history.models import FailureCluster, ExecutionRecord, TestEffectivenessRecord
from aegis.history.store import HistoryStore


class ReasoningProvider(ABC):
    """Abstract interface for failure explanation and historical summarization."""

    @abstractmethod
    def explain_failure(self, cluster: FailureCluster) -> Dict[str, Any]:
        pass

    @abstractmethod
    def summarize_history(self, records: List[ExecutionRecord]) -> str:
        pass


class DeterministicReasoningProvider(ReasoningProvider):
    """Zero-LLM deterministic implementation using structured historical facts and heuristics."""

    def __init__(self, store: Optional[HistoryStore] = None) -> None:
        self.store = store

    def explain_failure(self, cluster: FailureCluster) -> Dict[str, Any]:
        """Provides concise, deterministic explanation for a failure cluster."""
        rec_status = cluster.status.value
        cls_name = cluster.classification.value
        explanation = (
            f"Failure [{cluster.fingerprint}] classified as {cls_name} (Confidence: {cluster.confidence:.2f}). "
            f"Observed {cluster.occurrences} time(s) across {len(cluster.affected_tests)} test(s). "
            f"Current state: {rec_status}."
        )

        suggested_action: str
        if cls_name == "PRODUCT_DEFECT":
            suggested_action = "Inspect recent changes to application code in affected component."
        elif cls_name == "INFRASTRUCTURE":
            suggested_action = "Check local daemon/container status or runner tool availability."
        elif cls_name == "TIMEOUT":
            suggested_action = "Profile slow dependencies or increase execution timeout bounds."
        elif cls_name == "DEPENDENCY":
            suggested_action = "Verify installed package requirements or lockfile versions."
        else:
            suggested_action = "Review normalized stack frame for unexpected exception origins."

        return {
            "fingerprint": cluster.fingerprint,
            "classification": cls_name,
            "status": rec_status,
            "occurrences": cluster.occurrences,
            "explanation": explanation,
            "suggested_action": suggested_action,
            "affected_tests": cluster.affected_tests,
        }

    def summarize_history(self, records: List[ExecutionRecord]) -> str:
        """Compresses execution records into a token-efficient summary."""
        if not records:
            return "No historical execution records found."
        total = len(records)
        passes = sum(1 for r in records if r.status in ("PASSED", "PASS"))
        fails = sum(1 for r in records if r.status in ("FAILED", "FAIL", "ERROR"))
        pass_rate = (passes / max(1, total)) * 100

        unique_fps = {r.failure_fingerprint for r in records if r.failure_fingerprint}

        return (
            f"History summary: {total} execution(s) recorded across project. "
            f"Pass rate: {pass_rate:.1f}% ({passes} passed, {fails} failed). "
            f"{len(unique_fps)} unique failure fingerprint(s) observed."
        )
