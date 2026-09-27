"""
Aegis Historical Data Retention & Privacy Management
Prunes stale execution data while preserving necessary audit and release evidence.
"""

from __future__ import annotations
import time
from typing import Dict, Any, Optional

from aegis.history.store import HistoryStore


class RetentionManager:
    """Manages history lifecycle and storage bounds."""

    def __init__(self, store: HistoryStore, max_age_days: int = 90, max_records: int = 50000) -> None:
        self.store = store
        self.max_age_days = max_age_days
        self.max_records = max_records

    def enforce_retention(self) -> Dict[str, int]:
        """Runs pruning pass based on configured age and record thresholds."""
        deleted = self.store.prune_older_than(
            max_age_seconds=self.max_age_days * 86400,
            max_records=self.max_records,
        )
        return {"pruned_execution_records": deleted}
