import os
import pytest
from pathlib import Path
from aegis.core.config import AegisConfig
from aegis.core.exceptions import ConfigurationError


def test_config_defaults(tmp_path: Path):
    cfg = AegisConfig.load(workspace_root=tmp_path)
    assert cfg.project.name == "auto-detected"
    assert cfg.execution.parallel is True
    assert cfg.ai.enabled is False
    assert cfg.release.critical_tests_must_pass is True
    assert cfg.release.require_human_approval is True


def test_config_save_and_reload(tmp_path: Path):
    cfg = AegisConfig.load(workspace_root=tmp_path)
    cfg.project.name = "my-custom-service"
    cfg.ai.enabled = True
    cfg.ai.provider = "openai"
    saved_path = cfg.save(tmp_path / ".aegis" / "config.yaml")
    assert saved_path.exists()

    reloaded = AegisConfig.load(config_path=saved_path, workspace_root=tmp_path)
    assert reloaded.project.name == "my-custom-service"
    assert reloaded.ai.enabled is True
    assert reloaded.ai.provider == "openai"


def test_config_environment_overrides(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AEGIS_EXECUTION_PARALLEL", "false")
    monkeypatch.setenv("AEGIS_EXECUTION_MAX_WORKERS", "8")
    monkeypatch.setenv("AEGIS_AI_ENABLED", "true")

    cfg = AegisConfig.load(workspace_root=tmp_path)
    assert cfg.execution.parallel is False
    assert cfg.execution.max_workers == 8
    assert cfg.ai.enabled is True
