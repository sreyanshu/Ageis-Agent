# Aegis Quality Dimensions Engine

## 1. Executive Summary & Architecture

The **Quality Dimensions Engine** extends Aegis from functional test orchestration into deterministic multi-dimensional production readiness validation across:

1. **Accessibility (a11y)**: WCAG 2.1 AA/AAA rule compliance, axe-core substrate adapters, DOM/selector targeting, and baseline waiver management.
2. **Security**: Robust SARIF v2.1.0 report ingestion (SAST, DAST, secrets, container scans), deterministic vulnerability fingerprinting, and baseline regression gating.
3. **Performance**: Statistical benchmark sampling (median, p95), latency/startup measurement, environment fingerprinting, and tolerance-based regression detection.
4. **UX Heuristics**: Deterministic objective signals (unlabeled controls, dead-end navigation, heading skips, journey interaction friction).

```text
                  PROJECT GRAPH + CHANGE IMPACT
                                │
                                ▼
                       QUALITY PLANNER
                    (Impact & Risk-Aware)
                                │
                                ▼
                      QUALITY REGISTRY
        ┌───────────────┬───────────────┬───────────────┐
        ▼               ▼               ▼               ▼
  ACCESSIBILITY     SECURITY       PERFORMANCE         UX
    (axe-core)       (SARIF)       (Benchmark)    (Heuristics)
        │               │               │               │
        └───────────────┴───────┬───────┴───────────────┘
                                ▼
                    QUALITY EVIDENCE MODEL
            (Observed, Measured, Scanned, Derived)
                                │
                                ▼
                     RELEASE POLICY GATE
          (Deterministic Policy & Waiver Evaluation)
```

---

## 2. Core Tenets

### 2.1 Evidence Authoritativeness & Real vs Simulated Semantics
- When external tooling (axe-core, browser, SARIF scanner) is unavailable in real execution mode, the status is strictly **`UNAVAILABLE`** or **`NOT_EXECUTED`**. It NEVER silently falls back to `PASS`.
- Simulation (`execution_mode = SIMULATED`, `validation_strength = SIMULATED`) is restricted to offline testing and cannot satisfy authoritative production release gates (`require_real_execution = true`).

### 2.2 Baseline & Waiver Management
- Every finding computes a deterministic fingerprint:
  $$\text{Fingerprint} = \text{SHA256}(\text{Dimension} + \text{RuleID} + \text{Target} + \text{SourceFile} + \text{Line})$$
- Findings are classified against stored baselines into `NEW`, `REGRESSED`, `EXISTING`, `RESOLVED`, or `WAIVED`.
- Waivers require an owner, rationale, policy reference, and expiration timestamp. Expired waivers immediately fail policy evaluation.
