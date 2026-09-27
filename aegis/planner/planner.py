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
    ) -> TestPlan:
        """
        Constructs an adaptive test plan:
        - Directly affected tests: Priority 100
        - API / Integration tests: Priority 80 (if APIs affected or High/Critical risk)
        - Baseline regression tests: Priority 50
        - Skips unaffected tests when changed_only is True and risk is LOW.
        """
        planned_tests: List[PlannedTest] = []
        skipped_tests: List[SkippedTest] = []

        affected_test_files = {e.file_path for e in impact.affected_tests}
        affected_api_count = len(impact.affected_apis)

        for ts in available_suites:
            # Check if this test suite contains affected test files
            suite_files = set(ts.test_files)
            overlapping_files = suite_files.intersection(affected_test_files)

            if overlapping_files:
                planned_tests.append(
                    PlannedTest(
                        test_id=f"test.{ts.framework}.impacted",
                        name=f"{ts.framework} Impacted Suite",
                        category="unit",
                        runner_cmd=ts.runner_cmd,
                        priority=100,
                        selection_reason=f"Directly exercises changed code in {len(overlapping_files)} file(s)",
                        estimated_duration_ms=ts.test_count_estimate * 20.0,
                    )
                )
            elif risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL) or not changed_only or not impact.has_changes:
                priority = 80 if risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL) else 50
                planned_tests.append(
                    PlannedTest(
                        test_id=f"test.{ts.framework}.regression",
                        name=f"{ts.framework} Suite",
                        category="unit",
                        runner_cmd=ts.runner_cmd,
                        priority=priority,
                        selection_reason=f"Scheduled for {risk.level.value} risk validation",
                        estimated_duration_ms=ts.test_count_estimate * 20.0,
                    )
                )
            else:
                # Safely skip
                skipped_tests.append(
                    SkippedTest(
                        test_id=f"test.{ts.framework}.skipped",
                        name=f"{ts.framework} Suite",
                        category="unit",
                        skip_reason=f"No direct or transitive dependency to changed code ({risk.level.value} risk)",
                    )
                )

        # If no tests were discovered, create a preflight integrity check
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

        total_time = sum(t.estimated_duration_ms for t in planned_tests)

        return TestPlan(
            plan_id=generate_id("plan"),
            risk_level=risk.level,
            selected_tests=planned_tests,
            skipped_tests=skipped_tests,
            total_planned=len(planned_tests),
            total_skipped=len(skipped_tests),
            estimated_total_time_ms=total_time,
            metadata={"has_changes": impact.has_changes, "risk_score": risk.composite_score},
        )
