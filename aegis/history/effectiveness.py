"""
Aegis Test Effectiveness & Value Ranking Model
Quantifies historical defect detection rates, distinguishes real bugs from infra noise, and computes test value.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional

from aegis.history.models import (
    TestEffectivenessRecord,
    ExecutionRecord,
    FailureCategory,
    FlakinessRecord,
    FlakinessStatus,
)
from aegis.history.store import HistoryStore
from aegis.history.flakiness import FlakinessEngine


class TestEffectivenessEngine:
    """Computes test effectiveness metrics from historical execution evidence."""
    __test__ = False

    def __init__(self, store: HistoryStore) -> None:
        self.store = store
        self.flakiness_engine = FlakinessEngine(store)

    def analyze_test(self, test_id: str, limit: int = 100) -> TestEffectivenessRecord:
        records = self.store.get_executions(test_id=test_id, limit=limit)
        flakiness = self.flakiness_engine.compute_flakiness(test_id, records)
        return self.compute_effectiveness(test_id, records, flakiness)

    def compute_effectiveness(
        self,
        test_id: str,
        records: List[ExecutionRecord],
        flakiness: Optional[FlakinessRecord] = None,
    ) -> TestEffectivenessRecord:
        if not records:
            return TestEffectivenessRecord(
                test_id=test_id,
                category="unknown",
                value_score=50.0,
            )

        cat = records[0].category
        total_execs = len(records)
        failures = sum(1 for r in records if r.status in ("FAILED", "FAIL", "ERROR"))
        
        defects_detected = sum(
            1 for r in records if r.failure_category in (FailureCategory.PRODUCT_DEFECT, FailureCategory.CONFIGURATION)
        )
        false_infra = sum(
            1 for r in records if r.failure_category in (FailureCategory.INFRASTRUCTURE, FailureCategory.TIMEOUT, FailureCategory.NETWORK)
        )

        avg_dur = sum(r.duration_ms for r in records) / max(1, total_execs)

        # Cost score: 0.0 (fast, <=50ms) to 1.0 (slow, >=5000ms)
        cost_score = min(1.0, max(0.0, (avg_dur - 50.0) / 4950.0))
        defect_yield = defects_detected / max(1, total_execs)

        # Base value score (0 - 100)
        # 1. Defect yield contribution (up to 45 pts)
        score = 30.0 + (defect_yield * 45.0)
        # 2. Defect count bonus (up to 20 pts)
        score += min(20.0, defects_detected * 5.0)
        # 3. Cost penalty (up to -15 pts)
        score -= (cost_score * 15.0)
        # 4. Flakiness penalty (up to -20 pts)
        if flakiness and flakiness.status == FlakinessStatus.FLAKY:
            score -= 20.0
        elif flakiness and flakiness.status == FlakinessStatus.SUSPECTED_FLAKY:
            score -= 10.0

        clamped_score = max(5.0, min(100.0, round(score, 2)))

        last_defect = None
        for r in sorted(records, key=lambda x: x.timestamp, reverse=True):
            if r.failure_category == FailureCategory.PRODUCT_DEFECT:
                last_defect = r.timestamp
                break

        return TestEffectivenessRecord(
            test_id=test_id,
            category=cat,
            total_executions=total_execs,
            total_failures=failures,
            defects_detected=defects_detected,
            regressions_detected=defects_detected,
            false_infra_failures=false_infra,
            avg_duration_ms=round(avg_dur, 2),
            cost_score=round(cost_score, 3),
            defect_yield_rate=round(defect_yield, 3),
            value_score=clamped_score,
            last_defect_timestamp=last_defect,
        )

    def analyze_all(self, limit_per_test: int = 100) -> Dict[str, TestEffectivenessRecord]:
        all_execs = self.store.get_executions(limit=1000)
        test_ids = list({r.test_id for r in all_execs})
        results: Dict[str, TestEffectivenessRecord] = {}
        for tid in test_ids:
            results[tid] = self.analyze_test(tid, limit=limit_per_test)
        return results
