"""
Unit Tests for Aegis Accessibility Engine & Adapters
"""

from pathlib import Path
from aegis.runners.base import ExecutionContext, RunnerCategory
from aegis.quality.accessibility.runner import AccessibilityRunner
from aegis.quality.accessibility.adapter import SimulatedAxeAdapter, AccessibilityAdapter
from aegis.quality.models import (
    QualityDimension,
    QualityStatus,
    ExecutionMode,
    ValidationStrength,
    FindingSeverity,
    QualityBaseline,
    Waiver,
    BaselineStatus,
)


class MockUnavailableA11yAdapter(AccessibilityAdapter):
    @property
    def adapter_name(self) -> str:
        return "mock-unavailable"

    def is_available(self) -> bool:
        return False

    def scan_target(self, target: str, options=None):
        raise RuntimeError("Browser unavailable")


def test_accessibility_runner_unavailable_without_simulation(tmp_path: Path):
    runner = AccessibilityRunner(tmp_path, adapter=MockUnavailableA11yAdapter())
    ctx = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.ACCESSIBILITY,
        dry_run=False,
        options={"simulate": False},
    )
    result = runner.execute(ctx)
    # MUST be UNAVAILABLE, never PASS!
    assert result.status == QualityStatus.UNAVAILABLE
    assert result.execution_mode == ExecutionMode.REAL
    assert "unavailable" in (result.error_message or "").lower()


def test_accessibility_runner_simulated_execution(tmp_path: Path):
    runner = AccessibilityRunner(tmp_path, adapter=SimulatedAxeAdapter())
    ctx = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.ACCESSIBILITY,
        dry_run=True,
        options={"simulate": True},
    )
    result = runner.execute(ctx)
    assert result.status == QualityStatus.SIMULATED
    assert result.execution_mode == ExecutionMode.SIMULATED
    assert result.validation_strength == ValidationStrength.SIMULATED
    assert len(result.findings) >= 2
    # Verify WCAG findings normalized correctly
    image_alt = next((f for f in result.findings if "image-alt" in f.provenance.get("rule_id", "")), None)
    assert image_alt is not None
    assert image_alt.severity == FindingSeverity.CRITICAL


def test_accessibility_baseline_and_waiver_classification(tmp_path: Path):
    runner = AccessibilityRunner(tmp_path, adapter=SimulatedAxeAdapter())
    
    # First execution to get finding fingerprints
    ctx1 = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.ACCESSIBILITY,
        dry_run=True,
        options={"simulate": True},
    )
    res1 = runner.execute(ctx1)
    fps = [f.fingerprint for f in res1.findings]
    assert len(fps) >= 2

    # Create baseline with 1 existing finding, and 1 waiver for the second
    baseline = QualityBaseline(
        dimension=QualityDimension.ACCESSIBILITY,
        baseline_id="base_1",
        tree_hash="tree_hash_1",
        findings_fingerprints=[fps[0]],
    )
    waiver = Waiver(
        finding_fingerprint=fps[1],
        dimension=QualityDimension.ACCESSIBILITY,
        reason="Approved temporary contrast waiver for dark mode rollout",
        owner="design-system-team",
    )

    ctx2 = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.ACCESSIBILITY,
        dry_run=True,
        options={"simulate": True, "baseline": baseline, "waivers": [waiver]},
    )
    res2 = runner.execute(ctx2)
    
    # Verify status classification
    statuses = {f.fingerprint: f.baseline_status for f in res2.findings}
    assert statuses[fps[0]] == BaselineStatus.EXISTING
    assert statuses[fps[1]] == BaselineStatus.WAIVED
