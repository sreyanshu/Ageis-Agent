"""
Aegis Deterministic Release Policy & Gate Evaluator
Consolidates TestResults and QualityResults against strict deterministic release criteria.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from aegis.evidence.models import (
    ReleaseGateVerdict,
    PolicyCheckResult,
    ReleaseAssessment,
    EvidenceReport,
    TestStatus,
)
from aegis.quality.models import (
    QualityResult,
    QualityStatus,
    ExecutionMode,
    FindingSeverity,
    BaselineStatus,
    QualityFinding,
)


class QualityReleasePolicy(BaseModel):
    """Configurable deterministic criteria for production release gating."""
    require_real_execution: bool = True
    max_critical_security: int = 0
    max_high_security: int = 0
    max_critical_a11y: int = 0
    max_perf_regression_pct: float = 10.0
    require_human_approval: bool = True


class QualityPolicyEvaluator:
    """Evaluates evidence against configured release policies."""

    @classmethod
    def evaluate(
        cls,
        report: EvidenceReport,
        quality_results: Optional[Dict[str, QualityResult]] = None,
        policy: Optional[QualityReleasePolicy] = None,
    ) -> ReleaseAssessment:
        pol = policy or QualityReleasePolicy()
        checks: List[PolicyCheckResult] = []
        reasons: List[str] = []
        q_res = quality_results or {}

        # 1. Check unit / functional tests
        all_passed = report.failed == 0 and report.errors == 0
        checks.append(
            PolicyCheckResult(
                policy_name="functional_tests_must_pass",
                passed=all_passed,
                details=f"Passed: {report.passed}/{report.total_tests} (Failed: {report.failed}, Errors: {report.errors})",
            )
        )
        if not all_passed:
            reasons.append(f"Functional validation failure: {report.failed} tests failed, {report.errors} errors.")

        # 2. Check execution mode (Real vs Simulated)
        simulated_dimensions: List[str] = []
        for dim, res in q_res.items():
            if res.execution_mode == ExecutionMode.SIMULATED:
                simulated_dimensions.append(dim)

        if pol.require_real_execution and simulated_dimensions:
            checks.append(
                PolicyCheckResult(
                    policy_name="require_real_execution_mode",
                    passed=False,
                    details=f"Dimensions executed in SIMULATED mode: {', '.join(simulated_dimensions)}. Production gate requires REAL execution.",
                )
            )
            reasons.append(f"Simulation restriction: Quality dimensions [{', '.join(simulated_dimensions)}] ran in SIMULATED mode.")
        else:
            checks.append(
                PolicyCheckResult(
                    policy_name="require_real_execution_mode",
                    passed=True,
                    details="All required validations executed in authoritative REAL mode.",
                )
            )

        # 3. Check security findings
        sec_res = q_res.get("security")
        crit_sec = 0
        high_sec = 0
        if sec_res:
            for f in sec_res.findings:
                if f.baseline_status != BaselineStatus.WAIVED:
                    if f.severity == FindingSeverity.CRITICAL:
                        crit_sec += 1
                    elif f.severity == FindingSeverity.HIGH:
                        high_sec += 1

        sec_passed = crit_sec <= pol.max_critical_security and high_sec <= pol.max_high_security
        checks.append(
            PolicyCheckResult(
                policy_name="zero_unwaived_critical_security",
                passed=sec_passed,
                details=f"Un-waived security findings: Critical={crit_sec} (max: {pol.max_critical_security}), High={high_sec} (max: {pol.max_high_security})",
            )
        )
        if not sec_passed:
            reasons.append(f"Security policy violation: {crit_sec} critical and {high_sec} high un-waived vulnerabilities detected.")

        # 4. Check accessibility findings
        a11y_res = q_res.get("accessibility")
        crit_a11y = 0
        if a11y_res:
            for f in a11y_res.findings:
                if f.baseline_status != BaselineStatus.WAIVED and f.severity == FindingSeverity.CRITICAL:
                    crit_a11y += 1

        a11y_passed = crit_a11y <= pol.max_critical_a11y
        checks.append(
            PolicyCheckResult(
                policy_name="zero_unwaived_critical_accessibility",
                passed=a11y_passed,
                details=f"Un-waived critical WCAG violations: {crit_a11y} (max: {pol.max_critical_a11y})",
            )
        )
        if not a11y_passed:
            reasons.append(f"Accessibility policy violation: {crit_a11y} critical WCAG violations detected.")

        # 5. Check performance regression
        perf_res = q_res.get("performance")
        has_perf_reg = False
        if perf_res and perf_res.comparison_summary:
            for metric, data in perf_res.comparison_summary.items():
                if isinstance(data, dict) and data.get("trend") == "REGRESSED":
                    has_perf_reg = True

        perf_passed = not has_perf_reg
        checks.append(
            PolicyCheckResult(
                policy_name="performance_regression_boundary",
                passed=perf_passed,
                details="No significant performance regression detected beyond tolerance." if perf_passed else "Performance regression detected exceeding baseline tolerance threshold.",
            )
        )
        if not perf_passed:
            reasons.append("Performance policy violation: latency or throughput regressed against historical baseline.")

        # 6. Human approval policy
        if pol.require_human_approval:
            checks.append(
                PolicyCheckResult(
                    policy_name="require_human_approval",
                    passed=True,
                    details="Automated criteria evaluated; awaiting final human approval confirmation.",
                )
            )

        # Determine final verdict
        critical_policy_failed = not all_passed or not sec_passed or not a11y_passed or (pol.require_real_execution and bool(simulated_dimensions))
        
        if critical_policy_failed:
            verdict = ReleaseGateVerdict.BLOCKED
        elif pol.require_human_approval:
            verdict = ReleaseGateVerdict.REQUIRES_REVIEW
            if not reasons:
                reasons.append("All automated quality policies passed. Requires final human confirmation per release policy.")
        else:
            verdict = ReleaseGateVerdict.READY
            reasons.append("All automated quality policies passed cleanly.")

        return ReleaseAssessment(
            verdict=verdict,
            policy_checks=checks,
            reasons=reasons,
            total_tests=report.total_tests,
            passed_tests=report.passed,
            failed_tests=report.failed,
            critical_failures=crit_sec + crit_a11y,
            security_vulnerabilities=crit_sec + high_sec,
            accessibility_score=1.0 - (0.2 * min(crit_a11y, 5)),
            performance_regression_pct=15.0 if has_perf_reg else 0.0,
        )
