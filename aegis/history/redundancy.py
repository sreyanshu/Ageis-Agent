"""
Aegis Test Redundancy Detection Engine
Identifies duplicate or heavily overlapping test suites based on shared symbols and failure patterns.
"""

from __future__ import annotations
from typing import Dict, Any, List, Set, Tuple

from aegis.history.models import RedundancyRecord, ExecutionRecord
from aegis.history.store import HistoryStore


class RedundancyEngine:
    """Detects possible test redundancy without automatically deleting any tests."""

    def __init__(self, store: HistoryStore) -> None:
        self.store = store

    def analyze_redundancy(self, limit: int = 500) -> List[RedundancyRecord]:
        execs = self.store.get_executions(limit=limit)
        
        # Group symbols and failure fingerprints by test_id
        test_symbols: Dict[str, Set[str]] = {}
        test_fps: Dict[str, Set[str]] = {}

        for r in execs:
            if r.test_id not in test_symbols:
                test_symbols[r.test_id] = set()
                test_fps[r.test_id] = set()
            for s in r.affected_symbols:
                test_symbols[r.test_id].add(s)
            if r.failure_fingerprint:
                test_fps[r.test_id].add(r.failure_fingerprint)

        test_ids = sorted(list(test_symbols.keys()))
        redundancies: List[RedundancyRecord] = []

        for i in range(len(test_ids)):
            for j in range(i + 1, len(test_ids)):
                tid_a = test_ids[i]
                tid_b = test_ids[j]

                syms_a = test_symbols[tid_a]
                syms_b = test_symbols[tid_b]
                fps_a = test_fps[tid_a]
                fps_b = test_fps[tid_b]

                if not syms_a or not syms_b:
                    continue

                shared_syms = syms_a.intersection(syms_b)
                total_syms = syms_a.union(syms_b)
                sym_overlap = len(shared_syms) / max(1, len(total_syms))

                shared_fps = fps_a.intersection(fps_b) if (fps_a and fps_b) else set()
                fp_overlap = len(shared_fps) / max(1, len(fps_a.union(fps_b))) if (fps_a and fps_b) else 0.0

                composite_overlap = round((0.7 * sym_overlap) + (0.3 * fp_overlap), 3)

                if composite_overlap >= 0.70:
                    redundancies.append(
                        RedundancyRecord(
                            test_id_a=tid_a,
                            test_id_b=tid_b,
                            overlap_score=composite_overlap,
                            shared_symbols=sorted(list(shared_syms))[:5],
                            shared_failure_fingerprints=sorted(list(shared_fps))[:3],
                            recommendation="High overlap in covered symbols and failure clusters. Review for potential consolidation.",
                        )
                    )

        return sorted(redundancies, key=lambda r: r.overlap_score, reverse=True)
