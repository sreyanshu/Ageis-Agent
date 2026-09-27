"""
Aegis Historical Quality Intelligence Engine
Tracks quality finding recurrence, reintroductions, and resolution lifecycle over time.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional

from aegis.history.models import QualityHistoryRecord, QualityFindingStatus
from aegis.history.store import HistoryStore
from aegis.quality.models import QualityFinding, BaselineStatus


class QualityHistoryEngine:
    """Maintains long-term history of accessibility, security, performance, and UX issues."""

    def __init__(self, store: HistoryStore) -> None:
        self.store = store

    def process_quality_findings(self, findings: List[QualityFinding], run_id: str = "") -> List[QualityHistoryRecord]:
        """
        Updates quality history records, detecting if a previously resolved issue is REINTRODUCED.
        """
        now = time.time()
        updated_records: List[QualityHistoryRecord] = []
        current_fps = {f.fingerprint for f in findings}

        # 1. Update active findings
        for f in findings:
            existing = self.store.get_quality_history(fingerprint=f.fingerprint)
            rec: QualityHistoryRecord
            if existing:
                rec = existing[0]
                rec.last_seen = now
                rec.occurrences += 1
                if rec.status == QualityFindingStatus.RESOLVED:
                    rec.status = QualityFindingStatus.REINTRODUCED
                    f.baseline_status = BaselineStatus.REGRESSED
                else:
                    rec.status = QualityFindingStatus.EXISTING
                rec.history_events.append({"event": rec.status.value, "timestamp": now, "run_id": run_id})
            else:
                rec = QualityHistoryRecord(
                    finding_fingerprint=f.fingerprint,
                    dimension=f.dimension.value,
                    rule_id=str(f.provenance.get("rule_id", f.category)),
                    affected_target=f.affected_target,
                    severity=f.severity.value,
                    status=QualityFindingStatus.NEW,
                    first_seen=now,
                    last_seen=now,
                    occurrences=1,
                    history_events=[{"event": "DISCOVERED", "timestamp": now, "run_id": run_id}],
                )
            self.store.save_quality_history(rec)
            updated_records.append(rec)

        # 2. Check previously tracked findings that are now absent (mark as RESOLVED)
        all_tracked = self.store.get_quality_history(limit=500)
        for tracked in all_tracked:
            if tracked.finding_fingerprint not in current_fps and tracked.status in (
                QualityFindingStatus.NEW,
                QualityFindingStatus.EXISTING,
                QualityFindingStatus.REINTRODUCED,
            ):
                tracked.status = QualityFindingStatus.RESOLVED
                tracked.history_events.append({"event": "RESOLVED", "timestamp": now, "run_id": run_id})
                self.store.save_quality_history(tracked)
                updated_records.append(tracked)

        return updated_records
