"""
Aegis Project Discovery Coordinator
Aggregates language, framework, build system, infrastructure, interface, and test detectors
to construct the comprehensive Project Profile and machine-readable artifacts in .aegis/.
"""

from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from aegis.core.exceptions import DiscoveryError
from aegis.discovery.languages import LanguageDetector, LanguageInfo
from aegis.discovery.frameworks import FrameworkDetector, FrameworkInfo
from aegis.discovery.build_systems import BuildSystemDetector, BuildSystemInfo
from aegis.discovery.infrastructure import InfrastructureDetector, InfrastructureInfo
from aegis.discovery.interfaces import InterfaceDetector, InterfaceMap
from aegis.discovery.tests import TestDetector, TestSuiteInfo
from aegis.storage.base import StorageBackend
from aegis.storage.hashing import ContentHasher


class ProjectProfile(BaseModel):
    """Unified machine-verifiable description of the target workspace."""
    schema_version: str = "1.0.0"
    project_name: str
    root_path: str
    discovered_at: float = Field(default_factory=time.time)
    tree_hash: str
    languages: List[LanguageInfo] = Field(default_factory=list)
    frameworks: List[FrameworkInfo] = Field(default_factory=list)
    build_systems: List[BuildSystemInfo] = Field(default_factory=list)
    infrastructure: InfrastructureInfo = Field(default_factory=InfrastructureInfo)
    interfaces: InterfaceMap = Field(default_factory=InterfaceMap)
    test_suites: List[TestSuiteInfo] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def primary_language(self) -> Optional[str]:
        for lang in self.languages:
            if lang.primary:
                return lang.name
        return self.languages[0].name if self.languages else None


class ProjectDiscoveryEngine:
    """Coordinates full repository inspection and produces machine-readable profile maps."""

    def __init__(
        self,
        workspace_root: Path | str,
        storage: Optional[StorageBackend] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.storage = storage
        self.lang_detector = LanguageDetector()
        self.fw_detector = FrameworkDetector()
        self.build_detector = BuildSystemDetector()
        self.infra_detector = InfrastructureDetector()
        self.iface_detector = InterfaceDetector()
        self.test_detector = TestDetector()

    def discover(self, project_name: Optional[str] = None) -> ProjectProfile:
        """Executes full discovery across all facets and returns the ProjectProfile."""
        if not self.workspace_root.is_dir():
            raise DiscoveryError(f"Workspace path does not exist or is not a directory: {self.workspace_root}")

        name = project_name or self.workspace_root.name
        tree_hash, _ = ContentHasher.hash_directory_tree(self.workspace_root)

        languages = self.lang_detector.detect(self.workspace_root)
        frameworks = self.fw_detector.detect(self.workspace_root)
        build_systems = self.build_detector.detect(self.workspace_root)
        infrastructure = self.infra_detector.detect(self.workspace_root)
        interfaces = self.iface_detector.detect(self.workspace_root)
        test_suites = self.test_detector.detect(self.workspace_root)

        profile = ProjectProfile(
            project_name=name,
            root_path=str(self.workspace_root),
            tree_hash=tree_hash,
            languages=languages,
            frameworks=frameworks,
            build_systems=build_systems,
            infrastructure=infrastructure,
            interfaces=interfaces,
            test_suites=test_suites,
            metadata={
                "total_languages": len(languages),
                "total_frameworks": len(frameworks),
                "total_test_suites": len(test_suites),
            }
        )

        if self.storage:
            self._persist_profile_artifacts(profile)

        return profile

    def _persist_profile_artifacts(self, profile: ProjectProfile) -> None:
        """Saves all required machine-readable JSON files in .aegis/."""
        if not self.storage:
            return

        # 1. project-profile.json
        self.storage.save_json("project-profile.json", profile.model_dump())

        # 2. architecture.json
        architecture_data = {
            "project_name": profile.project_name,
            "primary_language": profile.primary_language,
            "languages": [l.model_dump() for l in profile.languages],
            "frameworks": [f.model_dump() for f in profile.frameworks],
            "infrastructure": profile.infrastructure.model_dump(),
        }
        self.storage.save_json("architecture.json", architecture_data)

        # 3. dependency-map.json
        dependency_data = {
            "build_systems": [b.model_dump() for b in profile.build_systems],
            "databases": profile.infrastructure.detected_databases,
            "queues": profile.infrastructure.detected_queues,
        }
        self.storage.save_json("dependency-map.json", dependency_data)

        # 4. api-map.json
        api_data = {
            "has_openapi": profile.interfaces.has_openapi,
            "openapi_specs": profile.interfaces.openapi_specs,
            "has_graphql": profile.interfaces.has_graphql,
            "graphql_schemas": profile.interfaces.graphql_schemas,
            "has_grpc": profile.interfaces.has_grpc,
            "proto_files": profile.interfaces.proto_files,
            "endpoints": [e.model_dump() for e in profile.interfaces.rest_endpoints],
        }
        self.storage.save_json("api-map.json", api_data)

        # 5. ui-map.json
        ui_data = {
            "has_frontend": any(f.category in ("frontend", "fullstack") for f in profile.frameworks),
            "ui_frameworks": [f.name for f in profile.frameworks if f.category in ("frontend", "fullstack")],
        }
        self.storage.save_json("ui-map.json", ui_data)

        # 6. test-map.json
        test_data = {
            "test_suites": [ts.model_dump() for ts in profile.test_suites],
            "total_estimated_tests": sum(ts.test_count_estimate for ts in profile.test_suites),
        }
        self.storage.save_json("test-map.json", test_data)

        # 7. risk-model.json (initial baseline risk parameters)
        risk_data = {
            "baseline_risk": "LOW" if profile.test_suites else "MEDIUM",
            "has_tests": len(profile.test_suites) > 0,
            "test_count": sum(ts.test_count_estimate for ts in profile.test_suites),
            "database_sensitivity": "HIGH" if profile.infrastructure.detected_databases else "LOW",
        }
        self.storage.save_json("risk-model.json", risk_data)

        # 8. environment.json
        env_data = {
            "root_path": profile.root_path,
            "tree_hash": profile.tree_hash,
            "discovered_at": profile.discovered_at,
            "ci_providers": profile.infrastructure.ci_providers,
        }
        self.storage.save_json("environment.json", env_data)
