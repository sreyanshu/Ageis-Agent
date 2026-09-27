"""
Aegis Performance Measurement & Benchmark Utilities
Deterministic execution timing, latency sampling, and statistical aggregation.
"""

from __future__ import annotations
import time
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path

from aegis.quality.models import PerformanceMeasurement


class BenchmarkEngine:
    """Executes deterministic multi-sample benchmarks."""

    @staticmethod
    def measure_command(
        cmd: List[str],
        cwd: str,
        iterations: int = 3,
        env_fingerprint: str = "",
        metric_name: str = "command_duration_ms",
    ) -> PerformanceMeasurement:
        """Runs a command multiple times and records execution time distribution."""
        samples: List[float] = []
        for _ in range(max(1, iterations)):
            t0 = time.perf_counter()
            try:
                subprocess.run(
                    cmd,
                    cwd=cwd,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
            except Exception:
                pass
            elapsed = (time.perf_counter() - t0) * 1000.0
            samples.append(round(elapsed, 2))

        return PerformanceMeasurement.from_samples(
            metric=metric_name,
            samples=samples,
            unit="ms",
            env_fingerprint=env_fingerprint,
            tool_source="subprocess_benchmark",
            metadata={"command": " ".join(cmd), "iterations": iterations},
        )

    @staticmethod
    def measure_function(
        fn,
        iterations: int = 5,
        env_fingerprint: str = "",
        metric_name: str = "function_latency_ms",
    ) -> PerformanceMeasurement:
        """Executes a callable multiple times."""
        samples: List[float] = []
        for _ in range(max(1, iterations)):
            t0 = time.perf_counter()
            fn()
            elapsed = (time.perf_counter() - t0) * 1000.0
            samples.append(round(elapsed, 2))

        return PerformanceMeasurement.from_samples(
            metric=metric_name,
            samples=samples,
            unit="ms",
            env_fingerprint=env_fingerprint,
            tool_source="in_process_benchmark",
            metadata={"iterations": iterations},
        )
