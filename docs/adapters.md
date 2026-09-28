# Aegis Universal Technology Adapters

Aegis uses an open, registry-based adapter architecture that decouples technology-specific integration from core quality engineering and release gating logic.

---

## 1. Adapter Contract

All technology adapters implement the `AegisAdapter` abstract contract:

```python
class AegisAdapter(ABC):
    adapter_id: str
    name: str
    category: str
    version: str

    @abstractmethod
    def detect(self, project_root: Path) -> DetectionResult:
        """Determines if the adapter applies to the given workspace."""
        ...

    @abstractmethod
    def capabilities(self) -> Set[ProjectCapability]:
        """Returns the capabilities provided by this adapter."""
        ...

    @abstractmethod
    def discover(self, project_root: Path) -> DiscoveryResult:
        """Extracts detailed technology-specific metadata."""
        ...

    @abstractmethod
    def validate(self, project_root: Path) -> ValidationResult:
        """Validates configuration sanity and tool availability."""
        ...
```

---

## 2. Adapter Categories

1. **Language Adapters**:
   - `PythonAdapter`: Detects Python manifests (`pyproject.toml`, `requirements.txt`, `Pipfile`), inspects AST.
   - `JavaScriptTypeScriptAdapter`: Detects JS/TS manifests (`package.json`, `tsconfig.json`), npm/pnpm/yarn/bun.
   - `GoAdapter`: Detects Go modules (`go.mod`), packages, and symbol structures.

2. **Testing Adapters**:
   - `PytestTestAdapter`: Discovers pytest suites, markers, and fixtures.
   - `VitestJestAdapter`: Discovers Vitest and Jest specs, configs, and npm scripts.
   - `GoTestAdapter`: Discovers Go unit and integration tests (`*_test.go`).

3. **Framework & Infrastructure Adapters**:
   - `WebFrameworkAdapter`: Detects FastAPI, Flask, Django, Express, NestJS, React, Vue, Svelte, Next.js.
   - `DockerInfrastructureAdapter`: Inspects `Dockerfile`, `docker-compose.yml`, multi-stage builds.
   - `QualityToolAdapter`: Ingests SARIF (Semgrep, Snyk, Bandit, ESLint, CodeQL) reports and WCAG/Lighthouse targets.

---

## 3. Adapter Registry & Lifecycle

Adapters register with the centralized `AdapterRegistry`. During `aegis init` and `aegis discover`, the registry evaluates `detect()` against the project root and activates only matching adapters without conditional hardcoded logic in the core.
