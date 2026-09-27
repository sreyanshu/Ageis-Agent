"""
Unit Tests for Aegis Redundancy, Change-Failure Correlations, and Quality Reintroductions
"""

import time
from pathlib import Path
from aegis.history.store import HistoryStore
from aegis.history.redundancy import RedundancyEngine
from aegis.history.correlations import CorrelationEngine
from aegis.history.quality_history import QualityHistoryEngine
from aegis.history.models import ExecutionRecord, QualityFindingStatus
from aegis.quality.models import QualityFinding, FindingSeverity, QualityDimension


def test_test_redundancy_detection(tmp_path: Path):
    store = HistoryStore(tmp_path / "history")
    red_engine = RedundancyEngine(store)

    # Two test suites covering identical symbols and having identical failures
    shared_syms = ["auth.login", "auth.token", "auth.logout"]
    r1 = ExecutionRecord(
        execution_id="e1",
        run_id="r1",
        timestamp=time.time(),
        project_name="TestApp",
        commit_or_tree_hash="tree_1",
        test_id="suite_a",
        category="unit",
        status="FAILED",
        failure_fingerprint="fp_common_1",
        affected_symbols=shared_syms,
    )
    r2 = ExecutionRecord(
        execution_id="e2",
        run_id="r1",
        timestamp=time.time(),
        project_name="TestApp",
        commit_or_tree_hash="tree_1",
        test_id="suite_b",
        category="unit",
        status="FAILED",
        failure_fingerprint="fp_common_1",
        affected_symbols=shared_syms,
    )
    store.record_executions([r1, r2])

    redundancies = red_engine.analyze_redundancy()
    assert len(redundancies) == 1
    assert redundancies[0].overlap_score >= 0.8
    assert "suite_a" in (redundancies[0].test_id_a, redundancies[0].test_id_b)


def test_change_failure_correlations(tmp_path: Path):
    store = HistoryStore(tmp_path / "history")
    corr_engine = CorrelationEngine(store)

    corr_engine.record_change_failure_link(
        symbol_name="models.user_profile",
        file_path="models.py",
        failure_fingerprint="fp_db_mismatch",
        test_id="test_db_migration",
    )

    correlated = corr_engine.find_correlated_tests(["models.user_profile", "unrelated_symbol"])
    assert "test_db_migration" in correlated
    assert correlated["test_db_migration"] >= 0.7


def test_quality_history_reintroduced_findings(tmp_path: Path):
    store = HistoryStore(tmp_path / "history")
    q_engine = QualityHistoryEngine(store)

    finding = QualityFinding(
        finding_id="f1",
        dimension=QualityDimension.SECURITY,
        severity=FindingSeverity.HIGH,
        category="secret",
        title="Hardcoded API Key",
        description="Found key in source",
        affected_target="config.py:10",
        fingerprint="qf_sec_key_10",
    )

    # 1. First run: Discovered
    recs1 = q_engine.process_quality_findings([finding], run_id="run_1")
    assert recs1[0].status == QualityFindingStatus.NEW

    # 2. Second run: Resolved (finding absent)
    recs2 = q_engine.process_quality_findings([], run_id="run_2")
    assert recs2[0].status == QualityFindingStatus.RESOLVED

    # 3. Third run: Reintroduced (finding returns)
    recs3 = q_engine.process_quality_findings([finding], run_id="run_3")
    assert recs3[0].status == QualityFindingStatus.REINTRODUCED
