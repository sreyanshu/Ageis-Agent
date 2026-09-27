"""
Unit Tests for Aegis Quality Planner & Deterministic Release Gate
"""

from pathlib import Path
from aegis.impact.models import ImpactReport, AffectedEntity, ConfidenceLevel, BlastRadius
from aegis.planner.models import RiskAssessment, RiskLevel
from aegis.quality.planner import QualityPlanner
from aegis.quality.models import (
    QualityDimension,
    QualityResult,
    QualityStatus,
    ExecutionMode,
    ValidationStrength,
    FindingSeverity,
    QualityFinding,
    BaselineStatus,
)
from aegis.evidence.models import EvidenceReport, ReleaseGateVerdict
from aegis.quality.gate import QualityPolicyEvaluator, QualityReleasePolicy


def test_quality_planner_impact_aware_selection():
    # 1. UI changes only
    ui_impact = ImpactReport(
        report_id="imp_1",
        tree_hash="hash1",
        has_changes=True,
        affected_ui=[AffectedEntity(id="ui.HeroBanner", name="HeroBanner", entity_type="ui", file_path="Hero.tsx", confidence=ConfidenceLevel.DIRECT)],
        blast_radius=BlastRadius(direct_count=1, total_affected=1),
    )
    plan_ui = QualityPlanner.plan(impact=ui_impact, mode="changed-only")
    selected_dims = {item.dimension for item in plan_ui.selected_dimensions}
    assert QualityDimension.ACCESSIBILITY in selected_dims
    assert QualityDimension.UX in selected_dims
    assert QualityDimension.PERFORMANCE not in selected_dims

    # 2. Full mode selects all
    plan_full = QualityPlanner.plan(impact=ui_impact, mode="full")
    assert plan_full.total_selected == 4


def test_release_gate_simulation_restriction():
    report = EvidenceReport(
        report_id="rep_1",
        correlation_id="corr_1",
        project_name="TestApp",
        tree_hash="tree_1",
        total_tests=10,
        passed=10,
    )
    
    # One quality dimension ran in SIMULATED mode
    q_res = {
        "accessibility": QualityResult(
            dimension=QualityDimension.ACCESSIBILITY,
            runner_id="a11y_sim",
            status=QualityStatus.SIMULATED,
            execution_mode=ExecutionMode.SIMULATED,
            validation_strength=ValidationStrength.SIMULATED,
        )
    }

    # Strict production release policy
    assessment = QualityPolicyEvaluator.evaluate(
        report=report,
        quality_results=q_res,
        policy=QualityReleasePolicy(require_real_execution=True, require_human_approval=False),
    )
    # MUST be BLOCKED because of simulation restriction!
    assert assessment.verdict == ReleaseGateVerdict.BLOCKED
    assert any("SIMULATED" in r for r in assessment.reasons)


def test_release_gate_unwaived_critical_security():
    report = EvidenceReport(
        report_id="rep_2",
        correlation_id="corr_2",
        project_name="TestApp",
        tree_hash="tree_1",
        total_tests=10,
        passed=10,
    )
    
    q_res = {
        "security": QualityResult(
            dimension=QualityDimension.SECURITY,
            runner_id="sec_runner",
            status=QualityStatus.FAIL,
            execution_mode=ExecutionMode.REAL,
            validation_strength=ValidationStrength.AUTHORITATIVE,
            findings=[
                QualityFinding(
                    finding_id="sec_1",
                    dimension=QualityDimension.SECURITY,
                    severity=FindingSeverity.CRITICAL,
                    category="security",
                    title="Critical RCE",
                    description="Unvalidated user input executed in eval",
                    affected_target="exec.py:12",
                    baseline_status=BaselineStatus.NEW,
                )
            ],
        )
    }

    assessment = QualityPolicyEvaluator.evaluate(
        report=report,
        quality_results=q_res,
        policy=QualityReleasePolicy(require_real_execution=True, require_human_approval=False),
    )
    assert assessment.verdict == ReleaseGateVerdict.BLOCKED
    assert assessment.security_vulnerabilities >= 1
