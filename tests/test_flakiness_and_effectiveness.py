"""
Unit Tests for Aegis Flakiness Analysis & Test Effectiveness Ranking
"""

import time
from pathlib import Path
from aegis.history.store import HistoryStore
from aegis.history.flakiness import FlakinessEngine
from aegis.history.effectiveness import TestEffectivenessEngine
from aegis.history.models import (
    ExecutionRecord,
    FlakinessStatus,
    FailureCategory,
)


def test_flakiness_detection_transitions(tmp_path: Path):
    store = HistoryStore(tmp_path / "history")
    engine = FlakinessEngine(store, min_samples=4)
    now = time.time()

    # Flaky test alternating P -> F -> P -> F
    statuses = ["PASSED", "FAILED", "PASSED", "FAILED", "PASSED"]
    records = [
        ExecutionRecord(
            execution_id=f"e_{i}",
            run_id=f"r_{i}",
            timestamp=now - (100 - i * 10),
            project_name="TestApp",
            commit_or_tree_hash="tree_1",
            test_id="test_flaky_checkout",
            category="e2e",
            status=st,
        )
        for i, st in enumerate(statuses)
    ]
    store.record_executions(records)

    flaky_rec = engine.analyze_test("test_flaky_checkout")
    assert flaky_rec.status == FlakinessStatus.FLAKY
    assert flaky_rec.instability_rate >= 0.5
    assert flaky_rec.pass_count == 3
    assert flaky_rec.fail_count == 2


def test_test_effectiveness_defect_yield_and_ranking(tmp_path: Path):
    store = HistoryStore(tmp_path / "history")
    eff_engine = TestEffectivenessEngine(store)
    now = time.time()

    # Test 1: High defect yield (catches real product bugs fast)
    t1_records = [
        ExecutionRecord(
            execution_id=f"t1_{i}",
            run_id=f"r_{i}",
            timestamp=now - (50 - i * 10),
            project_name="TestApp",
            commit_or_tree_hash="tree_1",
            test_id="test_security_auth",
            category="unit",
            status="FAILED" if i % 2 == 0 else "PASSED",
            duration_ms=40.0,
            failure_category=FailureCategory.PRODUCT_DEFECT if i % 2 == 0 else None,
        )
        for i in range(5)
    ]
    # Test 2: Slow test with only infra/timeout failures
    t2_records = [
        ExecutionRecord(
            execution_id=f"t2_{i}",
            run_id=f"r_{i}",
            timestamp=now - (50 - i * 10),
            project_name="TestApp",
            commit_or_tree_hash="tree_1",
            test_id="test_slow_e2e",
            category="e2e",
            status="FAILED" if i == 0 else "PASSED",
            duration_ms=6000.0,
            failure_category=FailureCategory.TIMEOUT if i == 0 else None,
        )
        for i in range(5)
    ]
    store.record_executions(t1_records + t2_records)

    eff1 = eff_engine.analyze_test("test_security_auth")
    eff2 = eff_engine.analyze_test("test_slow_e2e")

    assert eff1.defects_detected == 3
    assert eff2.defects_detected == 0
    assert eff2.false_infra_failures == 1
    # Fast test with high defect yield should score significantly higher
    assert eff1.value_score > eff2.value_score
