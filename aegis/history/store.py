"""
Aegis Persistent Historical Knowledge Store (SQLite & Multi-Index)
Provides durable storage, retrieval, temporal queries, and retention pruning for historical executions.
"""

from __future__ import annotations
import sqlite3
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from aegis.history.models import (
    ExecutionRecord,
    FailureCluster,
    FailureCategory,
    FailureStatus,
    ChangeFailureCorrelation,
    QualityHistoryRecord,
    QualityFindingStatus,
)


class HistoryStore:
    """Thread-safe persistent historical intelligence store."""

    def __init__(self, storage_dir: Path | str) -> None:
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_dir / "history.db"
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    project_name TEXT NOT NULL,
                    commit_or_tree_hash TEXT NOT NULL,
                    test_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    execution_mode TEXT DEFAULT 'REAL',
                    environment_fingerprint TEXT,
                    failure_fingerprint TEXT,
                    failure_category TEXT,
                    risk_level TEXT,
                    affected_symbols_json TEXT,
                    evidence_ref TEXT,
                    metadata_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_exec_test_id ON executions(test_id);
                CREATE INDEX IF NOT EXISTS idx_exec_timestamp ON executions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_exec_fp ON executions(failure_fingerprint);

                CREATE TABLE IF NOT EXISTS failure_clusters (
                    fingerprint TEXT PRIMARY KEY,
                    first_seen REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    occurrences INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    affected_tests_json TEXT,
                    affected_components_json TEXT,
                    environments_json TEXT,
                    sample_message TEXT,
                    sample_stack_frame TEXT,
                    resolved_at REAL
                );

                CREATE TABLE IF NOT EXISTS correlations (
                    symbol_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    failure_fingerprint TEXT NOT NULL,
                    test_id TEXT NOT NULL,
                    co_occurrence_count INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    last_observed REAL NOT NULL,
                    PRIMARY KEY (symbol_name, failure_fingerprint, test_id)
                );

                CREATE TABLE IF NOT EXISTS quality_history (
                    finding_fingerprint TEXT PRIMARY KEY,
                    dimension TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    affected_target TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    first_seen REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    occurrences INTEGER NOT NULL,
                    events_json TEXT
                );
                """
            )

    def record_execution(self, rec: ExecutionRecord) -> None:
        self.record_executions([rec])

    def record_executions(self, records: List[ExecutionRecord]) -> None:
        if not records:
            return
        with self._get_connection() as conn:
            for rec in records:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO executions (
                        execution_id, run_id, timestamp, project_name, commit_or_tree_hash,
                        test_id, category, status, duration_ms, retry_count, execution_mode,
                        environment_fingerprint, failure_fingerprint, failure_category,
                        risk_level, affected_symbols_json, evidence_ref, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rec.execution_id,
                        rec.run_id,
                        rec.timestamp,
                        rec.project_name,
                        rec.commit_or_tree_hash,
                        rec.test_id,
                        rec.category,
                        rec.status,
                        rec.duration_ms,
                        rec.retry_count,
                        rec.execution_mode,
                        rec.environment_fingerprint,
                        rec.failure_fingerprint,
                        rec.failure_category.value if rec.failure_category else None,
                        rec.risk_level,
                        json.dumps(rec.affected_symbols),
                        rec.evidence_ref,
                        json.dumps(rec.metadata),
                    ),
                )
            conn.commit()

    def get_executions(
        self,
        test_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> List[ExecutionRecord]:
        query = "SELECT * FROM executions WHERE 1=1"
        params: List[Any] = []
        if test_id:
            query += " AND test_id = ?"
            params.append(test_id)
        if since is not None:
            query += " AND timestamp >= ?"
            params.append(since)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        results: List[ExecutionRecord] = []
        for r in rows:
            results.append(
                ExecutionRecord(
                    execution_id=r["execution_id"],
                    run_id=r["run_id"],
                    timestamp=r["timestamp"],
                    project_name=r["project_name"],
                    commit_or_tree_hash=r["commit_or_tree_hash"],
                    test_id=r["test_id"],
                    category=r["category"],
                    status=r["status"],
                    duration_ms=r["duration_ms"],
                    retry_count=r["retry_count"],
                    execution_mode=r["execution_mode"],
                    environment_fingerprint=r["environment_fingerprint"] or "",
                    failure_fingerprint=r["failure_fingerprint"],
                    failure_category=FailureCategory(r["failure_category"]) if r["failure_category"] else None,
                    risk_level=r["risk_level"],
                    affected_symbols=json.loads(r["affected_symbols_json"] or "[]"),
                    evidence_ref=r["evidence_ref"],
                    metadata=json.loads(r["metadata_json"] or "{}"),
                )
            )
        return results

    def save_failure_cluster(self, cluster: FailureCluster) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO failure_clusters (
                    fingerprint, first_seen, last_seen, occurrences, status,
                    classification, confidence, affected_tests_json, affected_components_json,
                    environments_json, sample_message, sample_stack_frame, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cluster.fingerprint,
                    cluster.first_seen,
                    cluster.last_seen,
                    cluster.occurrences,
                    cluster.status.value,
                    cluster.classification.value,
                    cluster.confidence,
                    json.dumps(cluster.affected_tests),
                    json.dumps(cluster.affected_components),
                    json.dumps(cluster.environments),
                    cluster.sample_message,
                    cluster.sample_stack_frame,
                    cluster.resolved_at,
                ),
            )
            conn.commit()

    def get_failure_clusters(self, limit: int = 100) -> List[FailureCluster]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM failure_clusters ORDER BY last_seen DESC LIMIT ?", (limit,)
            )
            rows = cursor.fetchall()

        clusters: List[FailureCluster] = []
        for r in rows:
            clusters.append(
                FailureCluster(
                    fingerprint=r["fingerprint"],
                    first_seen=r["first_seen"],
                    last_seen=r["last_seen"],
                    occurrences=r["occurrences"],
                    status=FailureStatus(r["status"]),
                    classification=FailureCategory(r["classification"]),
                    confidence=r["confidence"],
                    affected_tests=json.loads(r["affected_tests_json"] or "[]"),
                    affected_components=json.loads(r["affected_components_json"] or "[]"),
                    environments=json.loads(r["environments_json"] or "[]"),
                    sample_message=r["sample_message"] or "",
                    sample_stack_frame=r["sample_stack_frame"],
                    resolved_at=r["resolved_at"],
                )
            )
        return clusters

    def get_failure_cluster(self, fingerprint: str) -> Optional[FailureCluster]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM failure_clusters WHERE fingerprint = ?", (fingerprint,)
            )
            r = cursor.fetchone()
        if not r:
            return None
        return FailureCluster(
            fingerprint=r["fingerprint"],
            first_seen=r["first_seen"],
            last_seen=r["last_seen"],
            occurrences=r["occurrences"],
            status=FailureStatus(r["status"]),
            classification=FailureCategory(r["classification"]),
            confidence=r["confidence"],
            affected_tests=json.loads(r["affected_tests_json"] or "[]"),
            affected_components=json.loads(r["affected_components_json"] or "[]"),
            environments=json.loads(r["environments_json"] or "[]"),
            sample_message=r["sample_message"] or "",
            sample_stack_frame=r["sample_stack_frame"],
            resolved_at=r["resolved_at"],
        )

    def save_correlation(self, corr: ChangeFailureCorrelation) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO correlations (
                    symbol_name, file_path, failure_fingerprint, test_id,
                    co_occurrence_count, confidence, last_observed
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol_name, failure_fingerprint, test_id) DO UPDATE SET
                    co_occurrence_count = co_occurrence_count + 1,
                    last_observed = excluded.last_observed,
                    confidence = MIN(1.0, confidence + 0.1)
                """,
                (
                    corr.symbol_name,
                    corr.file_path,
                    corr.failure_fingerprint,
                    corr.test_id,
                    corr.co_occurrence_count,
                    corr.confidence,
                    corr.last_observed,
                ),
            )
            conn.commit()

    def get_correlations(self, symbol: Optional[str] = None, limit: int = 100) -> List[ChangeFailureCorrelation]:
        query = "SELECT * FROM correlations WHERE 1=1"
        params: List[Any] = []
        if symbol:
            query += " AND symbol_name = ?"
            params.append(symbol)
        query += " ORDER BY co_occurrence_count DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        corrs: List[ChangeFailureCorrelation] = []
        for r in rows:
            corrs.append(
                ChangeFailureCorrelation(
                    symbol_name=r["symbol_name"],
                    file_path=r["file_path"],
                    failure_fingerprint=r["failure_fingerprint"],
                    test_id=r["test_id"],
                    co_occurrence_count=r["co_occurrence_count"],
                    confidence=r["confidence"],
                    last_observed=r["last_observed"],
                )
            )
        return corrs

    def save_quality_history(self, rec: QualityHistoryRecord) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO quality_history (
                    finding_fingerprint, dimension, rule_id, affected_target,
                    severity, status, first_seen, last_seen, occurrences, events_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.finding_fingerprint,
                    rec.dimension,
                    rec.rule_id,
                    rec.affected_target,
                    rec.severity,
                    rec.status.value,
                    rec.first_seen,
                    rec.last_seen,
                    rec.occurrences,
                    json.dumps(rec.history_events),
                ),
            )
            conn.commit()

    def get_quality_history(self, fingerprint: Optional[str] = None, limit: int = 100) -> List[QualityHistoryRecord]:
        query = "SELECT * FROM quality_history WHERE 1=1"
        params: List[Any] = []
        if fingerprint:
            query += " AND finding_fingerprint = ?"
            params.append(fingerprint)
        query += " ORDER BY last_seen DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        recs: List[QualityHistoryRecord] = []
        for r in rows:
            recs.append(
                QualityHistoryRecord(
                    finding_fingerprint=r["finding_fingerprint"],
                    dimension=r["dimension"],
                    rule_id=r["rule_id"],
                    affected_target=r["affected_target"],
                    severity=r["severity"],
                    status=QualityFindingStatus(r["status"]),
                    first_seen=r["first_seen"],
                    last_seen=r["last_seen"],
                    occurrences=r["occurrences"],
                    history_events=json.loads(r["events_json"] or "[]"),
                )
            )
        return recs

    def prune_older_than(self, max_age_seconds: float = 90 * 86400, max_records: int = 50000) -> int:
        """Prunes historical execution records older than max_age_seconds or exceeding max_records."""
        cutoff = time.time() - max_age_seconds
        deleted = 0
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM executions WHERE timestamp < ?", (cutoff,))
            deleted += cur.rowcount
            conn.commit()
        return deleted
