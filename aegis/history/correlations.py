"""
Aegis Change-to-Failure Historical Correlation Engine
Maps symbol and file modifications to historical failure clusters to power predictive test selection.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional

from aegis.history.models import ChangeFailureCorrelation, ExecutionRecord, FailureCategory
from aegis.history.store import HistoryStore


class CorrelationEngine:
    """Discovers empirical relationships between source changes and subsequent failures."""

    def __init__(self, store: HistoryStore) -> None:
        self.store = store

    def record_change_failure_link(
        self,
        symbol_name: str,
        file_path: str,
        failure_fingerprint: str,
        test_id: str,
    ) -> None:
        corr = ChangeFailureCorrelation(
            symbol_name=symbol_name,
            file_path=file_path,
            failure_fingerprint=failure_fingerprint,
            test_id=test_id,
            co_occurrence_count=1,
            confidence=0.7,
            last_observed=time.time(),
        )
        self.store.save_correlation(corr)

    def find_correlated_tests(self, changed_symbols: List[str]) -> Dict[str, float]:
        """
        Returns mapping of test_id -> correlation confidence for a set of modified symbols.
        """
        correlated: Dict[str, float] = {}
        for sym in changed_symbols:
            corrs = self.store.get_correlations(symbol=sym)
            for c in corrs:
                # Accumulate correlation strength
                prev = correlated.get(c.test_id, 0.0)
                boost = min(0.95, c.confidence * (1.0 + (0.1 * min(c.co_occurrence_count, 5))))
                correlated[c.test_id] = max(prev, boost)
        return correlated
