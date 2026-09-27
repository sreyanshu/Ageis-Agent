from pathlib import Path
from aegis.core.orchestrator import AegisEngine
from aegis.core.config import AegisConfig
from aegis.evidence.models import EvidenceReport, TestResult, TestStatus, ReleaseGateVerdict


def test_orchestrator_init_and_discover(tmp_path: Path):
    engine = AegisEngine(workspace_root=tmp_path)
    cfg_path = engine.init_workspace()

    assert cfg_path.exists()
    assert (tmp_path / ".aegis" / "project-profile.json").exists()
    assert (tmp_path / ".aegis" / "architecture.json").exists()


def test_orchestrator_release_gate_blocked(tmp_path: Path):
    engine = AegisEngine(workspace_root=tmp_path)
    failing_report = EvidenceReport(
        report_id="rep_fail",
        correlation_id="corr_fail",
        project_name="fail_proj",
        tree_hash="hash1",
        total_tests=5,
        passed=4,
        failed=1,
        errors=0,
        test_results=[
            TestResult(
                test_id="t1",
                name="Critical API Test",
                status=TestStatus.FAILED,
            )
        ]
    )

    assessment = engine.assess_release_readiness(failing_report)
    assert assessment.verdict == ReleaseGateVerdict.BLOCKED
    assert assessment.failed_tests == 1


def test_orchestrator_release_gate_requires_review(tmp_path: Path):
    engine = AegisEngine(workspace_root=tmp_path)
    passing_report = EvidenceReport(
        report_id="rep_pass",
        correlation_id="corr_pass",
        project_name="pass_proj",
        tree_hash="hash2",
        total_tests=5,
        passed=5,
        failed=0,
        errors=0,
    )

    assessment = engine.assess_release_readiness(passing_report)
    # Default policy requires human approval for production deployment
    assert assessment.verdict == ReleaseGateVerdict.REQUIRES_REVIEW
    assert len(assessment.reasons) > 0
