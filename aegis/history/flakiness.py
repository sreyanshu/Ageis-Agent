"""
Aegis Flakiness Analysis Engine
Deterministic evaluation of test outcome volatility across historical execution runs.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional

from aegis.history.models import FlakinessRecord, FlakinessStatus, ExecutionRecord
from aegis.history.store import HistoryStore


class FlakinessEngine:
    """Evaluates test stability and identifies non-deterministic flakiness."""

    def __init__(self, store: HistoryStore, min_samples: int = 4) -> None:
        self.store = store
        self.min_samples = min_samples

    def analyze_test(self, test_id: str, limit: int = 50) -> FlakinessRecord:
        """Analyzes historical runs of a single test to evaluate its flakiness profile."""
        records = self.store.get_executions(test_id=test_id, limit=limit)
        return self.compute_flakiness(test_id, records)

    def compute_flakiness(self, test_id: str, records: List[ExecutionRecord]) -> FlakinessRecord:
        if not records or len(records) < self.min_samples:
            return FlakinessRecord(
                test_id=test_id,
                total_runs=len(records),
                pass_count=sum(1 for r in records if r.status in ("PASSED", "PASS")),
                fail_count=sum(1 for r in records if r.status in ("FAILED", "FAIL", "ERROR")),
                retry_count=sum(r.retry_count for r in records),
                instability_rate=0.0,
                status=FlakinessStatus.UNKNOWN,
                confidence=0.5,
                recent_outcomes=[r.status[:1] for r in records[:10]],
            )

        # Sort chronologically
        chronological = sorted(records, key=lambda r: r.timestamp)
        pass_count = sum(1 for r in chronological if r.status in ("PASSED", "PASS"))
        fail_count = sum(1 for r in chronological if r.status in ("FAILED", "FAIL", "ERROR"))
        retry_count = sum(r.retry_count for r in chronological)

        # Calculate state transitions (e.g. PASS -> FAIL or FAIL -> PASS)
        transitions = 0
        for i in range(len(chronological) - 1):
            curr_pass = chronological[i].status in ("PASSED", "PASS")
            next_pass = chronological[i + 1].status in ("PASSED", "PASS")
            if curr_pass != next_pass:
                transitions += 1

        total_possible_transitions = max(1, len(chronological) - 1)
        instability_rate = round(transitions / total_possible_transitions, 3)

        environments = list({r.environment_fingerprint for r in chronological if r.environment_fingerprint})

        # Determine status
        status: FlakinessStatus
        if retry_count > 0 or (instability_rate >= 0.25 and pass_count > 0 and fail_count > 0):
            status = FlakinessStatus.FLAKY
        elif instability_rate >= 0.10 and pass_count > 0 and fail_count > 0:
            status = FlakinessStatus.SUSPECTED_FLAKY
        else:
            status = FlakinessStatus.STABLE

        conf = min(1.0, 0.6 + (0.1 * min(len(chronological), 4)))

        return FlakinessRecord(
            test_id=test_id,
            total_runs=len(chronological),
            pass_count=pass_count,
            fail_count=fail_count,
            retry_count=retry_count,
            instability_rate=instability_rate,
            status=status,
            confidence=conf,
            recent_outcomes=[r.status[:1] for r in chronological[-10:]],
            environments_affected=environments,
        )

    def analyze_all(self, limit_per_test: int = 50) -> Dict[str, FlakinessRecord]:
        """Analyzes all known tests in the execution history."""
        all_execs = self.store.get_executions(limit=1000)
        test_ids = list({r.test_id for r in all_execs})
        results: Dict[str, FlakinessRecord] = {}
        for tid in test_ids:
            results[tid] = self.analyze_test(tid, limit=limit_per_test)
        return results
