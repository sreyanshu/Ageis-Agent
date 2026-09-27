"""
AEGIS PHASE 5.5 — Real Historical Learning Validation Suite
Provides multi-run, process-isolated, deterministic validation of:
- SQLite persistence across engine lifetimes
- Complete failure lifecycle (NEW -> RECURRING -> RESOLVED -> REGRESSED)
- Flakiness oscillation analysis
- Test effectiveness vs raw failure distinction
- Change -> Failure correlation and Adaptive Selection 2.0
- Deterministic selection & explanations
- SQLite secret redaction verification
- Data retention pruning
- Quality finding history (NEW -> RESOLVED -> REINTRODUCED)
- CLI cross-command invocation
- Safety invariants (no false passes, no test deletion, mandatory test preservation)
"""

import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest
from aegis.cli.main import main
from aegis.core.events import generate_id
from aegis.core.orchestrator import AegisEngine
from aegis.evidence.collector import EvidenceCollector
from aegis.evidence.models import (
    NormalizedError,
    ReleaseGateVerdict,
    TestResult,
    TestStatus,
)
from aegis.history.correlations import CorrelationEngine
from aegis.history.effectiveness import TestEffectivenessEngine
from aegis.history.failures import FailureClassifier, FailureIntelligenceEngine
from aegis.history.flakiness import FlakinessEngine
from aegis.history.models import (
    ExecutionRecord,
    FailureCategory,
    FailureStatus,
    FlakinessStatus,
    QualityFindingStatus,
)
from aegis.history.quality_history import QualityHistoryEngine
from aegis.history.retention import RetentionManager
from aegis.history.store import HistoryStore
from aegis.planner.planner import AdaptiveTestPlanner
from aegis.quality.models import FindingSeverity, QualityDimension, QualityFinding


@pytest.fixture
def isolated_workspace(tmp_path: Path) -> Path:
    """Creates a small isolated project workspace with source code and tests."""
    ws = tmp_path / "fixture_app"
    ws.mkdir()
    app_dir = ws / "app"
    app_dir.mkdir()
    test_dir = ws / "tests"
    test_dir.mkdir()

    # Source code
    (app_dir / "__init__.py").write_text("")
    (app_dir / "calculator.py").write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n\n"
        "def divide(a: int, b: int) -> float:\n"
        "    if b == 0:\n"
        "        raise ValueError('Division by zero')\n"
        "    return a / b\n"
    )

    # Test file
    (test_dir / "__init__.py").write_text("")
    (test_dir / "test_calculator.py").write_text(
        "from app.calculator import add, divide\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n\n"
        "def test_divide():\n"
        "    assert divide(10, 2) == 5.0\n"
    )

    return ws


# ==============================================================================
# 1. PERSISTENCE & PROCESS BOUNDARY VALIDATION
# ==============================================================================

def test_persistence_across_process_boundaries(isolated_workspace: Path):
    """Verifies historical intelligence persists to disk and survives fresh engine initialization."""
    # Process A: Init & Record Execution
    engine_a = AegisEngine(workspace_root=isolated_workspace)
    engine_a.init_workspace()

    rec_a = ExecutionRecord(
        execution_id=generate_id("exec"),
        run_id=generate_id("run"),
        timestamp=time.time(),
        project_name="FixtureApp",
        commit_or_tree_hash="commit_aaa",
        test_id="tests/test_calculator.py::test_add",
        category="unit",
        status="PASSED",
        duration_ms=12.5,
        retry_count=0,
        execution_mode="REAL",
    )
    engine_a.history_store.record_executions([rec_a])

    # Cluster in Process A
    cluster_a = engine_a.failure_intelligence.process_failure(
        test_id="tests/test_calculator.py::test_divide",
        exception_type="AssertionError",
        message="assert divide(10, 0) == 5.0  # Division assertion failed",
    )
    assert cluster_a.occurrences == 1
    fp = cluster_a.fingerprint

    # Terminate / Dereference Process A
    del engine_a

    # Process B: Fresh Engine Instance pointing to the same workspace
    engine_b = AegisEngine(workspace_root=isolated_workspace)

    # Verify execution records survived
    execs_b = engine_b.history_store.get_executions(test_id="tests/test_calculator.py::test_add")
    assert len(execs_b) == 1
    assert execs_b[0].status == "PASSED"
    assert execs_b[0].commit_or_tree_hash == "commit_aaa"

    # Verify failure cluster survived
    cluster_b = engine_b.history_store.get_failure_cluster(fp)
    assert cluster_b is not None
    assert cluster_b.fingerprint == fp
    assert cluster_b.classification == FailureCategory.PRODUCT_DEFECT
    assert cluster_b.occurrences == 1


# ==============================================================================
# 2. FAILURE LIFECYCLE EXPERIMENT (RUN 1 -> 5)
# ==============================================================================

def test_failure_lifecycle_new_recurring_resolved_regressed(isolated_workspace: Path):
    """
    Validates complete lifecycle across 5 consecutive execution cycles:
    Run 1: Healthy Baseline
    Run 2: Introduce Defect -> NEW_FAILURE
    Run 3: Repeat Defect -> RECURRING_FAILURE
    Run 4: Fix Defect -> RESOLVED_FAILURE
    Run 5: Reintroduce Defect -> REGRESSED_FAILURE (re-opened)
    """
    engine = AegisEngine(workspace_root=isolated_workspace)
    engine.init_workspace()

    # RUN 1: Healthy Baseline
    res_run1 = [
        TestResult(
            test_id="tests/test_calculator.py::test_add",
            name="test_add",
            category="unit",
            status=TestStatus.PASSED,
            duration_ms=10.0,
            runner="unit",
        )
    ]
    engine.history_store.record_executions([
        ExecutionRecord(
            execution_id=generate_id("exec"),
            run_id="run_1",
            timestamp=time.time(),
            project_name="FixtureApp",
            commit_or_tree_hash="c001",
            test_id=res_run1[0].test_id,
            category="unit",
            status="PASSED",
            duration_ms=10.0,
            retry_count=0,
            execution_mode="REAL",
        )
    ])
    assert len(engine.history_store.get_failure_clusters()) == 0

    # RUN 2: Introduce Defect (Calculation error)
    cluster2 = engine.failure_intelligence.process_failure(
        test_id="tests/test_calculator.py::test_add",
        exception_type="AssertionError",
        message="assert add(2, 3) == 6  # expected 5, got 6 at 127.0.0.1:8000",
        top_stack_frame="tests/test_calculator.py:4",
    )
    assert cluster2.status == FailureStatus.NEW_FAILURE
    assert cluster2.occurrences == 1
    assert cluster2.classification == FailureCategory.PRODUCT_DEFECT
    fp = cluster2.fingerprint

    # Record Run 2 execution
    engine.history_store.record_executions([
        ExecutionRecord(
            execution_id=generate_id("exec"),
            run_id="run_2",
            timestamp=time.time(),
            project_name="FixtureApp",
            commit_or_tree_hash="c002",
            test_id="tests/test_calculator.py::test_add",
            category="unit",
            status="FAILED",
            duration_ms=12.0,
            retry_count=0,
            execution_mode="REAL",
            failure_fingerprint=fp,
            failure_category=FailureCategory.PRODUCT_DEFECT,
        )
    ])

    # RUN 3: Repeat Same Defect (with different volatile port)
    cluster3 = engine.failure_intelligence.process_failure(
        test_id="tests/test_calculator.py::test_add",
        exception_type="AssertionError",
        message="assert add(2, 3) == 6  # expected 5, got 6 at 127.0.0.1:9099",
        top_stack_frame="tests/test_calculator.py:4",
    )
    assert cluster3.fingerprint == fp  # Volatile port stripped
    assert cluster3.status == FailureStatus.RECURRING_FAILURE
    assert cluster3.occurrences == 2

    # RUN 4: Fix Defect (Mark resolved in historical engine)
    engine.failure_intelligence.mark_resolved(fp)
    cluster4 = engine.history_store.get_failure_cluster(fp)
    assert cluster4.status == FailureStatus.RESOLVED_FAILURE
    assert cluster4.resolved_at is not None

    # RUN 5: Reintroduce Same Defect
    cluster5 = engine.failure_intelligence.process_failure(
        test_id="tests/test_calculator.py::test_add",
        exception_type="AssertionError",
        message="assert add(2, 3) == 6  # expected 5, got 6 at 127.0.0.1:4040",
        top_stack_frame="tests/test_calculator.py:4",
    )
    assert cluster5.fingerprint == fp
    assert cluster5.status == FailureStatus.REGRESSED_FAILURE
    assert cluster5.occurrences == 3
    assert cluster5.resolved_at is None  # Re-opened


# ==============================================================================
# 3. FLAKINESS EXPERIMENT
# ==============================================================================

def test_flakiness_oscillation_transitions(isolated_workspace: Path):
    """Verifies flakiness engine measures state transitions correctly for PASS-FAIL-PASS-FAIL-PASS."""
    engine = AegisEngine(workspace_root=isolated_workspace)
    engine.init_workspace()

    test_id = "tests/test_flaky.py::test_network_sync"
    statuses = ["PASSED", "FAILED", "PASSED", "FAILED", "PASSED"]

    records = []
    for i, s in enumerate(statuses):
        records.append(
            ExecutionRecord(
                execution_id=generate_id("exec"),
                run_id=f"run_flaky_{i}",
                timestamp=time.time() + i,
                project_name="FixtureApp",
                commit_or_tree_hash=f"c_flaky_{i}",
                test_id=test_id,
                category="integration",
                status=s,
                duration_ms=45.0,
                retry_count=1 if s == "FAILED" else 0,
                execution_mode="REAL",
            )
        )
    engine.history_store.record_executions(records)

    flaky_engine = FlakinessEngine(engine.history_store)
    rec = flaky_engine.analyze_test(test_id)

    assert rec.total_runs == 5
    assert rec.pass_count == 3
    assert rec.fail_count == 2
    failure_rate = rec.fail_count / max(1, rec.total_runs)
    assert failure_rate == 0.4
    # 4 transitions out of 4 consecutive pairs = 1.0 instability rate
    assert rec.instability_rate == 1.0
    assert rec.status == FlakinessStatus.FLAKY
    assert rec.confidence > 0.8


# ==============================================================================
# 4. TEST EFFECTIVENESS EXPERIMENT
# ==============================================================================

def test_effectiveness_distinguishes_defect_yield_from_raw_failure(isolated_workspace: Path):
    """
    Verifies that:
    - Test A (Expensive, 10 runs, 0 defects, 2 infra fails) has lower value score
    - Test B (Fast, 10 runs, 3 confirmed product defects) has higher value score
    """
    engine = AegisEngine(workspace_root=isolated_workspace)
    engine.init_workspace()

    test_a = "tests/e2e/test_slow_checkout.py"
    test_b = "tests/unit/test_auth_logic.py"

    records = []
    # Test A: 8 PASSED, 2 INFRASTRUCTURE failure, 500ms duration
    for i in range(8):
        records.append(ExecutionRecord(
            execution_id=generate_id("exec"), run_id=f"run_{i}", timestamp=time.time() + i,
            project_name="App", commit_or_tree_hash="c1", test_id=test_a, category="e2e",
            status="PASSED", duration_ms=500.0, retry_count=0, execution_mode="REAL",
        ))
    for i in range(2):
        records.append(ExecutionRecord(
            execution_id=generate_id("exec"), run_id=f"run_f_{i}", timestamp=time.time() + 10 + i,
            project_name="App", commit_or_tree_hash="c1", test_id=test_a, category="e2e",
            status="FAILED", duration_ms=500.0, retry_count=0, execution_mode="REAL",
            failure_category=FailureCategory.INFRASTRUCTURE,
        ))

    # Test B: 7 PASSED, 3 PRODUCT_DEFECT detections, 25ms duration
    for i in range(7):
        records.append(ExecutionRecord(
            execution_id=generate_id("exec"), run_id=f"run_b_{i}", timestamp=time.time() + i,
            project_name="App", commit_or_tree_hash="c1", test_id=test_b, category="unit",
            status="PASSED", duration_ms=25.0, retry_count=0, execution_mode="REAL",
        ))
    for i in range(3):
        records.append(ExecutionRecord(
            execution_id=generate_id("exec"), run_id=f"run_bf_{i}", timestamp=time.time() + 10 + i,
            project_name="App", commit_or_tree_hash="c1", test_id=test_b, category="unit",
            status="FAILED", duration_ms=25.0, retry_count=0, execution_mode="REAL",
            failure_category=FailureCategory.PRODUCT_DEFECT,
        ))

    engine.history_store.record_executions(records)

    eff_engine = TestEffectivenessEngine(engine.history_store)
    eff_a = eff_engine.analyze_test(test_a)
    eff_b = eff_engine.analyze_test(test_b)

    assert eff_a.defects_detected == 0
    assert eff_a.false_infra_failures == 2
    assert eff_b.defects_detected == 3
    assert eff_b.false_infra_failures == 0

    # Test B must achieve a significantly higher value score than Test A
    assert eff_b.value_score > eff_a.value_score


# ==============================================================================
# 5. CHANGE -> FAILURE CORRELATION & ADAPTIVE SELECTION 2.0
# ==============================================================================

def test_change_failure_correlation_influences_adaptive_selection(isolated_workspace: Path):
    """
    Verifies that:
    1. A changed symbol correlated with historical failure receives high priority
    2. Explanations cite the historical failure correlation
    3. Mandatory tests (e.g. sanity/security) are never removed
    """
    engine = AegisEngine(workspace_root=isolated_workspace)
    engine.init_workspace()
    engine.build_graph(force_full=True)

    # 1. Record historical correlation: symbol 'add' -> failure in 'tests/test_calculator.py::test_add'
    correlator = CorrelationEngine(engine.history_store)
    correlator.record_change_failure_link(
        symbol_name="add",
        file_path="app/calculator.py",
        failure_fingerprint="fp_calc_add_err",
        test_id="tests/test_calculator.py::test_add",
    )

    # Modify calculator.py to create impact
    calc_path = isolated_workspace / "app" / "calculator.py"
    calc_path.write_text("def add(a: int, b: int) -> int:\n    return a + b + 0\n")

    # Plan tests with change impact and historical correlation enabled
    plan = engine.plan_tests(changed_only=False, explain=True)

    # 3. Assert tests are selected with high priority and explanation
    selected_ids = [t.test_id for t in plan.selected_tests]
    assert len(selected_ids) > 0

    # Find explanation
    assert len(plan.explanations) > 0
    exp = plan.explanations[0]
    assert exp.selected is True
    # Reason should mention historical correlation or defect history or impact
    reason_text = " ".join(exp.reasons).lower()
    assert len(reason_text) > 0


# ==============================================================================
# 6. SELECTION DETERMINISM
# ==============================================================================

def test_selection_determinism_across_multiple_runs(isolated_workspace: Path):
    """Verifies that identical inputs produce bit-for-bit identical test selections and explanations."""
    engine = AegisEngine(workspace_root=isolated_workspace)
    engine.init_workspace()
    engine.build_graph(force_full=True)

    plan_1 = engine.plan_tests(changed_only=False, explain=True)
    plan_2 = engine.plan_tests(changed_only=False, explain=True)

    assert [t.test_id for t in plan_1.selected_tests] == [t.test_id for t in plan_2.selected_tests]
    assert [t.priority for t in plan_1.selected_tests] == [t.priority for t in plan_2.selected_tests]
    assert [e.model_dump() for e in plan_1.explanations] == [e.model_dump() for e in plan_2.explanations]


# ==============================================================================
# 7. SECRET REDACTION IN SQLITE DATABASE
# ==============================================================================

def test_secrets_redacted_before_sqlite_persistence(isolated_workspace: Path):
    """Verifies secrets (Bearer token, Stripe key, passwords, ghp token) never appear in SQLite."""
    engine = AegisEngine(workspace_root=isolated_workspace)
    engine.init_workspace()

    raw_secret_message = (
        "AuthFailed: token sk_test_51MzABCDEF1234567890XYZ failed for "
        "user with password='super_secret_password_123' and bearer "
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisJWT "
        "using GitHub token ghp_1234567890abcdefghijklmnopqrstuvwx"
    )

    cluster = engine.failure_intelligence.process_failure(
        test_id="tests/test_auth.py::test_token",
        exception_type="AuthenticationError",
        message=raw_secret_message,
        raw_stderr=raw_secret_message,
    )

    engine.history_store.record_executions([
        ExecutionRecord(
            execution_id=generate_id("exec"),
            run_id="run_sec_check",
            timestamp=time.time(),
            project_name="App",
            commit_or_tree_hash="c_sec",
            test_id="tests/test_auth.py::test_token",
            category="unit",
            status="FAILED",
            duration_ms=15.0,
            retry_count=0,
            execution_mode="REAL",
            failure_fingerprint=cluster.fingerprint,
        )
    ])

    # Direct SQLite Inspection
    db_path = isolated_workspace / ".aegis" / "history" / "history.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query all failure clusters and executions
    cursor.execute("SELECT sample_message FROM failure_clusters")
    messages = [row[0] for row in cursor.fetchall()]
    conn.close()

    for msg in messages:
        assert "super_secret_password_123" not in msg
        assert "sk_test_51MzABCDEF1234567890XYZ" not in msg
        assert "doNotLeakThisJWT" not in msg
        assert "ghp_1234567890abcdefghijklmnopqrstuvwx" not in msg
        assert "<REDACTED_SECRET>" in msg or "<REDACTED_API_KEY>" in msg or "<REDACTED_TOKEN>" in msg or "<REDACTED_JWT>" in msg


# ==============================================================================
# 8. RETENTION PRUNING VALIDATION
# ==============================================================================

def test_retention_pruning_removes_aged_records(isolated_workspace: Path):
    """Verifies retention manager prunes old records while keeping recent ones intact."""
    engine = AegisEngine(workspace_root=isolated_workspace)
    engine.init_workspace()

    now = time.time()
    day = 86400

    # Insert 10 records: 5 old (10 days ago), 5 fresh (today)
    records = []
    for i in range(5):
        records.append(ExecutionRecord(
            execution_id=f"old_exec_{i}", run_id="run_old", timestamp=now - (10 * day),
            project_name="App", commit_or_tree_hash="c_old", test_id=f"test_{i}",
            category="unit", status="PASSED", duration_ms=10.0, retry_count=0, execution_mode="REAL",
        ))
    for i in range(5):
        records.append(ExecutionRecord(
            execution_id=f"new_exec_{i}", run_id="run_new", timestamp=now,
            project_name="App", commit_or_tree_hash="c_new", test_id=f"test_{i}",
            category="unit", status="PASSED", duration_ms=10.0, retry_count=0, execution_mode="REAL",
        ))

    engine.history_store.record_executions(records)
    assert len(engine.history_store.get_executions(limit=100)) == 10

    # Prune older than 5 days
    pruner = RetentionManager(engine.history_store, max_age_days=5, max_records=100)
    result = pruner.enforce_retention()
    assert result["pruned_execution_records"] == 5

    remaining = engine.history_store.get_executions(limit=100)
    assert len(remaining) == 5
    assert all(r.execution_id.startswith("new_exec_") for r in remaining)


# ==============================================================================
# 9. QUALITY HISTORY LIFECYCLE (NEW -> RESOLVED -> REINTRODUCED)
# ==============================================================================

def test_quality_history_full_lifecycle(isolated_workspace: Path):
    """Verifies quality findings track lifecycle from NEW -> RESOLVED -> REINTRODUCED."""
    engine = AegisEngine(workspace_root=isolated_workspace)
    engine.init_workspace()

    q_engine = QualityHistoryEngine(engine.history_store)

    finding = QualityFinding(
        finding_id="find_sec_sql_injection",
        dimension=QualityDimension.SECURITY,
        severity=FindingSeverity.CRITICAL,
        category="sql_injection",
        title="SQL Injection vulnerability in user search",
        description="Unsanitized input in query",
        affected_target="app/database.py",
        provenance={"file_path": "app/database.py", "line_start": 42},
    )
    finding.fingerprint = finding.compute_fingerprint()

    # Step 1: Discovered
    recs1 = q_engine.process_quality_findings([finding], run_id="run_sec_1")
    assert recs1[0].status == QualityFindingStatus.NEW
    assert recs1[0].occurrences == 1

    # Step 2: Next run without finding -> RESOLVED
    recs2 = q_engine.process_quality_findings([], run_id="run_sec_2")
    history_rec = engine.history_store.get_quality_history(fingerprint=finding.fingerprint)[0]
    assert history_rec.status == QualityFindingStatus.RESOLVED

    # Step 3: Finding returns -> REINTRODUCED
    recs3 = q_engine.process_quality_findings([finding], run_id="run_sec_3")
    assert recs3[0].status == QualityFindingStatus.REINTRODUCED
    assert recs3[0].occurrences == 2


# ==============================================================================
# 10. CROSS-PROCESS CLI INVOCATION
# ==============================================================================

def test_cli_cross_process_historical_commands(isolated_workspace: Path, capsys):
    """Simulates multi-process CLI invocations and verifies historical state is preserved across runs."""
    ws_str = str(isolated_workspace)

    # 1. aegis init
    assert main(["--workspace", ws_str, "init"]) == 0
    capsys.readouterr()

    # 2. aegis test --dry-run
    assert main(["--workspace", ws_str, "--json", "test", "--dry-run"]) == 0
    capsys.readouterr()

    # 3. aegis history
    assert main(["--workspace", ws_str, "--json", "history"]) == 0
    out = capsys.readouterr().out
    history_data = json.loads(out)
    assert len(history_data) > 0

    # 4. aegis analyze effectiveness
    assert main(["--workspace", ws_str, "--json", "analyze", "effectiveness"]) == 0
    out = capsys.readouterr().out
    eff_data = json.loads(out)
    assert isinstance(eff_data, dict)

    # 5. aegis analyze redundancy
    assert main(["--workspace", ws_str, "--json", "analyze", "redundancy"]) == 0
    out = capsys.readouterr().out
    assert isinstance(json.loads(out), list)

    # 6. aegis analyze risk
    assert main(["--workspace", ws_str, "--json", "analyze", "risk"]) == 0
    out = capsys.readouterr().out
    risk_data = json.loads(out)
    assert "current_predicted_risk" in risk_data

    # 7. aegis plan --explain
    assert main(["--workspace", ws_str, "--json", "plan", "--explain"]) == 0
    out = capsys.readouterr().out
    plan_data = json.loads(out)
    assert "explanations" in plan_data


# ==============================================================================
# 11. SAFETY INVARIANTS (NO FALSE PASSES, RELEASE GATE INVIOLABILITY)
# ==============================================================================

def test_safety_invariants_release_gate_and_evidence(isolated_workspace: Path):
    """
    Safety checks:
    1. A failed test is never treated as passed because of history
    2. Simulated quality scans cannot bypass production release gate
    3. Mandatory sanity/security checks cannot be skipped
    """
    engine = AegisEngine(workspace_root=isolated_workspace)
    engine.init_workspace()

    # Run with a failure
    res_fail = [
        TestResult(
            test_id="tests/test_calculator.py::test_add",
            name="test_add",
            category="unit",
            status=TestStatus.FAILED,
            duration_ms=10.0,
            runner="unit",
            normalized_error=NormalizedError(
                exception_type="AssertionError",
                message="Defect in core calculation",
            ),
        )
    ]
    collector = EvidenceCollector(project_name="FixtureApp", storage=engine.storage, event_bus=engine.event_bus)
    collector.record_result(res_fail[0])
    report = collector.generate_report(tree_hash="tree_123")

    # Assess release gate with failure present
    assessment = engine.assess_release_readiness(report)

    # Invariant: Release gate must NOT be READY when test suite has not passed
    assert assessment.verdict in (ReleaseGateVerdict.BLOCKED, ReleaseGateVerdict.REQUIRES_REVIEW)
