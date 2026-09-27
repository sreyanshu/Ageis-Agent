"""
Unit Tests for Aegis Objective UX Heuristics Engine
"""

from pathlib import Path
from aegis.quality.ux.heuristics import UXHeuristicEvaluator
from aegis.quality.ux.runner import UXRunner
from aegis.runners.base import ExecutionContext, RunnerCategory
from aegis.quality.models import FindingSeverity, QualityDimension, QualityStatus


def test_ux_heuristics_html_evaluation():
    sample_html = """
    <!DOCTYPE html>
    <html>
        <body>
            <h1>Main Title</h1>
            <h4>Skipped Subtitle</h4>
            <button class="icon-btn"></button>
            <a href="#">Placeholder link</a>
        </body>
    </html>
    """
    findings, evidence = UXHeuristicEvaluator.evaluate_html(sample_html, "sample.html")
    assert len(findings) == 3
    assert len(evidence) == 3

    categories = {f.category for f in findings}
    assert "unlabeled_control" in categories
    assert "dead_end_navigation" in categories
    assert "heading_hierarchy" in categories


def test_ux_journey_step_friction_evaluation():
    steps = [{"action": "click", "target": f"btn_{i}"} for i in range(16)]
    findings, evidence = UXHeuristicEvaluator.evaluate_journey(steps, "long_checkout_flow")
    assert len(findings) == 1
    assert findings[0].category == "excessive_steps"
    assert findings[0].severity == FindingSeverity.LOW


def test_ux_runner_clean_pass_and_workspace_scanning(tmp_path: Path):
    clean_html = """
    <html>
        <body>
            <h1>Welcome</h1>
            <h2>Section</h2>
            <button>Click Me</button>
            <a href="/login">Login</a>
        </body>
    </html>
    """
    (tmp_path / "index.html").write_text(clean_html)

    runner = UXRunner(tmp_path)
    ctx = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.UX,
        dry_run=False,
    )
    res = runner.execute(ctx)
    assert res.dimension == QualityDimension.UX
    assert res.status == QualityStatus.PASS
    assert len(res.findings) == 0
