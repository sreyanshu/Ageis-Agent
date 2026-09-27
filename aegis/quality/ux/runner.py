"""
Aegis UX Quality Runner
Executes objective UX heuristic evaluations against UI components, rendered HTML, and user journeys.
"""

from __future__ import annotations
import time
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional

from aegis.runners.base import ExecutionContext
from aegis.quality.base import QualityRunner
from aegis.quality.models import (
    QualityDimension,
    QualityCapability,
    QualityResult,
    QualityFinding,
    QualityEvidence,
    QualityStatus,
    ExecutionMode,
    ValidationStrength,
    FindingSeverity,
    QualityBaseline,
    Waiver,
)
from aegis.quality.ux.heuristics import UXHeuristicEvaluator


class UXRunner(QualityRunner):
    """Universal UX Runner assessing objective user experience signals and friction."""

    def __init__(self, workspace_root: Path | str) -> None:
        super().__init__(workspace_root)

    @property
    def dimension(self) -> QualityDimension:
        return QualityDimension.UX

    @property
    def capability(self) -> QualityCapability:
        return QualityCapability(
            dimension=QualityDimension.UX,
            name="aegis_ux_runner",
            version="1.0.0",
            supported_adapters=["heuristic_evaluator", "simulated_ux"],
            requires_browser=False,
            supports_baselines=True,
            supports_waivers=True,
        )

    def supports(self, context: ExecutionContext) -> bool:
        return context.category.value in ("ux", "ui", "e2e", "all")

    def execute(self, context: ExecutionContext) -> QualityResult:
        start_time = time.time()
        opts = context.options or {}
        simulate = opts.get("simulate", False) or opts.get("dry_run", False) or context.dry_run

        exec_mode = ExecutionMode.SIMULATED if simulate else ExecutionMode.REAL
        val_strength = ValidationStrength.SIMULATED if simulate else ValidationStrength.AUTHORITATIVE

        findings: List[QualityFinding] = []
        evidence_list: List[QualityEvidence] = []

        if simulate:
            sample_html = """
            <div>
                <h1>Dashboard</h1>
                <h4>Analytics</h4>
                <button></button>
                <a href="#">Learn More</a>
            </div>
            """
            f, ev = UXHeuristicEvaluator.evaluate_html(sample_html, "simulated_view.html")
            findings.extend(f)
            evidence_list.extend(ev)
        else:
            # Discover and evaluate HTML / template files in workspace
            html_files = glob.glob(str(self.workspace_root / "**" / "*.html"), recursive=True)
            for hf in html_files[:10]:  # Cap at first 10 for performance
                try:
                    content = Path(hf).read_text(encoding="utf-8", errors="ignore")
                    f, ev = UXHeuristicEvaluator.evaluate_html(content, str(Path(hf).relative_to(self.workspace_root)))
                    findings.extend(f)
                    evidence_list.extend(ev)
                except Exception:
                    pass

        # Baseline & waiver evaluation
        baseline_obj: Optional[QualityBaseline] = opts.get("baseline")
        waivers_list: List[Waiver] = opts.get("waivers", [])
        classified_findings, comp_summary = self.evaluate_baseline(findings, baseline_obj, waivers_list)

        has_critical = any(f.severity == FindingSeverity.CRITICAL for f in classified_findings)
        has_high = any(f.severity == FindingSeverity.HIGH for f in classified_findings)

        status: QualityStatus
        if exec_mode == ExecutionMode.SIMULATED:
            status = QualityStatus.SIMULATED
        elif not classified_findings:
            status = QualityStatus.PASS
        elif has_critical or has_high:
            status = QualityStatus.FAIL
        else:
            status = QualityStatus.WARN

        duration_ms = (time.time() - start_time) * 1000

        return QualityResult(
            dimension=QualityDimension.UX,
            runner_id=self.capability.name,
            status=status,
            execution_mode=exec_mode,
            validation_strength=val_strength,
            findings=classified_findings,
            evidence=evidence_list,
            confidence=1.0 if exec_mode == ExecutionMode.REAL else 0.8,
            duration_ms=duration_ms,
            comparison_summary=comp_summary,
        )
