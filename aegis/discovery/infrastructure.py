"""
Aegis Infrastructure Discovery Engine
Detects containerization, orchestration, IaC, CI/CD workflows, databases, and message brokers.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Set
from pydantic import BaseModel, Field


class InfrastructureInfo(BaseModel):
    has_docker: bool = False
    dockerfiles: List[str] = Field(default_factory=list)
    has_compose: bool = False
    compose_files: List[str] = Field(default_factory=list)
    has_kubernetes: bool = False
    k8s_manifests: List[str] = Field(default_factory=list)
    has_terraform: bool = False
    terraform_files: List[str] = Field(default_factory=list)
    ci_providers: List[str] = Field(default_factory=list)
    detected_databases: List[str] = Field(default_factory=list)
    detected_queues: List[str] = Field(default_factory=list)


class InfrastructureDetector:
    """Detects infrastructure definitions and external service footprints in the project."""

    IGNORED_DIRS: Set[str] = {
        ".git", ".aegis", "node_modules", ".venv", "venv", "__pycache__",
        ".pytest_cache", "target", "build", "dist", ".idea", ".vscode"
    }

    def detect(self, workspace_root: Path | str) -> InfrastructureInfo:
        root = Path(workspace_root).resolve()
        info = InfrastructureInfo()

        dockerfiles: List[str] = []
        compose_files: List[str] = []
        k8s_files: List[str] = []
        tf_files: List[str] = []
        ci_providers: Set[str] = set()
        databases: Set[str] = set()
        queues: Set[str] = set()

        # Check standard CI locations
        if (root / ".github" / "workflows").is_dir():
            ci_providers.add("github-actions")
        if (root / ".gitlab-ci.yml").is_file():
            ci_providers.add("gitlab-ci")
        if (root / ".circleci").is_dir():
            ci_providers.add("circleci")
        if (root / "Jenkinsfile").is_file():
            ci_providers.add("jenkins")
        if (root / "azure-pipelines.yml").is_file():
            ci_providers.add("azure-pipelines")

        # Scan repository for infra configs
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in self.IGNORED_DIRS and not d.startswith(".")]

            for f in filenames:
                full_path = Path(dirpath) / f
                rel_path = str(full_path.relative_to(root))

                # Docker
                if f.lower().startswith("dockerfile") or f.lower().endswith(".dockerfile"):
                    dockerfiles.append(rel_path)
                elif f in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
                    compose_files.append(rel_path)
                    self._extract_services_from_compose(full_path, databases, queues)

                # Kubernetes / Helm
                elif f.endswith((".yaml", ".yml")) and ("k8s" in dirpath.lower() or "helm" in dirpath.lower() or "kubernetes" in dirpath.lower()):
                    k8s_files.append(rel_path)

                # Terraform
                elif f.endswith(".tf") or f.endswith(".tfvars"):
                    tf_files.append(rel_path)

        info.has_docker = len(dockerfiles) > 0
        info.dockerfiles = sorted(dockerfiles)
        info.has_compose = len(compose_files) > 0
        info.compose_files = sorted(compose_files)
        info.has_kubernetes = len(k8s_files) > 0
        info.k8s_manifests = sorted(k8s_files)
        info.has_terraform = len(tf_files) > 0
        info.terraform_files = sorted(tf_files)
        info.ci_providers = sorted(list(ci_providers))
        info.detected_databases = sorted(list(databases))
        info.detected_queues = sorted(list(queues))

        return info

    def _extract_services_from_compose(self, compose_path: Path, databases: Set[str], queues: Set[str]) -> None:
        """Parses docker-compose file for database and message queue services."""
        try:
            content = compose_path.read_text(encoding="utf-8", errors="ignore").lower()
            if "postgres" in content:
                databases.add("PostgreSQL")
            if "mysql" in content or "mariadb" in content:
                databases.add("MySQL")
            if "mongo" in content:
                databases.add("MongoDB")
            if "redis" in content:
                databases.add("Redis")
                queues.add("Redis")
            if "sqlite" in content:
                databases.add("SQLite")
            if "kafka" in content:
                queues.add("Kafka")
            if "rabbitmq" in content or "amqp" in content:
                queues.add("RabbitMQ")
            if "nats" in content:
                queues.add("NATS")
        except Exception:
            pass
