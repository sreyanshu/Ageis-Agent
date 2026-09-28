# Aegis Universal Project Onboarding

Universal project onboarding is the entry-point mechanism through which Aegis inspects an arbitrary software repository, detects its underlying architecture, resolves capabilities, maps registered technology adapters, builds the project intelligence graph, and initializes historical tracking.

---

## 1. Onboarding Pipeline

Running `aegis init` executes a deterministic, multi-stage pipeline:

```text
Repository Inspection
        ↓
Language & Framework Detection
        ↓
Build & Infrastructure Detection
        ↓
Test Framework & Existing Test Discovery
        ↓
Adapter Detection & Capability Resolution
        ↓
Canonical Project Profile (.aegis/project-profile.json v2.0.0)
        ↓
AST Symbol Indexing & Project Intelligence Graph
        ↓
Historical Store Initialized (.aegis/history/history.db)
```

No manual configuration file is required. Aegis dynamically adapts to the repository rather than forcing the project into an Aegis-specific layout.

---

## 2. Evidence-Based Detection

Aegis never assumes technology presence from file name alone without evidence. Every detected element produces structured evidence and confidence ratings (`DIRECT`, `HIGH_CONFIDENCE`, `INFERRED`, `HEURISTIC`):

- **Languages**: Manifest dependencies, lockfiles, file extensions, language statistics.
- **Frameworks**: Source import patterns, framework configs (e.g. `vite.config.ts`, `next.config.js`).
- **Build Systems**: Manifest files (`pyproject.toml`, `package.json`, `go.mod`, `pom.xml`, `Cargo.toml`).
- **Testing Systems**: Test runner configs (`pytest.ini`, `vitest.config.ts`, `jest.config.js`, `playwright.config.ts`), test file naming patterns.
- **Infrastructure & Quality**: `Dockerfile`, `docker-compose.yml`, `.github/workflows/`, SARIF scan outputs, accessibility targets.

---

## 3. Idempotent & Non-Destructive Reinitialization

Running `aegis init` multiple times on the same repository is completely safe:
- Existing `.aegis/history/history.db` database is preserved and never deleted or corrupted.
- Compatible project graphs and cached AST index hashes are updated incrementally.
- The canonical project profile (`.aegis/project-profile.json`) is refreshed with updated active adapters and capabilities.

---

## 4. Multi-Stack & Monorepo Readiness

A single repository may contain multiple technology stacks (e.g., Python backend + React frontend + Go service + Docker + PostgreSQL). Aegis represents this unified environment in a single project profile with multiple resolved capabilities and component boundaries.
