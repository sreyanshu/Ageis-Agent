# Aegis Universal Capability Model

Aegis abstracts software capabilities into a canonical, technology-independent taxonomy so that the risk engine, adaptive planner, and release gate can operate uniformly across any repository.

---

## 1. Capability Taxonomy (`CapabilityType`)

The capability model supports the following domains:

- `LANGUAGE`: Underlying programming languages (Python, TypeScript, JavaScript, Go, etc.)
- `FRAMEWORK`: Application & UI frameworks (FastAPI, React, Express, etc.)
- `BUILD`: Build systems and package managers (npm, poetry, pip, go mod, etc.)
- `TEST_UNIT`: Unit testing suites and frameworks
- `TEST_API`: Contract and REST API testing systems
- `TEST_INTEGRATION`: Cross-component integration tests
- `TEST_E2E`: End-to-end journey tests (Playwright, Cypress, etc.)
- `TEST_UI`: Frontend component and visual regression tests
- `API`: API interfaces (REST, OpenAPI, GraphQL, gRPC)
- `DATABASE`: Relational and document databases (PostgreSQL, MySQL, SQLite, MongoDB)
- `CACHE`: In-memory caching layers (Redis, Memcached)
- `SECURITY`: Static analysis, vulnerability scanners (SARIF, Semgrep)
- `ACCESSIBILITY`: WCAG and A11y heuristic checkers
- `PERFORMANCE`: Benchmark suites and response-time profilers
- `CONTAINER`: Containerization and orchestration (Docker, Docker Compose)
- `CI`: Continuous Integration pipelines (.github/workflows, GitLab CI)

---

## 2. Capability Status Lifecycle (`CapabilityStatus`)

- `DETECTED`: Discovered in the workspace via evidence patterns.
- `SUPPORTED`: Validated as having an active adapter and runner available.
- `CONFIGURED`: Explicitly configured in project manifests or Aegis profiles.
- `AVAILABLE`: Ready for immediate authoritative execution.
- `UNAVAILABLE`: Capability exists in project but missing required tool dependencies.
- `NOT_APPLICABLE`: Excluded or not relevant to the current project context.
- `UNKNOWN`: Insufficient evidence to establish operational readiness.

---

## 3. Structured Provenance (`ProjectCapability`)

Each capability instance stores:
- `name`: Human-readable identifier (e.g., `"FastAPI REST API"`)
- `type`: `CapabilityType` enum
- `status`: `CapabilityStatus` enum
- `confidence`: Floating-point confidence score `[0.0, 1.0]`
- `evidence`: Concrete file paths, dependencies, and configuration references
- `metadata`: Key-value configuration details
