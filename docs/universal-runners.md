# Aegis Universal Test Runner Architecture

## 1. Overview
Aegis decouples test orchestration from test execution. Aegis owns planning, dependency scheduling, resource isolation, failure classification, and evidence collection, while native language tooling performs test execution via universal runner adapters.

## 2. Universal Runner Protocol
Every runner conforms to the `TestRunner` contract and declares explicit capabilities:
```python
class TestRunner(ABC):
    @property
    def capability(self) -> RunnerCapability: ...

    def supports(self, context: ExecutionContext) -> bool: ...

    def plan(self, context: ExecutionContext) -> RunnerPlan: ...

    def execute(self, plan: RunnerPlan, context: ExecutionContext) -> List[TestResult]: ...
```

## 3. Built-in Runner Adapters

| Runner Adapter | Categories | Supported Stacks | Key Features |
| :--- | :--- | :--- | :--- |
| **`UniversalUnitRunner`** | `unit` | Python (pytest), JS/TS (Vitest, Jest), Go (go test) | Targeted test function filtering, output parsing, dry-run |
| **`SanityPreflightRunner`** | `sanity` | Polyglot (Any) | Project manifest integrity, Python syntax compilation, port probing |
| **`ContractAPIRunner`** | `api` | REST, OpenAPI, FastAPI, Express, Gin | Schema validation, empty payload checks, bounded deterministic fuzzing |
| **`IntegrationRunner`** | `integration` | Multi-service, DB, Caches | Boundary protection (refuses unsafe production execution) |
| **`E2EJourneyRunner`** | `e2e` | Browser, Playwright substrate | Structured user journeys, step logging, DOM snapshots |
| **`UIFunctionalRunner`** | `ui` | React, Vue, Next.js, HTML | Viewport responsiveness, visual baseline diff calculation |
