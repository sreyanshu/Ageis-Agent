"""
Unit Tests for Aegis Adaptive Test Selection 2.0 and Selection Explanations
"""

from pathlib import Path
from aegis.impact.models import ImpactReport, ChangedSymbol, SymbolChangeType, BlastRadius
from aegis.planner.models import RiskAssessment, RiskLevel
from aegis.planner.planner import AdaptiveTestPlanner
from aegis.discovery.tests import TestSuiteInfo
from aegis.history.store import HistoryStore
from aegis.history.correlations import CorrelationEngine


def test_adaptive_selection_v2_with_historical_correlations(tmp_path: Path):
    store = HistoryStore(tmp_path / "history")
    correlator = CorrelationEngine(store)

    # Establish correlation between modified symbol 'auth.hash_password' and test suite 'test.pytest.suite'
    correlator.record_change_failure_link(
        symbol_name="auth.hash_password",
        file_path="auth.py",
        failure_fingerprint="fp_hash_error",
        test_id="test.pytest.suite",
    )

    impact = ImpactReport(
        report_id="imp_1",
        tree_hash="hash_1",
        has_changes=True,
        changed_symbols=[
            ChangedSymbol(
                symbol_id="sym_auth_hash",
                name="auth.hash_password",
                file_path="auth.py",
                symbol_type="function",
                change_type=SymbolChangeType.MODIFIED,
            )
        ],
        blast_radius=BlastRadius(direct_count=1, total_affected=1),
    )

    risk = RiskAssessment(
        level=RiskLevel.LOW,
        composite_score=0.2,
        factors=[],
        reasons=[],
        recommendation="Low risk change",
    )

    suites = [
        TestSuiteInfo(
            framework="pytest",
            manifest_file="pytest.ini",
            test_files=["tests/test_auth.py"],
            test_count_estimate=5,
            runner_cmd="pytest",
        )
    ]

    planner = AdaptiveTestPlanner()
    plan = planner.plan_tests(
        impact=impact,
        risk=risk,
        available_suites=suites,
        changed_only=True,
        history_store=store,
        explain=True,
    )

    assert plan.total_planned == 1
    assert len(plan.explanations) == 1
    exp = plan.explanations[0]
    assert exp.selected is True
    assert any("Historical correlation" in r or "Historically correlated" in r for r in exp.reasons)
