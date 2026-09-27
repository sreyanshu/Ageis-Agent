"""
Unit Tests for Aegis Performance Engine & Environment Fingerprinting
"""

from pathlib import Path
from aegis.runners.base import ExecutionContext, RunnerCategory
from aegis.quality.performance.runner import PerformanceRunner
from aegis.quality.performance.environment import EnvironmentFingerprint
from aegis.quality.models import (
    QualityDimension,
    QualityStatus,
    QualityBaseline,
    PerformanceTrend,
)


def test_environment_fingerprint_capture_and_compatibility():
    env1 = EnvironmentFingerprint.capture("tree_1")
    assert "fingerprint_hash" in env1
    assert env1["fingerprint_hash"].startswith("env_")

    env2 = EnvironmentFingerprint.capture("tree_2")
    # Same machine has compatible environment
    assert EnvironmentFingerprint.are_compatible(env1, env2)

    # Incompatible OS/architecture simulation
    env_incompat = dict(env1)
    env_incompat["os_name"] = "DifferentOS"
    assert not EnvironmentFingerprint.are_compatible(env1, env_incompat)


def test_performance_runner_execution_and_baseline_regression(tmp_path: Path):
    runner = PerformanceRunner(tmp_path)
    
    # 1. Baseline with 20ms startup
    baseline = QualityBaseline(
        dimension=QualityDimension.PERFORMANCE,
        baseline_id="base_perf",
        tree_hash="tree_1",
        measurements={"python_runtime_startup_ms": 20.0},
        metadata={"environment": EnvironmentFingerprint.capture()},
    )

    ctx = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.PERFORMANCE,
        dry_run=False,
        options={
            "iterations": 2,
            "baseline": baseline,
            "tolerance": 0.05,  # 5% tolerance
        },
    )
    res = runner.execute(ctx)
    assert res.dimension == QualityDimension.PERFORMANCE
    assert len(res.measurements) > 0
    assert "python_runtime_startup_ms" in res.comparison_summary
    comp = res.comparison_summary["python_runtime_startup_ms"]
    assert "trend" in comp


def test_performance_environment_mismatch_warning(tmp_path: Path):
    runner = PerformanceRunner(tmp_path)
    
    # Incompatible environment in baseline
    mismatched_env = {"os_name": "WindowsNT", "machine_arch": "x86_32", "python_version": "2.7.0"}
    baseline = QualityBaseline(
        dimension=QualityDimension.PERFORMANCE,
        baseline_id="base_perf_mismatch",
        tree_hash="tree_1",
        measurements={"python_runtime_startup_ms": 10.0},
        metadata={"environment": mismatched_env},
    )

    ctx = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.PERFORMANCE,
        dry_run=False,
        options={"iterations": 1, "baseline": baseline},
    )
    res = runner.execute(ctx)
    assert "environment_warning" in res.comparison_summary
