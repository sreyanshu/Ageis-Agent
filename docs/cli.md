# Aegis Command Line Interface (CLI)

The Aegis CLI exposes deterministic quality engineering, project discovery, test execution, quality dimension evaluation, historical analysis, and release gating workflows.

---

## 1. Primary Commands

### `aegis init`
Initializes a repository, performs complete project discovery, indexes AST symbols, builds the project intelligence graph, registers active adapters, and creates `.aegis/project-profile.json`.
```bash
aegis init
```

### `aegis project`
Inspects the canonical project profile and discovered capabilities.
```bash
aegis project
aegis project --json
```

### `aegis capabilities`
Lists all detected, supported, and configured project capabilities.
```bash
aegis capabilities
aegis capabilities --json
```

### `aegis adapters`
Lists all registered technology adapters and their active status for the current workspace.
```bash
aegis adapters
aegis adapters --json
```

### `aegis check`
High-level unified verification workflow orchestrating discovery, change impact, risk evaluation, adaptive test execution, quality dimension evaluation, and release policy gating.
```bash
aegis check
aegis check --dry-run
aegis check --all
aegis check --json
```

### `aegis release`
Evaluates release readiness policies against the latest execution and quality evidence, returning a deterministic release verdict (`READY`, `REQUIRES_REVIEW`, `BLOCKED`).
```bash
aegis release
aegis release --json
```

---

## 2. Additional Inspection & Execution Commands

- `aegis discover`: Polyglot repository discovery summary.
- `aegis graph`: Project intelligence graph inspection and build.
- `aegis impact`: Change impact and blast radius assessment.
- `aegis risk`: Deterministic adaptive risk scoring.
- `aegis plan`: Impact and risk-based adaptive test planning.
- `aegis test`: Universal test execution engine across runners.
- `aegis quality`: Multi-dimensional quality scans (Security, A11y, Perf, UX).
- `aegis history`: Historical execution, failure clustering, and quality findings log.
- `aegis analyze`: Flakiness, test effectiveness, and test redundancy analytics.
