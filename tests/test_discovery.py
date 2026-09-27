from pathlib import Path
import pytest
from aegis.discovery.detector import ProjectDiscoveryEngine
from aegis.storage.filesystem import FilesystemStorage


def test_discover_fastapi_fixture():
    fixture_dir = Path(__file__).parent / "fixtures" / "projects" / "python_fastapi"
    storage = FilesystemStorage(workspace_root=fixture_dir)
    engine = ProjectDiscoveryEngine(workspace_root=fixture_dir, storage=storage)
    profile = engine.discover(project_name="fastapi-test")

    assert profile.project_name == "fastapi-test"
    assert profile.primary_language == "Python"
    
    fw_names = [f.name for f in profile.frameworks]
    assert "FastAPI" in fw_names

    build_names = [b.name for b in profile.build_systems]
    assert "poetry" in build_names

    assert profile.infrastructure.has_docker is True
    assert profile.infrastructure.has_compose is True
    assert "PostgreSQL" in profile.infrastructure.detected_databases
    assert "Redis" in profile.infrastructure.detected_queues

    test_fws = [ts.framework for ts in profile.test_suites]
    assert "pytest" in test_fws

    # Check endpoints
    paths = [e.path for e in profile.interfaces.rest_endpoints]
    assert "/health" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/items" in paths

    # Verify saved machine-readable files
    assert (fixture_dir / ".aegis" / "project-profile.json").exists()
    assert (fixture_dir / ".aegis" / "architecture.json").exists()
    assert (fixture_dir / ".aegis" / "api-map.json").exists()
    assert (fixture_dir / ".aegis" / "test-map.json").exists()


def test_discover_node_react_express_fixture():
    fixture_dir = Path(__file__).parent / "fixtures" / "projects" / "node_react_express"
    storage = FilesystemStorage(workspace_root=fixture_dir)
    engine = ProjectDiscoveryEngine(workspace_root=fixture_dir, storage=storage)
    profile = engine.discover()

    fw_names = [f.name for f in profile.frameworks]
    assert "Express" in fw_names
    assert "React" in fw_names

    assert profile.infrastructure.ci_providers == ["github-actions"]

    test_fws = [ts.framework for ts in profile.test_suites]
    assert "vitest" in test_fws or "jest" in test_fws


def test_discover_go_service_fixture():
    fixture_dir = Path(__file__).parent / "fixtures" / "projects" / "go_service"
    storage = FilesystemStorage(workspace_root=fixture_dir)
    engine = ProjectDiscoveryEngine(workspace_root=fixture_dir, storage=storage)
    profile = engine.discover()

    assert profile.primary_language == "Go"
    fw_names = [f.name for f in profile.frameworks]
    assert "Gin" in fw_names

    test_fws = [ts.framework for ts in profile.test_suites]
    assert "go test" in test_fws
