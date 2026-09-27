"""
Aegis Adaptive Test Planning Engine
Calculates high-utility test plans based on impact blast radius, risk level,
and test suite relevance, skipping unaffected suites with explainable reasoning.
"""

from __future__ import annotations
from typing import List, Optional

from aegis.core.events import generate_id
from aegis.discovery.tests import TestSuiteInfo
from aegis.impact.models import ImpactReport
from aegis.planner.models import (
    TestPlan,
    PlannedTest,
    SkippedTest,
    RiskAssessment,
    RiskLevel,
)


class AdaptiveTestPlanner:
    """Plans test execution using utility maximization (regression detection value / execution cost)."""

    def plan_tests(
        self,
        impact: ImpactReport,
        risk: RiskAssessment,
        available_suites: List[TestSuiteInfo],
        changed_only: bool = False,
        history_store: Optional[Any] = None,
        explain: bool = False,
    ) -> TestPlan:
        """
        Constructs an adaptive test plan incorporating:
        - Change Impact & Blast Radius
        - Risk Factors
        - Historical Defect Yield & Failure Correlations
        - Flakiness & Execution Cost Awareness
        """
        from aegis.history.models import SelectionExplanation

        planned_tests: List[PlannedTest] = []
        skipped_tests: List[SkippedTest] = []
        explanations: List[SelectionExplanation] = []

        affected_test_files = {e.file_path for e in impact.affected_tests}
        changed_symbols = [s.name for s in impact.changed_symbols]

        # Query historical correlations if store is available
        correlated_tests: dict[str, float] = {}
        if history_store:
            try:
                from aegis.history.correlations import CorrelationEngine
                correlator = CorrelationEngine(history_store)
                correlated_tests = correlator.find_correlated_tests(changed_symbols)
            except Exception:
                pass

        for ts in available_suites:
            suite_files = set(ts.test_files)
            overlapping_files = suite_files.intersection(affected_test_files)
            test_id = f"test.{ts.framework}.impacted" if overlapping_files else f"test.{ts.framework}.suite"
            est_dur = ts.test_count_estimate * 20.0

            # Calculate historical correlation boost
            corr_boost = correlated_tests.get(test_id, 0.0)

            if overlapping_files:
                priority = 100
                reasons = [
                    f"Directly exercises changed code across {len(overlapping_files)} file(s).",
                    f"Test framework: {ts.framework}",
                ]
                if corr_boost > 0:
                    reasons.append(f"Historical correlation confidence: {corr_boost:.2f}")

                planned_tests.append(
                    PlannedTest(
                        test_id=test_id,
                        name=f"{ts.framework} Impacted Suite",
                        category="unit",
                        runner_cmd=ts.runner_cmd,
                        priority=priority,
                        selection_reason="; ".join(reasons),
                        estimated_duration_ms=est_dur,
                    )
                )
                explanations.append(
                    SelectionExplanation(
                        test_id=test_id,
                        selected=True,
                        priority=priority,
                        value_score=95.0,
                        reasons=reasons,
                        estimated_duration_ms=est_dur,
                    )
                )
            elif risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL) or not changed_only or not impact.has_changes or corr_boost > 0.4:
                priority = 85 if corr_boost > 0.4 else (80 if risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL) else 50)
                reasons = [
                    f"Scheduled for {risk.level.value} risk validation.",
                    f"Test count: ~{ts.test_count_estimate}",
                ]
                if corr_boost > 0:
                    reasons.append(f"Historically correlated with modified symbols (conf: {corr_boost:.2f})")

                planned_tests.append(
                    PlannedTest(
                        test_id=test_id,
                        name=f"{ts.framework} Suite",
                        category="unit",
                        runner_cmd=ts.runner_cmd,
                        priority=priority,
                        selection_reason="; ".join(reasons),
                        estimated_duration_ms=est_dur,
                    )
                )
                explanations.append(
                    SelectionExplanation(
                        test_id=test_id,
                        selected=True,
                        priority=priority,
                        value_score=75.0 if corr_boost > 0 else 50.0,
                        reasons=reasons,
                        estimated_duration_ms=est_dur,
                    )
                )
            else:
                skip_msg = f"No direct or transitive dependency to changed code ({risk.level.value} risk, changed-only mode)"
                skipped_tests.append(
                    SkippedTest(
                        test_id=f"test.{ts.framework}.skipped",
                        name=f"{ts.framework} Suite",
                        category="unit",
                        skip_reason=skip_msg,
                    )
                )
                explanations.append(
                    SelectionExplanation(
                        test_id=f"test.{ts.framework}.skipped",
                        selected=False,
                        priority=0,
                        value_score=10.0,
                        reasons=[],
                        skip_reason=skip_msg,
                        estimated_duration_ms=0.0,
                    )
                )

        if not planned_tests and not skipped_tests:
            planned_tests.append(
                PlannedTest(
                    test_id="test.sanity.integrity",
                    name="Workspace Integrity Check",
                    category="sanity",
                    runner_cmd="aegis sanity",
                    priority=50,
                    selection_reason="Preflight sanity check",
                    estimated_duration_ms=10.0,
                )
            )
            explanations.append(
                SelectionExplanation(
                    test_id="test.sanity.integrity",
                    selected=True,
                    priority=50,
                    value_score=50.0,
                    reasons=["Preflight workspace integrity check."],
                    estimated_duration_ms=10.0,
                )
            )

        total_time = sum(t.estimated_duration_ms for t in planned_tests)

        return TestPlan(
            plan_id=generate_id("plan"),
            risk_level=risk.level,
            selected_tests=planned_tests,
            skipped_tests=skipped_tests,
            total_planned=len(planned_tests),
            total_skipped=len(skipped_tests),
            estimated_total_time_ms=total_time,
            explanations=explanations,
            metadata={"has_changes": impact.has_changes, "risk_score": risk.composite_score},
        )
