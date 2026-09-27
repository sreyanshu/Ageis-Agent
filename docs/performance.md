# Aegis Performance Quality Dimension

## 1. Deterministic Benchmarking & Sampling

The Performance Runner collects multi-sample measurements across key lifecycle metrics:
- Python/Node runtime startup latency (`ms`)
- CLI command execution duration (`ms`)
- HTTP/REST endpoint response latency (`ms`)
- Memory RSS footprint (`MB`)

Sample distributions record `min`, `max`, `median`, and `p95`.

## 2. Environment Fingerprinting

Performance comparisons require runtime compatibility context:
- OS name & release
- Machine CPU architecture (e.g. `arm64`, `x86_64`)
- CPU core count
- Python and Node runtime versions

Incompatible environments trigger an `environment_warning` and prevent false regression failures.

## 3. Baseline Comparison

Trends are evaluated against stored baselines with a configurable tolerance margin (default 10%):
- `diff_pct > tolerance`: `PerformanceTrend.REGRESSED`
- `diff_pct < -tolerance`: `PerformanceTrend.IMPROVED`
- Otherwise: `PerformanceTrend.STABLE`
