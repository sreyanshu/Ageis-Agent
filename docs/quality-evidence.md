# Aegis Quality Evidence Model

## 1. Evidence Classification Taxonomy

Quality evidence records are tagged with concrete provenance and evidence kind:

| Evidence Kind | Source | Example |
| :--- | :--- | :--- |
| **`OBSERVED`** | Direct DOM / Browser State | Contrast ratio violation, missing label on button |
| **`MEASURED`** | Statistical Runtime Sample | Startup time median of 45.2ms across 5 iterations |
| **`SCANNED`** | External Tool Ingestion | SARIF SAST finding with file and line coordinates |
| **`DERIVED`** | Computed Analysis | Blast radius impact traversal, baseline delta |
| **`SIMULATED`** | Mocked Test Runtime | Offline synthetic check (cannot satisfy production gate) |

## 2. Quality Status Semantics

Aegis enforces non-collapsible quality status states:
- **`PASS`**: Evaluated cleanly with zero policy violations.
- **`FAIL`**: Un-waived critical or high findings detected.
- **`WARN`**: Medium or low findings detected within acceptable policy limits.
- **`SKIPPED`**: Intentionally bypassed by planner.
- **`NOT_APPLICABLE`**: Dimension not relevant to target stack.
- **`NOT_EXECUTED`**: Runner was not invoked.
- **`UNAVAILABLE`**: External runtime or scanner missing in host environment.
- **`ERROR`**: Scanner or runner threw an unhandled execution error.
- **`SIMULATED`**: Synthetic simulation execution.
