"""
Aegis Interface & Contract Discovery Engine
Discovers REST routes, OpenAPI/Swagger specifications, GraphQL schemas, gRPC protobufs, CLI tools, and database models.
"""

from __future__ import annotations
import os
import re
import json
from pathlib import Path
from typing import List, Set, Optional
from pydantic import BaseModel, Field


class EndpointInfo(BaseModel):
    method: str
    path: str
    source_file: str
    line_number: Optional[int] = None
    handler_name: Optional[str] = None


class InterfaceMap(BaseModel):
    has_openapi: bool = False
    openapi_specs: List[str] = Field(default_factory=list)
    has_graphql: bool = False
    graphql_schemas: List[str] = Field(default_factory=list)
    has_grpc: bool = False
    proto_files: List[str] = Field(default_factory=list)
    has_cli: bool = False
    rest_endpoints: List[EndpointInfo] = Field(default_factory=list)
    database_models: List[str] = Field(default_factory=list)


class InterfaceDetector:
    """Discovers exposed contracts and communication interfaces."""

    IGNORED_DIRS: Set[str] = {
        ".git", ".aegis", "node_modules", ".venv", "venv", "__pycache__",
        ".pytest_cache", "target", "build", "dist", ".idea", ".vscode"
    }

    def detect(self, workspace_root: Path | str) -> InterfaceMap:
        root = Path(workspace_root).resolve()
        imap = InterfaceMap()

        openapi_specs: List[str] = []
        graphql_schemas: List[str] = []
        proto_files: List[str] = []
        endpoints: List[EndpointInfo] = []
        db_models: Set[str] = set()

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in self.IGNORED_DIRS and not d.startswith(".")]

            for f in filenames:
                full_path = Path(dirpath) / f
                rel_path = str(full_path.relative_to(root))

                # Protobuf
                if f.endswith(".proto"):
                    proto_files.append(rel_path)

                # GraphQL
                elif f.endswith((".graphql", ".gql")) or "schema.graphql" in f:
                    graphql_schemas.append(rel_path)

                # OpenAPI / Swagger
                elif "openapi" in f.lower() or "swagger" in f.lower():
                    if f.endswith((".json", ".yaml", ".yml")):
                        openapi_specs.append(rel_path)

                # Static code route discovery (Python FastAPI/Flask, Express, etc.)
                elif f.endswith(".py"):
                    self._extract_python_routes(full_path, rel_path, endpoints, db_models)
                elif f.endswith((".js", ".ts")):
                    self._extract_js_routes(full_path, rel_path, endpoints)

        imap.has_openapi = len(openapi_specs) > 0
        imap.openapi_specs = sorted(openapi_specs)
        imap.has_graphql = len(graphql_schemas) > 0
        imap.graphql_schemas = sorted(graphql_schemas)
        imap.has_grpc = len(proto_files) > 0
        imap.proto_files = sorted(proto_files)
        imap.rest_endpoints = endpoints
        imap.database_models = sorted(list(db_models))

        return imap

    def _extract_python_routes(self, full_path: Path, rel_path: str, endpoints: List[EndpointInfo], db_models: Set[str]) -> None:
        """Heuristically extracts FastAPI/Flask routes and ORM models from Python files."""
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            # Route decorator patterns: @app.get("/path"), @router.post("/items")
            route_pattern = re.compile(r'@(?:app|router|api)\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)["\']')
            # Class ORM patterns: class User(Base): or class Item(models.Model):
            model_pattern = re.compile(r'class\s+([A-Za-z0-9_]+)\s*\(\s*(?:Base|models\.Model|SQLModel|Document)')

            for idx, line in enumerate(lines):
                m_route = route_pattern.search(line)
                if m_route:
                    method = m_route.group(1).upper()
                    path = m_route.group(2)
                    endpoints.append(
                        EndpointInfo(
                            method=method,
                            path=path,
                            source_file=rel_path,
                            line_number=idx + 1,
                        )
                    )

                m_model = model_pattern.search(line)
                if m_model:
                    db_models.add(m_model.group(1))
        except Exception:
            pass

    def _extract_js_routes(self, full_path: Path, rel_path: str, endpoints: List[EndpointInfo]) -> None:
        """Heuristically extracts Express/Fastify/NestJS routes from JS/TS files."""
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            # Express patterns: app.get('/path', ...), router.post('/login', ...)
            route_pattern = re.compile(r'(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']')

            for idx, line in enumerate(lines):
                m = route_pattern.search(line)
                if m:
                    method = m.group(1).upper()
                    path = m.group(2)
                    endpoints.append(
                        EndpointInfo(
                            method=method,
                            path=path,
                            source_file=rel_path,
                            line_number=idx + 1,
                        )
                    )
        except Exception:
            pass
