"""
Aegis Performance Quality Runner
Executes deterministic performance measurements, environment fingerprinting, and statistical baseline comparisons.
"""

from __future__ import annotations
import time
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

from aegis.runners.base import ExecutionContext
from aegis.quality.base import QualityRunner
from aegis.quality.models import (
    QualityDimension,
    QualityCapability,
    QualityResult,
    QualityEvidence,
    QualityStatus,
    ExecutionMode,
    ValidationStrength,
    EvidenceKind,
    QualityBaseline,
    PerformanceMeasurement,
    PerformanceTrend,
)
from aegis.quality.performance.environment import EnvironmentFingerprint
from aegis.quality.performance.benchmarks import BenchmarkEngine


class PerformanceRunner(QualityRunner):
    """Universal Performance Runner for execution latency, startup benchmarks, and resource profiling."""

    def __init__(self, workspace_root: Path | str) -> None:
        super().__init__(workspace_root)

    @property
    def dimension(self) -> QualityDimension:
        return QualityDimension.PERFORMANCE

    @property
    def capability(self) -> QualityCapability:
        return QualityCapability(
            dimension=QualityDimension.PERFORMANCE,
            name="aegis_performance_runner",
            version="1.0.0",
            supported_adapters=["native_benchmark", "simulated_benchmark"],
            requires_browser=False,
            supports_baselines=True,
            supports_waivers=False,
        )

    def supports(self, context: ExecutionContext) -> bool:
        return context.category.value in ("performance", "api", "sanity", "all")

    def execute(self, context: ExecutionContext) -> QualityResult:
        start_time = time.time()
        opts = context.options or {}
        simulate = opts.get("simulate", False) or opts.get("dry_run", False) or context.dry_run
        iterations = opts.get("iterations", 3)
        tolerance = opts.get("tolerance", 0.10)  # 10% margin of error

        env_info = EnvironmentFingerprint.capture(tree_hash=opts.get("tree_hash", ""))
        env_fp = env_info["fingerprint_hash"]

        exec_mode = ExecutionMode.SIMULATED if simulate else ExecutionMode.REAL
        val_strength = ValidationStrength.SIMULATED if simulate else ValidationStrength.AUTHORITATIVE

        measurements: List[PerformanceMeasurement] = []
        evidence_list: List[QualityEvidence] = []

        if simulate:
            m_startup = PerformanceMeasurement.from_samples(
                metric="cli_startup_latency_ms",
                samples=[45.2, 46.1, 44.8],
                unit="ms",
                env_fingerprint=env_fp,
                tool_source="simulated_benchmark",
            )
            measurements.append(m_startup)
        else:
            # Measure python startup or target command
            custom_cmd = opts.get("benchmark_command")
            cmd = custom_cmd if custom_cmd else [sys.executable, "-c", "import aegis"]
            m_startup = BenchmarkEngine.measure_command(
                cmd=cmd,
                cwd=str(self.workspace_root),
                iterations=iterations,
                env_fingerprint=env_fp,
                metric_name="python_runtime_startup_ms",
            )
            measurements.append(m_startup)

        # Baseline comparison
        baseline_obj: Optional[QualityBaseline] = opts.get("baseline")
        comparison_results: Dict[str, Any] = {}
        has_regression = False
        incompatible_env = False

        if baseline_obj and baseline_obj.measurements:
            # Check environment compatibility
            baseline_env = baseline_obj.metadata.get("environment", {})
            if baseline_env and not EnvironmentFingerprint.are_compatible(env_info, baseline_env):
                incompatible_env = True
                comparison_results["environment_warning"] = "Baseline environment differs from current runtime."

            for m in measurements:
                base_val = baseline_obj.measurements.get(m.metric)
                if base_val is not None and not incompatible_env:
                    diff_pct = (m.median - base_val) / max(base_val, 1e-6)
                    if diff_pct > tolerance:
                        trend = PerformanceTrend.REGRESSED
                        has_regression = True
                    elif diff_pct < -tolerance:
                        trend = PerformanceTrend.IMPROVED
                    else:
                        trend = PerformanceTrend.STABLE

                    comparison_results[m.metric] = {
                        "baseline_median": base_val,
                        "current_median": m.median,
                        "diff_pct": round(diff_pct * 100, 2),
                        "trend": trend.value,
                    }
                else:
                    comparison_results[m.metric] = {
                        "trend": PerformanceTrend.INSUFFICIENT_DATA.value,
                        "current_median": m.median,
                    }

        for m in measurements:
            ev = QualityEvidence(
                evidence_id=f"ev_perf_{m.metric}",
                kind=EvidenceKind.MEASURED if exec_mode == ExecutionMode.REAL else EvidenceKind.SIMULATED,
                description=f"Performance Metric: {m.metric} = {m.median:.2f} {m.unit} (p95: {m.p95:.2f} {m.unit})",
                raw_data={"samples": m.samples, "unit": m.unit, "count": m.sample_count},
                provenance={"env_fingerprint": env_fp, "tool": m.tool_source},
            )
            evidence_list.append(ev)

        status: QualityStatus
        if exec_mode == ExecutionMode.SIMULATED:
            status = QualityStatus.SIMULATED
        elif has_regression:
            status = QualityStatus.FAIL
        else:
            status = QualityStatus.PASS

        duration_ms = (time.time() - start_time) * 1000

        return QualityResult(
            dimension=QualityDimension.PERFORMANCE,
            runner_id=self.capability.name,
            status=status,
            execution_mode=exec_mode,
            validation_strength=val_strength,
            measurements=measurements,
            evidence=evidence_list,
            confidence=1.0 if exec_mode == ExecutionMode.REAL else 0.8,
            duration_ms=duration_ms,
            environment=env_info,
            comparison_summary=comparison_results,
        )
