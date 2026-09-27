"""
Aegis Security Quality Runner
Executes SAST/DAST/Dependency/Secret scanner analysis via SARIF ingestion and normalizes results.
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
    Waiver,
    QualityBaseline,
)
from aegis.quality.security.adapter import SecurityAdapter, SARIFSecurityAdapter, SimulatedSecurityAdapter


class SecurityRunner(QualityRunner):
    """Universal Security Runner for codebases, APIs, and infrastructure configurations."""

    def __init__(self, workspace_root: Path | str, adapter: Optional[SecurityAdapter] = None) -> None:
        super().__init__(workspace_root)
        self.adapter = adapter or SARIFSecurityAdapter(self.workspace_root)
        self.simulated_adapter = SimulatedSecurityAdapter()

    @property
    def dimension(self) -> QualityDimension:
        return QualityDimension.SECURITY

    @property
    def capability(self) -> QualityCapability:
        return QualityCapability(
            dimension=QualityDimension.SECURITY,
            name="aegis_security_runner",
            version="1.0.0",
            supported_adapters=["sarif-ingestion", "simulated-security"],
            requires_browser=False,
            supports_baselines=True,
            supports_waivers=True,
        )

    def supports(self, context: ExecutionContext) -> bool:
        return context.category.value in ("security", "api", "sanity", "all")

    def execute(self, context: ExecutionContext) -> QualityResult:
        start_time = time.time()
        opts = context.options or {}
        simulate = opts.get("simulate", False) or opts.get("dry_run", False) or context.dry_run

        active_adapter: SecurityAdapter
        exec_mode: ExecutionMode
        val_strength: ValidationStrength

        if not self.adapter.is_available():
            if not simulate:
                duration_ms = (time.time() - start_time) * 1000
                return QualityResult(
                    dimension=QualityDimension.SECURITY,
                    runner_id=self.capability.name,
                    status=QualityStatus.UNAVAILABLE,
                    execution_mode=ExecutionMode.REAL,
                    validation_strength=ValidationStrength.AUTHORITATIVE,
                    duration_ms=duration_ms,
                    error_message="No SARIF reports or security scanners found in workspace.",
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
            findings, evidence_list = active_adapter.ingest_findings(options=opts)
        except Exception as ex:
            duration_ms = (time.time() - start_time) * 1000
            return QualityResult(
                dimension=QualityDimension.SECURITY,
                runner_id=self.capability.name,
                status=QualityStatus.ERROR,
                execution_mode=exec_mode,
                validation_strength=val_strength,
                duration_ms=duration_ms,
                error_message=f"Security report ingestion failed: {ex}",
            )

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
            dimension=QualityDimension.SECURITY,
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
