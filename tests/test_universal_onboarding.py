"""
Aegis Universal Project Onboarding & Adapter Architecture Test Suite
Validates:
- Universal Capability Model & Adapter Registry
- Automatic detection on Python/FastAPI, Node/React/Express, and Go Service fixtures
- Universality (same Aegis core adapting to arbitrary stacks)
- Safe reinitialization and history preservation
- CLI commands: init, project, capabilities, adapters, check, release
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from aegis.cli.main import main
from aegis.core.orchestrator import AegisEngine
from aegis.adapters.capabilities import CapabilityType, CapabilityStatus, ProjectCapability
from aegis.adapters.registry import AdapterRegistry, default_adapter_registry
from aegis.evidence.models import TestResult, TestStatus
from aegis.history.models import ExecutionRecord


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "projects"


# ==============================================================================
# 1. ADAPTER REGISTRY & BUILT-IN ADAPTERS
# ==============================================================================

def test_adapter_registry_discovery_and_filtering():
    registry = AdapterRegistry()
    adapters = registry.list_adapters()
    assert len(adapters) >= 9

    adapter_ids = {a.adapter_id for a in adapters}
    assert "lang_python" in adapter_ids
    assert "lang_js_ts" in adapter_ids
    assert "lang_go" in adapter_ids
    assert "test_pytest" in adapter_ids
    assert "test_vitest_jest" in adapter_ids
    assert "test_gotest" in adapter_ids
    assert "fw_web" in adapter_ids
    assert "infra_docker" in adapter_ids
    assert "quality_tools" in adapter_ids

    # Category filtering
    lang_adapters = registry.list_adapters(category="language")
    assert len(lang_adapters) == 3
    test_adapters = registry.list_adapters(category="testing")
    assert len(test_adapters) == 3


# ==============================================================================
# 2. PYTHON FASTAPI FIXTURE ONBOARDING
# ==============================================================================

def test_python_fastapi_onboarding(tmp_path: Path):
    fixture_src = FIXTURES_DIR / "python_fastapi"
    ws = tmp_path / "python_project"
    shutil.copytree(fixture_src, ws)

    engine = AegisEngine(workspace_root=ws)
    engine.init_workspace()

    summary = engine.get_init_summary()
    assert summary["project_name"] == "python_project"
    assert "Python" in summary["languages"]
    assert "FastAPI" in summary["frameworks"]
    assert summary["infrastructure"]["has_docker"] is True
    assert "pytest" in summary["test_systems"]
    assert summary["api_surface"]["rest_endpoints"] > 0
    assert summary["capabilities_count"] > 0

    profile = engine.discover()
    assert profile.schema_version == "2.0.0"
    assert profile.primary_language == "Python"
    cap_types = {c.type for c in profile.capabilities}
    assert CapabilityType.LANGUAGE in cap_types
    assert CapabilityType.TEST_UNIT in cap_types


# ==============================================================================
# 3. NODE REACT EXPRESS FIXTURE ONBOARDING
# ==============================================================================

def test_node_react_express_onboarding(tmp_path: Path):
    fixture_src = FIXTURES_DIR / "node_react_express"
    ws = tmp_path / "node_project"
    shutil.copytree(fixture_src, ws)

    engine = AegisEngine(workspace_root=ws)
    engine.init_workspace()

    summary = engine.get_init_summary()
    assert any("JavaScript" in l or "TypeScript" in l for l in summary["languages"])
    assert any(fw in ("React", "Express") for fw in summary["frameworks"])
    assert any(ts in ("vitest", "jest") for ts in summary["test_systems"])
    assert summary["capabilities_count"] > 0


# ==============================================================================
# 4. GO SERVICE FIXTURE ONBOARDING
# ==============================================================================

def test_go_service_onboarding(tmp_path: Path):
    fixture_src = FIXTURES_DIR / "go_service"
    ws = tmp_path / "go_project"
    shutil.copytree(fixture_src, ws)

    engine = AegisEngine(workspace_root=ws)
    engine.init_workspace()

    summary = engine.get_init_summary()
    assert "Go" in summary["languages"]
    assert "go test" in summary["test_systems"]
    assert summary["infrastructure"]["has_docker"] is True


# ==============================================================================
# 5. UNIVERSALITY: SAME CORE, ARBITRARY STACKS
# ==============================================================================

def test_universality_across_multiple_stacks(tmp_path: Path):
    """
    Proves Aegis operates universally across Python, JS/TS, and Go repositories
    without any stack-specific core modifications.
    """
    stacks = [
        ("python_fastapi", "Python", ("pytest",)),
        ("node_react_express", "JavaScript", ("vitest", "jest")),
        ("go_service", "Go", ("go test",)),
    ]

    for fixture_name, expected_lang, expected_test_runners in stacks:
        ws = tmp_path / f"test_{fixture_name}"
        shutil.copytree(FIXTURES_DIR / fixture_name, ws)

        # Instantiate identical Aegis core
        engine = AegisEngine(workspace_root=ws)
        profile = engine.discover()

        # Check languages and testing capabilities
        langs = [l.name for l in profile.languages]
        assert any(expected_lang in l for l in langs), f"Failed for {fixture_name}"
        test_runners = [ts.framework for ts in profile.test_suites]
        assert any(r in expected_test_runners for r in test_runners), f"Failed runner detection for {fixture_name}"
        assert len(profile.capabilities) > 0


# ==============================================================================
# 6. REINITIALIZATION SAFETY & HISTORY PRESERVATION
# ==============================================================================

def test_reinitialization_preserves_history_and_graph(tmp_path: Path):
    ws = tmp_path / "reinit_project"
    shutil.copytree(FIXTURES_DIR / "python_fastapi", ws)

    engine1 = AegisEngine(workspace_root=ws)
    engine1.init_workspace()

    # Record historical execution
    rec = ExecutionRecord(
        execution_id="exec_persistent_001",
        run_id="run_001",
        project_name="reinit_project",
        commit_or_tree_hash="commit_hash_1",
        test_id="tests/test_api.py::test_health",
        category="api",
        status="PASSED",
        duration_ms=15.0,
        retry_count=0,
        execution_mode="REAL",
    )
    engine1.history_store.record_executions([rec])
    assert len(engine1.history_store.get_executions()) == 1

    # Destroy engine instance and re-run init_workspace
    del engine1

    engine2 = AegisEngine(workspace_root=ws)
    engine2.init_workspace()

    # Verify history was NOT overwritten or wiped
    execs = engine2.history_store.get_executions()
    assert len(execs) == 1
    assert execs[0].execution_id == "exec_persistent_001"


# ==============================================================================
# 7. CLI COMMANDS VALIDATION (INIT, PROJECT, CAPABILITIES, ADAPTERS, CHECK, RELEASE)
# ==============================================================================

def test_cli_onboarding_and_check_commands(tmp_path: Path, capsys):
    ws = tmp_path / "cli_onboarding_project"
    shutil.copytree(FIXTURES_DIR / "python_fastapi", ws)
    ws_str = str(ws)

    # 1. aegis init
    code = main(["--workspace", ws_str, "init"])
    assert code == 0
    out = capsys.readouterr().out
    assert "AEGIS PROJECT INITIALIZATION" in out
    assert "Python" in out

    # 2. aegis project --json
    code = main(["--workspace", ws_str, "--json", "project"])
    assert code == 0
    out = capsys.readouterr().out
    profile_data = json.loads(out)
    assert profile_data["schema_version"] == "2.0.0"
    assert "capabilities" in profile_data

    # 3. aegis capabilities --json
    code = main(["--workspace", ws_str, "--json", "capabilities"])
    assert code == 0
    out = capsys.readouterr().out
    caps_data = json.loads(out)
    assert isinstance(caps_data, list)
    assert len(caps_data) > 0

    # 4. aegis adapters --json
    code = main(["--workspace", ws_str, "--json", "adapters"])
    assert code == 0
    out = capsys.readouterr().out
    adapters_data = json.loads(out)
    assert isinstance(adapters_data, list)
    assert any(a["active"] for a in adapters_data)

    # 5. aegis check --dry-run --json
    code = main(["--workspace", ws_str, "--json", "check", "--dry-run"])
    assert code in (0, 1)
    out = capsys.readouterr().out
    check_data = json.loads(out)
    assert "release_verdict" in check_data
    assert "risk_level" in check_data

    # 6. aegis release --json
    code = main(["--workspace", ws_str, "--json", "release"])
    assert code in (0, 1)
    out = capsys.readouterr().out
    rel_data = json.loads(out)
    assert "verdict" in rel_data
