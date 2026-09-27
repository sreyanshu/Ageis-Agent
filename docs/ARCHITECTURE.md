# AEGIS: Universal AI Quality Engineering & Production Readiness Platform
## Architecture & Technical Specification — Phase 1: Foundation

---

## 1. Executive Summary & Vision

**Aegis** is a universal, AI-assisted Quality Engineering and Production Readiness platform. It is engineered from first principles to be completely **IDE-agnostic, AI-provider-agnostic, and framework-agnostic**.

The foundational philosophy is:
> **Deterministic execution first. AI reasoning only where it provides additional value. Evidence is the source of truth.**

Aegis shifts quality engineering from manual, reactive, or brute-force testing to an **adaptive, evidence-backed, risk-optimized** lifecycle.

```
                  SOFTWARE CHANGE / TARGET REPO
                                │
                                ▼
                       PROJECT DISCOVERY
                    (Polyglot / Multi-Stack)
                                │
                                ▼
                      PROJECT INTELLIGENCE
                 (Graph / Symbol / Dependency)
                                │
                                ▼
                         IMPACT ANALYSIS
                     (AST / API / UI / Test)
                                │
                                ▼
                          RISK ENGINE
                                │
                                ▼
                         TEST SELECTION
                   (Utility = Value / Cost)
                                │
                ┌───────────────┴───────────────┐
                │                               │
        DETERMINISTIC ENGINES               AI REASONING
      (Unit, API, E2E, UI, Perf,         (Failure Root-Cause,
       A11y, Security, Sanity)            Context Compression)
                │                               │
                └───────────────┬───────────────┘
                                ▼
                       EVIDENCE COLLECTOR
                   (Normalized & Fingerprinted)
                                │
                                ▼
                       FAILURE INVESTIGATOR
                                │
                                ▼
                     RELEASE READINESS GATE
                   (Deterministic Policy-Based)
                                │
                                ▼
                          HUMAN APPROVAL
```

---

## 2. Non-Negotiable Core Architectural Tenets

### 2.1 AI-Agnostic Engine
- Core discovery, static analysis, graph compilation, impact analysis, test execution, evidence normalization, and release gating are 100% deterministic and function without any LLM configured or reachable.
- When AI reasoning is engaged (e.g. failure root cause synthesis, complex test synthesis), it is routed through an abstract `AIProvider` interface with strict token budgets, context compression, and cost routing.

### 2.2 IDE & Environment Agnostic
- Antigravity, Claude Code, Cursor, VS Code, JetBrains, CI/CD pipelines (GitHub Actions, GitLab CI), and automated agents consume Aegis via standard protocols:
  - High-performance CLI (`aegis ...`)
  - Model Context Protocol (MCP) tool adapter
  - Structured JSON / File IPC (`.aegis/`)
  - REST / RPC API
- Zero business logic resides inside IDE or UI integration layers.

### 2.3 Evidence-First & Machine-Verifiable
- AI opinions are never stored as ground truth.
- Every assertion is linked to raw evidence: exit codes, stderr/stdout, HTTP response dumps, visual diffs, accessibility violation trees, SARIF security records, OpenTelemetry trace spans, and timing profiles.

### 2.4 Token & Compute Economy
- Incremental hashing (SHA-256 content hashes, AST hashes, dependency tree hashes) ensures zero redundant computation.
- Log and stack trace compression fingerprints crashes so identical failures never trigger repeated LLM queries.

---

## 3. Monorepo & Component Structure

```
aegis/
├── core/
│   ├── config.py           # Configuration schema, environment overrides, YAML parser
│   ├── events.py           # Structured event bus, lifecycle events, correlation IDs
│   ├── executor.py         # Sandboxed process execution, timeout bounds, output streaming
│   ├── orchestrator.py     # Main engine lifecycle manager
│   └── exceptions.py       # Strongly-typed Aegis domain exceptions
├── discovery/
│   ├── detector.py         # Main ProjectDiscoveryEngine coordinator
│   ├── languages.py        # Polyglot language detectors (Python, TS, Go, Rust, Java, C#, etc.)
│   ├── frameworks.py       # Framework detectors (FastAPI, React, Spring, Express, Django, etc.)
│   ├── build_systems.py    # Build system detectors (npm, pnpm, yarn, poetry, cargo, maven, etc.)
│   ├── infrastructure.py   # Infrastructure detectors (Docker, Compose, K8s, Terraform, CI)
│   ├── interfaces.py       # Interface detectors (REST, GraphQL, gRPC, CLI, DB, Workers)
│   └── tests.py            # Test framework discovery (pytest, jest, vitest, go test, cargo test, junit)
├── storage/
│   ├── base.py             # Storage protocol & abstract base class
│   ├── filesystem.py       # File-based .aegis/ repository storage
│   └── hashing.py          # Content hashing, AST fingerprinting, cache manager
├── evidence/
│   ├── models.py           # Machine-verifiable schemas: TestResult, Evidence, Fingerprint, Report
│   ├── collector.py        # Structured evidence accumulator & trace correlator
│   └── normalizer.py       # Stack trace, log, and HTTP error normalizer/fingerprinter
├── adapters/
│   └── base.py             # Base TestRunner and ToolAdapter contracts (NOT_IMPLEMENTED markers)
└── cli/
    └── main.py             # Unified CLI entrypoint (Click/argparse based)
```

---

## 4. Phase 1 Data Models & Schemas

### 4.1 Project Profile (`.aegis/project-profile.json`)
Represents the comprehensive discovery artifact of the target repository:
```json
{
  "schema_version": "1.0.0",
  "project_name": "sample-service",
  "root_path": "/workspace",
  "fingerprint": "a1b2c3d4...",
  "languages": [
    {"name": "Python", "version_hint": "^3.11", "file_count": 42, "percentage": 78.5}
  ],
  "frameworks": [
    {"name": "FastAPI", "category": "backend", "confidence": 0.99, "version": "0.110.0"}
  ],
  "build_systems": [
    {"name": "poetry", "manifest": "pyproject.toml", "lockfile": "poetry.lock"}
  ],
  "infrastructure": {
    "has_docker": true,
    "has_compose": true,
    "has_k8s": false,
    "ci_providers": ["github-actions"]
  },
  "interfaces": [
    {"type": "rest", "entrypoints": ["/api/v1/health", "/api/v1/auth"]}
  ],
  "test_suites": [
    {"framework": "pytest", "test_count_estimate": 28, "directory": "tests/"}
  ]
}
```

### 4.2 Machine-Readable Evidence Model
```json
{
  "evidence_id": "evi_01HXYZ...",
  "correlation_id": "corr_98765...",
  "timestamp": "2026-09-27T16:30:00Z",
  "test_id": "test_auth_login_expired_token",
  "status": "FAILED",
  "duration_ms": 142.5,
  "runner": "pytest",
  "failure_fingerprint": "fp_sha256_e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "normalized_error": {
    "exception_type": "HTTPStatusError",
    "message": "Expected 401 Unauthorized, received 500 Internal Server Error",
    "top_stack_frame": "tests/test_auth.py:45 in test_auth_login_expired_token"
  },
  "raw_artifacts": [
    {"kind": "stdout", "path": ".aegis/artifacts/test_auth_stdout.log"},
    {"kind": "http_dump", "path": ".aegis/artifacts/http_dump_401.json"}
  ],
  "deterministic_verdict": false
}
```

---

## 5. Execution Sandboxing & Safety

All target execution (unit tests, build commands, sanity probes) executes via `ProcessExecutor`:
1. **Bounded Execution**: Strict timeouts with graceful SIGTERM and forceful SIGKILL.
2. **Resource Limits**: Configurable memory/process boundaries.
3. **Environment Scrubbing**: Secrets in environment variables are masked by default.
4. **Non-destructive Defaults**: Dry-run mode allows inspecting command plans without modifying repository state.

---

## 6. Roadmap to Full Autonomy

- **Phase 1 (Complete Foundation)**: Discovery, Config, CLI, Evidence Schemas, Execution Engine, Storage, Hashing, Fixtures.
- **Phase 2 (Project Intelligence & Graph)**: AST parsing, Dependency Graph, Change Impact Analysis, Risk Engine.
- **Phase 3 (Core Test Runners)**: Native Unit, API, Sanity, Integration, Playwright E2E/UI runners.
- **Phase 4 (Quality Dimensions)**: A11y, UX heuristic engine, Security scanning (SARIF), Performance baselines.
- **Phase 5 (AI Investigation & Routing)**: LLM abstraction, failure correlation, context compression, cost routing.
- **Phase 6 (Controlled Self-Healing)**: Bounded patch proposal loops, patch verification, regression checking.
- **Phase 7 (Release Gate)**: Deterministic policy evaluator (pass/fail release readiness verdict).
- **Phase 8 (Integrations)**: MCP Server, Antigravity plugin, GitHub Actions CI action, REST API.
