"""
Unit Tests for Aegis Historical Knowledge Store
"""

import time
from pathlib import Path
from aegis.history.store import HistoryStore
from aegis.history.models import (
    ExecutionRecord,
    FailureCluster,
    FailureCategory,
    FailureStatus,
    ChangeFailureCorrelation,
    QualityHistoryRecord,
    QualityFindingStatus,
)


def test_history_store_crud_and_queries(tmp_path: Path):
    store = HistoryStore(tmp_path / "history")

    # 1. Record executions
    rec1 = ExecutionRecord(
        execution_id="exec_1",
        run_id="run_1",
        timestamp=time.time() - 100,
        project_name="TestApp",
        commit_or_tree_hash="tree_1",
        test_id="test_login",
        category="unit",
        status="PASSED",
        duration_ms=45.0,
    )
    rec2 = ExecutionRecord(
        execution_id="exec_2",
        run_id="run_1",
        timestamp=time.time(),
        project_name="TestApp",
        commit_or_tree_hash="tree_1",
        test_id="test_login",
        category="unit",
        status="FAILED",
        duration_ms=52.0,
        failure_fingerprint="fp_auth_err",
        failure_category=FailureCategory.PRODUCT_DEFECT,
    )
    store.record_executions([rec1, rec2])

    execs = store.get_executions(test_id="test_login")
    assert len(execs) == 2
    assert execs[0].execution_id == "exec_2"  # Sorted DESC by timestamp

    # 2. Save and query failure clusters
    cluster = FailureCluster(
        fingerprint="fp_auth_err",
        first_seen=time.time() - 100,
        last_seen=time.time(),
        occurrences=2,
        status=FailureStatus.NEW_FAILURE,
        classification=FailureCategory.PRODUCT_DEFECT,
        confidence=0.9,
        affected_tests=["test_login"],
    )
    store.save_failure_cluster(cluster)
    clusters = store.get_failure_clusters()
    assert len(clusters) == 1
    assert clusters[0].fingerprint == "fp_auth_err"

    # 3. Correlations
    corr = ChangeFailureCorrelation(
        symbol_name="auth.validate_token",
        file_path="auth.py",
        failure_fingerprint="fp_auth_err",
        test_id="test_login",
        co_occurrence_count=1,
        confidence=0.8,
        last_observed=time.time(),
    )
    store.save_correlation(corr)
    corrs = store.get_correlations(symbol="auth.validate_token")
    assert len(corrs) == 1
    assert corrs[0].test_id == "test_login"

    # 4. Quality History
    q_rec = QualityHistoryRecord(
        finding_fingerprint="qf_sec_jwt",
        dimension="security",
        rule_id="B105",
        affected_target="auth.py:42",
        severity="HIGH",
        status=QualityFindingStatus.NEW,
    )
    store.save_quality_history(q_rec)
    q_list = store.get_quality_history(fingerprint="qf_sec_jwt")
    assert len(q_list) == 1
    assert q_list[0].status == QualityFindingStatus.NEW


def test_history_store_pruning(tmp_path: Path):
    store = HistoryStore(tmp_path / "history")
    now = time.time()

    # Old record (> 100 days ago)
    old_rec = ExecutionRecord(
        execution_id="old_1",
        run_id="run_old",
        timestamp=now - (120 * 86400),
        project_name="TestApp",
        commit_or_tree_hash="tree_old",
        test_id="test_old",
        category="unit",
        status="PASSED",
    )
    # Fresh record
    fresh_rec = ExecutionRecord(
        execution_id="fresh_1",
        run_id="run_fresh",
        timestamp=now,
        project_name="TestApp",
        commit_or_tree_hash="tree_fresh",
        test_id="test_fresh",
        category="unit",
        status="PASSED",
    )
    store.record_executions([old_rec, fresh_rec])

    # Prune records older than 90 days
    pruned = store.prune_older_than(max_age_seconds=90 * 86400)
    assert pruned == 1
    remaining = store.get_executions(limit=10)
    assert len(remaining) == 1
    assert remaining[0].execution_id == "fresh_1"
