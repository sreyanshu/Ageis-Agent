"""
Aegis Framework, Infrastructure & Quality Adapters
Covers FastAPI, React, Express, Docker, PostgreSQL/Redis, and CI/SARIF scanners.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import List, Dict, Any

from aegis.adapters.base import AegisAdapter, DetectionResult, DiscoveryResult, ValidationResult
from aegis.adapters.capabilities import ProjectCapability, CapabilityType, CapabilityStatus
from aegis.discovery.frameworks import FrameworkDetector
from aegis.discovery.infrastructure import InfrastructureDetector


class WebFrameworkAdapter(AegisAdapter):
    """Adapter for Web Application Frameworks (FastAPI, Flask, Django, Express, React)."""

    def __init__(self) -> None:
        super().__init__(
            adapter_id="fw_web",
            name="Web Framework Adapter",
            category="framework",
            version="1.0.0",
        )
        self.detector = FrameworkDetector()

    def detect(self, workspace_root: Path) -> DetectionResult:
        fws = self.detector.detect(workspace_root)
        evidence = [f"Detected framework: {f.name} (v{f.version or 'unknown'}) in {f.category}" for f in fws]
        return DetectionResult(
            detected=len(fws) > 0,
            confidence=1.0 if fws else 0.0,
            evidence=evidence,
            metadata={"frameworks": [f.name for f in fws]},
        )

    def capabilities(self, workspace_root: Path) -> List[ProjectCapability]:
        fws = self.detector.detect(workspace_root)
        caps = []
        for f in fws:
            cap_type = CapabilityType.FRAMEWORK
            if f.category == "frontend":
                cap_type = CapabilityType.TEST_UI
            caps.append(
                ProjectCapability(
                    id=f"cap_fw_{f.name.lower()}",
                    type=cap_type,
                    name=f.name,
                    status=CapabilityStatus.SUPPORTED,
                    confidence=0.95,
                    evidence=[f"Detected {f.name} via import/package manifest"],
                    source="WebFrameworkAdapter",
                )
            )
        return caps

    def discover(self, workspace_root: Path) -> DiscoveryResult:
        caps = self.capabilities(workspace_root)
        return DiscoveryResult(capabilities=caps)


class DockerInfrastructureAdapter(AegisAdapter):
    """Adapter for Container & Infrastructure (Docker, Docker Compose, Databases)."""

    def __init__(self) -> None:
        super().__init__(
            adapter_id="infra_docker",
            name="Docker Infrastructure Adapter",
            category="infrastructure",
            version="1.0.0",
        )
        self.detector = InfrastructureDetector()

    def detect(self, workspace_root: Path) -> DetectionResult:
        infra = self.detector.detect(workspace_root)
        evidence = []
        if infra.has_docker:
            evidence.append(f"Found Dockerfile ({len(infra.dockerfiles)} files)")
        if infra.has_compose:
            evidence.append(f"Found Compose configuration ({len(infra.compose_files)} files)")
        for db in infra.detected_databases:
            evidence.append(f"Discovered database infrastructure: {db}")
        for q in infra.detected_queues:
            evidence.append(f"Discovered queue/cache infrastructure: {q}")

        detected = infra.has_docker or infra.has_compose or len(infra.detected_databases) > 0
        return DetectionResult(
            detected=detected,
            confidence=1.0 if detected else 0.0,
            evidence=evidence,
        )

    def capabilities(self, workspace_root: Path) -> List[ProjectCapability]:
        infra = self.detector.detect(workspace_root)
        caps = []
        if infra.has_docker:
            caps.append(ProjectCapability(
                id="cap_infra_docker",
                type=CapabilityType.CONTAINER,
                name="Docker",
                status=CapabilityStatus.AVAILABLE,
                evidence=["Dockerfile present in workspace"],
                source="DockerInfrastructureAdapter",
            ))
        if infra.has_compose:
            caps.append(ProjectCapability(
                id="cap_infra_compose",
                type=CapabilityType.CONTAINER,
                name="Docker Compose",
                status=CapabilityStatus.AVAILABLE,
                evidence=infra.compose_files,
                source="DockerInfrastructureAdapter",
            ))
        for db in infra.detected_databases:
            caps.append(ProjectCapability(
                id=f"cap_db_{db.lower()}",
                type=CapabilityType.DATABASE,
                name=db,
                status=CapabilityStatus.SUPPORTED,
                evidence=[f"{db} referenced in infrastructure config"],
                source="DockerInfrastructureAdapter",
            ))
        for q in infra.detected_queues:
            caps.append(ProjectCapability(
                id=f"cap_cache_{q.lower()}",
                type=CapabilityType.CACHE,
                name=q,
                status=CapabilityStatus.SUPPORTED,
                evidence=[f"{q} referenced in configuration"],
                source="DockerInfrastructureAdapter",
            ))
        return caps

    def discover(self, workspace_root: Path) -> DiscoveryResult:
        caps = self.capabilities(workspace_root)
        infra = self.detector.detect(workspace_root)
        configs = list(infra.dockerfiles) + list(infra.compose_files)
        return DiscoveryResult(capabilities=caps, configuration_files=configs)


class QualityToolAdapter(AegisAdapter):
    """Adapter for Security (SARIF, Semgrep), Accessibility, Performance, and CI tools."""

    def __init__(self) -> None:
        super().__init__(
            adapter_id="quality_tools",
            name="Quality Dimensions & Scanners Adapter",
            category="quality",
            version="1.0.0",
        )

    def detect(self, workspace_root: Path) -> DetectionResult:
        evidence = []
        # Check for SARIF reports or security configs
        for dirpath, dirnames, filenames in os.walk(workspace_root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("node_modules", ".venv", "build", "dist")]
            for f in filenames:
                if f.endswith(".sarif") or f.endswith(".sarif.json"):
                    evidence.append(f"Found SARIF security report: {f}")
                elif f in (".semgrep.yml", ".semgrepignore", "security-audit.json"):
                    evidence.append(f"Found security scanner config: {f}")
                elif f in ("axe.config.js", ".pa11yci", "lighthouserc.json"):
                    evidence.append(f"Found quality scan config: {f}")

        # Check CI workflows
        gh_workflows = workspace_root / ".github" / "workflows"
        if gh_workflows.is_dir():
            evidence.append(f"Found GitHub Actions CI workflows ({len(list(gh_workflows.glob('*.yml')))} workflows)")
        if (workspace_root / ".gitlab-ci.yml").is_file():
            evidence.append("Found GitLab CI configuration")

        return DetectionResult(
            detected=len(evidence) > 0,
            confidence=1.0 if evidence else 0.5,
            evidence=evidence,
        )

    def capabilities(self, workspace_root: Path) -> List[ProjectCapability]:
        det = self.detect(workspace_root)
        caps = [
            ProjectCapability(
                id="cap_quality_security_sarif",
                type=CapabilityType.SECURITY,
                name="SARIF / Static Security Analysis",
                status=CapabilityStatus.AVAILABLE,
                confidence=0.9,
                evidence=det.evidence,
                source="QualityToolAdapter",
            ),
            ProjectCapability(
                id="cap_quality_a11y_wcag",
                type=CapabilityType.ACCESSIBILITY,
                name="WCAG Accessibility Audits",
                status=CapabilityStatus.AVAILABLE,
                confidence=0.9,
                evidence=["Aegis native WCAG automated evaluator"],
                source="QualityToolAdapter",
            ),
            ProjectCapability(
                id="cap_quality_perf_budgets",
                type=CapabilityType.PERFORMANCE,
                name="Performance Baseline & Budgets",
                status=CapabilityStatus.AVAILABLE,
                confidence=0.9,
                evidence=["Aegis statistical performance engine"],
                source="QualityToolAdapter",
            ),
        ]
        gh_workflows = workspace_root / ".github" / "workflows"
        if gh_workflows.is_dir():
            caps.append(ProjectCapability(
                id="cap_ci_github_actions",
                type=CapabilityType.CI,
                name="GitHub Actions",
                status=CapabilityStatus.AVAILABLE,
                evidence=["GitHub Actions workflows detected"],
                source="QualityToolAdapter",
            ))
        return caps

    def discover(self, workspace_root: Path) -> DiscoveryResult:
        caps = self.capabilities(workspace_root)
        return DiscoveryResult(capabilities=caps)
