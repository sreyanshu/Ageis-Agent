"""
Aegis Accessibility Quality Runner
Executes accessibility evaluations (WCAG 2.1 AA/AAA) via axe-core adapters or offline analyzers.
"""

from __future__ import annotations
import time
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
    EvidenceKind,
    Waiver,
    QualityBaseline,
)
from aegis.quality.accessibility.adapter import AccessibilityAdapter, AxeCoreAdapter, SimulatedAxeAdapter


class AccessibilityRunner(QualityRunner):
    """Universal Accessibility Runner for web applications, routes, and UI components."""

    def __init__(self, workspace_root: Path | str, adapter: Optional[AccessibilityAdapter] = None) -> None:
        super().__init__(workspace_root)
        self.adapter = adapter or AxeCoreAdapter()
        self.simulated_adapter = SimulatedAxeAdapter()

    @property
    def dimension(self) -> QualityDimension:
        return QualityDimension.ACCESSIBILITY

    @property
    def capability(self) -> QualityCapability:
        return QualityCapability(
            dimension=QualityDimension.ACCESSIBILITY,
            name="aegis_accessibility_runner",
            version="1.0.0",
            supported_adapters=["axe-core", "simulated-axe"],
            requires_browser=True,
            supports_baselines=True,
            supports_waivers=True,
        )

    def supports(self, context: ExecutionContext) -> bool:
        # Supports if context category is accessibility, ui, e2e, or all
        return context.category.value in ("accessibility", "ui", "e2e", "all")

    def normalize_impact(self, impact: Optional[str]) -> FindingSeverity:
        mapping = {
            "critical": FindingSeverity.CRITICAL,
            "serious": FindingSeverity.HIGH,
            "moderate": FindingSeverity.MEDIUM,
            "minor": FindingSeverity.LOW,
        }
        return mapping.get((impact or "").lower(), FindingSeverity.MEDIUM)

    def execute(self, context: ExecutionContext) -> QualityResult:
        start_time = time.time()
        opts = context.options or {}
        simulate = opts.get("simulate", False) or opts.get("dry_run", False) or context.dry_run

        target = context.target_files[0] if context.target_files else str(self.workspace_root)

        # Check adapter availability
        active_adapter: AccessibilityAdapter
        exec_mode: ExecutionMode
        val_strength: ValidationStrength

        if not self.adapter.is_available():
            if not simulate:
                duration_ms = (time.time() - start_time) * 1000
                return QualityResult(
                    dimension=QualityDimension.ACCESSIBILITY,
                    runner_id=self.capability.name,
                    status=QualityStatus.UNAVAILABLE,
                    execution_mode=ExecutionMode.REAL,
                    validation_strength=ValidationStrength.AUTHORITATIVE,
                    duration_ms=duration_ms,
                    error_message="Axe-core / Playwright browser substrate is unavailable in the host environment.",
                )
            else:
                active_adapter = self.simulated_adapter
                exec_mode = ExecutionMode.SIMULATED
                val_strength = ValidationStrength.SIMULATED
        else:
            if simulate:
                active_adapter = self.simulated_adapter
                exec_mode = ExecutionMode.SIMULATED
                val_strength = ValidationStrength.SIMULATED
            else:
                active_adapter = self.adapter
                exec_mode = ExecutionMode.REAL
                val_strength = ValidationStrength.AUTHORITATIVE

        try:
            raw_violations = active_adapter.scan_target(target, options=opts)
        except Exception as ex:
            duration_ms = (time.time() - start_time) * 1000
            return QualityResult(
                dimension=QualityDimension.ACCESSIBILITY,
                runner_id=self.capability.name,
                status=QualityStatus.ERROR,
                execution_mode=exec_mode,
                validation_strength=val_strength,
                duration_ms=duration_ms,
                error_message=f"Accessibility scan failed with exception: {ex}",
            )

        findings: List[QualityFinding] = []
        evidence_list: List[QualityEvidence] = []

        for v in raw_violations:
            rule_id = v.get("id", "unknown-rule")
            sev = self.normalize_impact(v.get("impact"))
            nodes = v.get("nodes", [{}])

            for node in nodes:
                target_sel = " > ".join(node.get("target", ["unknown_element"]))
                html_snippet = node.get("html", "")
                failure_summary = node.get("failureSummary", v.get("description", ""))

                evidence_item = QualityEvidence(
                    evidence_id=f"ev_a11y_{rule_id}_{abs(hash(target_sel)) % 10000}",
                    kind=EvidenceKind.OBSERVED if exec_mode == ExecutionMode.REAL else EvidenceKind.SIMULATED,
                    description=failure_summary,
                    raw_data={"html": html_snippet, "tags": v.get("tags", [])},
                    provenance={"rule_id": rule_id, "target": target_sel, "help_url": v.get("helpUrl")},
                )
                evidence_list.append(evidence_item)

                finding = QualityFinding(
                    finding_id=f"a11y_{rule_id}_{abs(hash(target_sel)) % 10000}",
                    dimension=QualityDimension.ACCESSIBILITY,
                    severity=sev,
                    category="accessibility",
                    title=f"WCAG Violation: {v.get('help', rule_id)}",
                    description=v.get("description", failure_summary),
                    affected_target=target_sel,
                    evidence=[evidence_item],
                    provenance={
                        "rule_id": rule_id,
                        "file_path": target,
                        "tags": v.get("tags", []),
                        "help_url": v.get("helpUrl"),
                    },
                    confidence=1.0 if exec_mode == ExecutionMode.REAL else 0.8,
                    remediation_reference=v.get("helpUrl"),
                )
                finding.fingerprint = finding.compute_fingerprint()
                findings.append(finding)

        # Evaluate against baseline & waivers if provided
        baseline_obj: Optional[QualityBaseline] = opts.get("baseline")
        waivers_list: List[Waiver] = opts.get("waivers", [])
        classified_findings, comp_summary = self.evaluate_baseline(findings, baseline_obj, waivers_list)

        # Determine status
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
            dimension=QualityDimension.ACCESSIBILITY,
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
