from aegis.discovery.tests import TestSuiteInfo
from aegis.impact.models import ImpactReport, AffectedEntity
from aegis.planner.planner import AdaptiveTestPlanner
from aegis.planner.models import RiskAssessment, RiskLevel


def test_adaptive_planner_impacted_selection():
    planner = AdaptiveTestPlanner()
    impact = ImpactReport(
        report_id="imp_1",
        tree_hash="hash1",
        has_changes=True,
        affected_tests=[
            AffectedEntity(id="py:test_auth", name="test_auth", entity_type="test", file_path="tests/test_auth.py"),
        ],
    )
    risk = RiskAssessment(
        level=RiskLevel.MEDIUM,
        composite_score=0.35,
        reasons=["Medium risk changes"],
        recommendation="Targeted test validation",
    )
    suites = [
        TestSuiteInfo(
            framework="pytest",
            runner_cmd="pytest",
            test_files=["tests/test_auth.py", "tests/test_other.py"],
            test_count_estimate=10,
        ),
        TestSuiteInfo(
            framework="vitest",
            runner_cmd="npm test",
            test_files=["frontend/app.test.tsx"],
            test_count_estimate=5,
        ),
    ]

    # When changed_only = True
    plan = planner.plan_tests(impact=impact, risk=risk, available_suites=suites, changed_only=True)
    assert plan.total_planned >= 1
    selected_ids = [t.test_id for t in plan.selected_tests]
    assert "test.pytest.impacted" in selected_ids

    # Unrelated suite is safely skipped
    assert plan.total_skipped >= 1
    skipped_ids = [s.test_id for s in plan.skipped_tests]
    assert "test.vitest.skipped" in skipped_ids
