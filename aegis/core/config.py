"""
Aegis Configuration Management Engine
Provides strongly-typed schemas, YAML parsing, environment overrides, and default configurations.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field
import yaml

from aegis.core.exceptions import ConfigurationError


class ProjectConfig(BaseModel):
    name: str = Field(default="auto-detected", description="Name of the analyzed project")
    root_path: str = Field(default=".", description="Root path of the project workspace")
    environment: str = Field(default="development", description="Target environment: development, staging, production, ci")


class ExecutionConfig(BaseModel):
    parallel: bool = Field(default=True, description="Enable parallel test execution when safe")
    max_workers: int = Field(default=4, description="Maximum concurrent worker processes")
    timeout_seconds: int = Field(default=300, description="Global process timeout per operation")
    dry_run: bool = Field(default=False, description="Preview actions without modifying state or executing mutations")
    safe_mode: bool = Field(default=True, description="Enforce sandboxing and forbid unverified filesystem mutations")


class TestingConfig(BaseModel):
    unit: str = Field(default="auto", description="Execution mode: auto, always, disabled, adaptive")
    api: str = Field(default="auto", description="Execution mode: auto, always, disabled, adaptive")
    sanity: str = Field(default="auto", description="Execution mode: auto, always, disabled, adaptive")
    integration: str = Field(default="auto", description="Execution mode: auto, always, disabled, adaptive")
    e2e: str = Field(default="auto", description="Execution mode: auto, always, disabled, adaptive")
    ui: str = Field(default="auto", description="Execution mode: auto, always, disabled, adaptive")
    ux: str = Field(default="auto", description="Execution mode: auto, always, disabled, adaptive")
    accessibility: str = Field(default="auto", description="Execution mode: auto, always, disabled, adaptive")
    security: str = Field(default="auto", description="Execution mode: auto, always, disabled, adaptive")
    performance: str = Field(default="auto", description="Execution mode: auto, always, disabled, adaptive")
    compatibility: str = Field(default="adaptive", description="Execution mode: auto, always, disabled, adaptive")


class AIConfig(BaseModel):
    enabled: bool = Field(default=False, description="Enable AI assistance layers (deterministic core operates without AI)")
    provider: str = Field(default="none", description="AI Provider: none, openai, anthropic, google, xai, local")
    model: str = Field(default="", description="Model name/identifier for the provider")
    max_tokens: int = Field(default=4096, description="Token budget cap per reasoning call")
    budget_usd: float = Field(default=1.00, description="Total budget dollar limit")
    escalation: bool = Field(default=True, description="Permit escalation to stronger models for complex root causes")


class AgentConfig(BaseModel):
    autonomous: bool = Field(default=False, description="Allow autonomous self-healing loop execution")
    max_iterations: int = Field(default=3, description="Maximum bounded autonomous loop cycles")
    max_patch_attempts: int = Field(default=2, description="Maximum patch trial attempts before giving up")
    max_runtime_minutes: int = Field(default=10, description="Maximum autonomous agent runtime")


class ReleasePolicyConfig(BaseModel):
    critical_tests_must_pass: bool = Field(default=True, description="Strict requirement: zero critical test failures")
    critical_security_findings: int = Field(default=0, description="Max allowed critical security vulnerabilities")
    accessibility_threshold: float = Field(default=0.95, description="Minimum acceptable A11y compliance score (0.0 to 1.0)")
    performance_regression_percent: float = Field(default=10.0, description="Maximum acceptable latency/throughput regression %")
    production_build_required: bool = Field(default=True, description="Require a verified successful production build")
    require_human_approval: bool = Field(default=True, description="Never auto-promote to production without human confirmation")


class StorageConfig(BaseModel):
    dir_name: str = Field(default=".aegis", description="Directory where Aegis metadata and evidence are persisted")
    artifact_retention_days: int = Field(default=30, description="Retention limit for raw evidence artifacts")


class AegisConfig(BaseModel):
    """Root configuration object for Aegis."""
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    testing: TestingConfig = Field(default_factory=TestingConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    release: ReleasePolicyConfig = Field(default_factory=ReleasePolicyConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @classmethod
    def load(cls, config_path: Optional[Path | str] = None, workspace_root: Optional[Path | str] = None) -> AegisConfig:
        """
        Loads configuration from the specified path or standard location (.aegis/config.yaml),
        merging with defaults and applying environment variable overrides.
        """
        root = Path(workspace_root) if workspace_root else Path.cwd()
        target_file = Path(config_path) if config_path else root / ".aegis" / "config.yaml"

        raw_data: Dict[str, Any] = {}
        if target_file.exists():
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        raw_data = loaded
            except Exception as e:
                raise ConfigurationError(f"Failed to parse configuration file at {target_file}: {e}") from e

        # Ensure project root path defaults to workspace
        if "project" not in raw_data:
            raw_data["project"] = {}
        if "root_path" not in raw_data["project"]:
            raw_data["project"]["root_path"] = str(root.resolve())

        # Environment variable overrides (e.g. AEGIS_EXECUTION_DRY_RUN=1, AEGIS_AI_ENABLED=true)
        cls._apply_env_overrides(raw_data)

        try:
            return cls(**raw_data)
        except Exception as e:
            raise ConfigurationError(f"Configuration validation failed: {e}") from e

    @classmethod
    def _apply_env_overrides(cls, data: Dict[str, Any]) -> None:
        prefix = "AEGIS_"
        for key, val in os.environ.items():
            if key.startswith(prefix):
                key_body = key[len(prefix):].lower()
                if "_" in key_body:
                    section, field = key_body.split("_", 1)
                    if section not in data:
                        data[section] = {}
                    # Convert boolean/int if possible
                    if val.lower() in ("true", "1", "yes"):
                        data[section][field] = True
                    elif val.lower() in ("false", "0", "no"):
                        data[section][field] = False
                    elif val.isdigit():
                        data[section][field] = int(val)
                    else:
                        data[section][field] = val

    def dump_yaml(self) -> str:
        """Serializes current configuration to YAML string."""
        return yaml.dump(self.model_dump(), sort_keys=False, default_flow_style=False)

    def save(self, destination: Optional[Path | str] = None) -> Path:
        """Saves configuration to .aegis/config.yaml or specified destination."""
        dest = Path(destination) if destination else Path(self.project.root_path) / ".aegis" / "config.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(self.dump_yaml())
        return dest
