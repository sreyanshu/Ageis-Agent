# Aegis Canonical Project Profile

The canonical project profile represents the serialized, authoritative snapshot of a repository's discovered architecture, active adapters, resolved capabilities, and component breakdown.

---

## 1. Schema & Location

The profile is persisted deterministically at:
```text
.aegis/project-profile.json
```
Current Schema Version: `2.0.0`

---

## 2. Profile Structure

```json
{
  "schema_version": "2.0.0",
  "project_name": "example-service",
  "root_path": "/workspace/example-service",
  "created_at": "2026-09-27T22:00:00+00:00",
  "updated_at": "2026-09-27T22:00:00+00:00",
  "tree_hash": "a1b2c3d4...",
  "primary_language": "Python",
  "languages": [
    {
      "name": "Python",
      "file_count": 42,
      "percentage": 85.0,
      "primary": true,
      "version_hint": "3.11"
    }
  ],
  "frameworks": [
    {
      "name": "FastAPI",
      "category": "backend",
      "version": "0.110.0"
    }
  ],
  "build_systems": [
    {
      "name": "poetry",
      "manifest_file": "pyproject.toml",
      "lock_file": "poetry.lock"
    }
  ],
  "infrastructure": {
    "has_docker": true,
    "has_compose": true,
    "has_kubernetes": false,
    "ci_providers": ["GitHub Actions"]
  },
  "interfaces": {
    "rest_endpoints": ["/api/v1/health", "/api/v1/items"],
    "has_openapi": true,
    "has_graphql": false,
    "has_grpc": false
  },
  "test_suites": [
    {
      "framework": "pytest",
      "test_files": ["tests/test_api.py"],
      "test_count_estimate": 12
    }
  ],
  "capabilities": [
    {
      "name": "Python Language Core",
      "type": "language",
      "status": "DETECTED",
      "confidence": 1.0,
      "evidence": ["pyproject.toml detected"],
      "metadata": {}
    }
  ],
  "active_adapters": ["lang_python", "test_pytest", "fw_web", "infra_docker"],
  "components": [],
  "confidence_scores": {
    "languages": 1.0,
    "frameworks": 0.95,
    "tests": 1.0
  }
}
```
