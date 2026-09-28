"""
Aegis Language Adapters (Python, JavaScript/TypeScript, Go)
Provides deterministic detection, capabilities, and discovery for primary languages.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import List, Set

from aegis.adapters.base import AegisAdapter, DetectionResult, DiscoveryResult, ValidationResult
from aegis.adapters.capabilities import ProjectCapability, CapabilityType, CapabilityStatus


class PythonAdapter(AegisAdapter):
    """Adapter for Python language and ecosystem."""

    def __init__(self) -> None:
        super().__init__(
            adapter_id="lang_python",
            name="Python Language Adapter",
            category="language",
            version="1.0.0",
        )

    def detect(self, workspace_root: Path) -> DetectionResult:
        evidence = []
        py_files = 0
        for dirpath, dirnames, filenames in os.walk(workspace_root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("node_modules", ".venv", "venv", "__pycache__", "build", "dist")]
            for f in filenames:
                if f.endswith(".py"):
                    py_files += 1
                if f in ("pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock", "setup.py", "setup.cfg"):
                    evidence.append(f"Found Python manifest: {f}")

        if py_files > 0:
            evidence.append(f"Discovered {py_files} Python source files")

        detected = py_files > 0 or len(evidence) > 0
        confidence = 1.0 if len(evidence) >= 2 else (0.8 if detected else 0.0)
        return DetectionResult(
            detected=detected,
            confidence=confidence,
            evidence=evidence,
            metadata={"python_file_count": py_files},
        )

    def capabilities(self, workspace_root: Path) -> List[ProjectCapability]:
        det = self.detect(workspace_root)
        if not det.detected:
            return []
        caps = [
            ProjectCapability(
                id="cap_lang_python",
                type=CapabilityType.LANGUAGE,
                name="Python",
                status=CapabilityStatus.SUPPORTED,
                confidence=det.confidence,
                evidence=det.evidence,
                source="PythonAdapter",
            )
        ]
        # Check build system capabilities
        if (workspace_root / "pyproject.toml").is_file():
            caps.append(ProjectCapability(
                id="cap_build_pyproject",
                type=CapabilityType.BUILD,
                name="pyproject.toml",
                status=CapabilityStatus.AVAILABLE,
                evidence=["pyproject.toml build configuration"],
                source="PythonAdapter",
            ))
        elif (workspace_root / "requirements.txt").is_file():
            caps.append(ProjectCapability(
                id="cap_build_pip_requirements",
                type=CapabilityType.BUILD,
                name="pip requirements",
                status=CapabilityStatus.AVAILABLE,
                evidence=["requirements.txt dependency manifest"],
                source="PythonAdapter",
            ))
        return caps

    def discover(self, workspace_root: Path) -> DiscoveryResult:
        caps = self.capabilities(workspace_root)
        configs = []
        for name in ("pyproject.toml", "requirements.txt", "Pipfile", "setup.py", "pytest.ini"):
            if (workspace_root / name).is_file():
                configs.append(name)
        return DiscoveryResult(capabilities=caps, configuration_files=configs)


class JavaScriptTypeScriptAdapter(AegisAdapter):
    """Adapter for JavaScript and TypeScript ecosystem."""

    def __init__(self) -> None:
        super().__init__(
            adapter_id="lang_js_ts",
            name="JavaScript / TypeScript Language Adapter",
            category="language",
            version="1.0.0",
        )

    def detect(self, workspace_root: Path) -> DetectionResult:
        evidence = []
        js_files = 0
        ts_files = 0

        for dirpath, dirnames, filenames in os.walk(workspace_root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("node_modules", "dist", "build", ".next", ".nuxt")]
            for f in filenames:
                if f.endswith((".js", ".jsx", ".mjs", ".cjs")):
                    js_files += 1
                elif f.endswith((".ts", ".tsx")):
                    ts_files += 1
                if f in ("package.json", "tsconfig.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
                    evidence.append(f"Found Node manifest/config: {f}")

        if ts_files > 0:
            evidence.append(f"Discovered {ts_files} TypeScript source files")
        if js_files > 0:
            evidence.append(f"Discovered {js_files} JavaScript source files")

        detected = (js_files + ts_files > 0) or len(evidence) > 0
        confidence = 1.0 if (workspace_root / "package.json").is_file() else (0.8 if detected else 0.0)
        return DetectionResult(
            detected=detected,
            confidence=confidence,
            evidence=evidence,
            metadata={"js_files": js_files, "ts_files": ts_files},
        )

    def capabilities(self, workspace_root: Path) -> List[ProjectCapability]:
        det = self.detect(workspace_root)
        if not det.detected:
            return []
        caps = []
        if det.metadata.get("ts_files", 0) > 0 or (workspace_root / "tsconfig.json").is_file():
            caps.append(ProjectCapability(
                id="cap_lang_typescript",
                type=CapabilityType.LANGUAGE,
                name="TypeScript",
                status=CapabilityStatus.SUPPORTED,
                confidence=det.confidence,
                evidence=det.evidence,
                source="JavaScriptTypeScriptAdapter",
            ))
        caps.append(ProjectCapability(
            id="cap_lang_javascript",
            type=CapabilityType.LANGUAGE,
            name="JavaScript",
            status=CapabilityStatus.SUPPORTED,
            confidence=det.confidence,
            evidence=det.evidence,
            source="JavaScriptTypeScriptAdapter",
        ))
        if (workspace_root / "package.json").is_file():
            pkg_mgr = "npm"
            if (workspace_root / "pnpm-lock.yaml").is_file():
                pkg_mgr = "pnpm"
            elif (workspace_root / "yarn.lock").is_file():
                pkg_mgr = "yarn"
            caps.append(ProjectCapability(
                id=f"cap_build_{pkg_mgr}",
                type=CapabilityType.BUILD,
                name=f"Node.js ({pkg_mgr})",
                status=CapabilityStatus.AVAILABLE,
                evidence=[f"package.json and {pkg_mgr} lockfile"],
                source="JavaScriptTypeScriptAdapter",
            ))
        return caps

    def discover(self, workspace_root: Path) -> DiscoveryResult:
        caps = self.capabilities(workspace_root)
        configs = []
        for name in ("package.json", "tsconfig.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
            if (workspace_root / name).is_file():
                configs.append(name)
        return DiscoveryResult(capabilities=caps, configuration_files=configs)


class GoAdapter(AegisAdapter):
    """Adapter for Go language ecosystem."""

    def __init__(self) -> None:
        super().__init__(
            adapter_id="lang_go",
            name="Go Language Adapter",
            category="language",
            version="1.0.0",
        )

    def detect(self, workspace_root: Path) -> DetectionResult:
        evidence = []
        go_files = 0
        for dirpath, dirnames, filenames in os.walk(workspace_root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("vendor", "bin", "pkg")]
            for f in filenames:
                if f.endswith(".go"):
                    go_files += 1
                if f in ("go.mod", "go.sum", "Gopkg.toml"):
                    evidence.append(f"Found Go module manifest: {f}")

        if go_files > 0:
            evidence.append(f"Discovered {go_files} Go source files")

        detected = go_files > 0 or len(evidence) > 0
        confidence = 1.0 if (workspace_root / "go.mod").is_file() else (0.8 if detected else 0.0)
        return DetectionResult(
            detected=detected,
            confidence=confidence,
            evidence=evidence,
            metadata={"go_files": go_files},
        )

    def capabilities(self, workspace_root: Path) -> List[ProjectCapability]:
        det = self.detect(workspace_root)
        if not det.detected:
            return []
        caps = [
            ProjectCapability(
                id="cap_lang_go",
                type=CapabilityType.LANGUAGE,
                name="Go",
                status=CapabilityStatus.SUPPORTED,
                confidence=det.confidence,
                evidence=det.evidence,
                source="GoAdapter",
            )
        ]
        if (workspace_root / "go.mod").is_file():
            caps.append(ProjectCapability(
                id="cap_build_go_modules",
                type=CapabilityType.BUILD,
                name="Go Modules",
                status=CapabilityStatus.AVAILABLE,
                evidence=["go.mod module manifest"],
                source="GoAdapter",
            ))
        return caps

    def discover(self, workspace_root: Path) -> DiscoveryResult:
        caps = self.capabilities(workspace_root)
        configs = []
        for name in ("go.mod", "go.sum"):
            if (workspace_root / name).is_file():
                configs.append(name)
        return DiscoveryResult(capabilities=caps, configuration_files=configs)
