# AEGIS: Universal AI Quality Engineering & Production Readiness Platform
## Architecture & Technical Specification — Phase 2: Intelligence Layer

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
                 (AST Symbol Index & Graph DB)
                                │
                                ▼
                         IMPACT ANALYSIS
                 (AST Diff & Downstream Traversal)
                                │
                                ▼
                           RISK ENGINE
                  (Deterministic Factor Model)
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

## 2. Core Architectural Tenets

### 2.1 AI-Agnostic Core
- Discovery, AST parsing, symbol indexing, dependency graph compilation, impact analysis, risk scoring, test planning, execution sandboxing, evidence normalization, and release gating are 100% deterministic and function without any LLM configured.

### 2.2 IDE & Environment Agnostic
- Antigravity, Claude Code, Cursor, VS Code, JetBrains, and CI/CD pipelines consume Aegis via standard protocols: CLI (`aegis`), SQLite / JSON IPC (`.aegis/`), and MCP adapters.

### 2.3 Evidence-First & Machine-Verifiable
- Every assertion, relationship, and risk score carries concrete provenance: file path, line numbers, code snippets, and confidence levels (`DIRECT`, `HIGH_CONFIDENCE`, `INFERRED`, `HEURISTIC`).

### 2.4 Token & Compute Economy
- Multi-tier incremental hashing (file hash -> AST hash -> symbol hash) ensures only modified AST nodes trigger re-indexing and downstream graph traversal.

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
├── indexer/
│   ├── base.py             # LanguageIndexer ABC, Symbol, Relationship, Provenance models
│   ├── python_indexer.py   # Python AST indexer (classes, methods, routes, ORM, tests, calls)
│   ├── js_ts_indexer.py    # JS/TS semantic indexer (interfaces, components, routes, fetch, tests)
│   ├── go_indexer.py       # Go semantic indexer (structs, interfaces, methods, routes, tests)
│   ├── registry.py         # Polyglot indexer registry and extension dispatcher
│   └── symbol_index.py     # Incremental symbol index with content/AST hash tracking
├── graph/
│   ├── models.py           # GraphNode, GraphEdge, TraversalPath, GraphStats
│   ├── store.py            # GraphStore ABC & SQLiteGraphStore (.aegis/graph.db)
│   ├── traversal.py        # Cycle-safe, depth-bounded downstream and upstream traversal
│   └── project_graph.py    # High-level ProjectGraph facade and query API
├── impact/
│   ├── models.py           # ImpactReport, ChangedSymbol, AffectedEntity, BlastRadius
│   └── analyzer.py         # ChangeImpactEngine (AST diffs & downstream blast radius)
├── planner/
│   ├── models.py           # RiskAssessment, RiskFactor, TestPlan, PlannedTest, SkippedTest
│   ├── risk.py             # AdaptiveRiskEngine (5-factor deterministic risk model)
│   └── planner.py          # AdaptiveTestPlanner (utility-driven test selection)
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
    └── main.py             # Unified CLI entrypoint supporting graph, impact, risk, plan, test
```

---

## 4. Roadmap Status

- [x] **Phase 1 (Foundation)**: Discovery, Config, CLI, Evidence Schemas, Process Sandboxing, Filesystem Storage, Hashing, Fixtures.
- [x] **Phase 2 (Project Intelligence & Graph)**: AST parsing (Python, TS/JS, Go), SQLite Project Graph, Change Impact Engine, Adaptive Risk Engine, Test Planning Foundation.
- [ ] **Phase 3 (Core Test Runners)**: Native Unit, API Contract/Fuzzing, Sanity probes, Integration, Playwright E2E/UI runners.
- [ ] **Phase 4 (Quality Dimensions)**: Accessibility (axe-core), UX heuristic analysis, Security scanning (SARIF), Performance baseline benchmarking.
- [ ] **Phase 5 (AI Investigation & Routing)**: Multi-provider LLM abstraction (`openai`, `anthropic`, `google`, `local`), context compression, failure root cause synthesis.
- [ ] **Phase 6 (Controlled Self-Healing)**: Bounded patch proposal loops, patch verification, regression validation.
- [ ] **Phase 7 (Release Gate)**: Deterministic policy evaluator (pass/fail release readiness verdict).
- [ ] **Phase 8 (Integrations)**: MCP Server, Antigravity IDE adapter, GitHub Actions CI action, REST API.
