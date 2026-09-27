# Aegis Project Intelligence Graph

## 1. Overview
The **Project Intelligence Graph** is Aegis's semantic graph engine. It persists nodes (symbols, components, APIs, database models, tests) and typed directed edges (dependencies, calls, imports, inheritances, route exposures, database accesses) into an indexed SQLite store (`.aegis/graph.db`).

## 2. Node Schema
Each node has a stable identity and strongly typed semantic category:
```json
{
  "id": "python:app.services.UserService.get_user",
  "name": "get_user",
  "symbol_type": "method",
  "language": "python",
  "file_path": "app/services.py",
  "line_start": 25,
  "line_end": 40,
  "signature": "def get_user(self, user_id: int) -> User:",
  "content_hash": "sha256...",
  "metadata": {}
}
```

## 3. Supported Relationships & Provenance
* `contains`: Container to child symbol.
* `imports`: Module or file import dependency.
* `calls`: Function/method invocation.
* `inherits`: Class/interface inheritance.
* `exposes_api`: Route handler mapping to HTTP/gRPC endpoint.
* `consumes_api`: Client fetching or calling remote API.
* `accesses_database`: Entity or query accessing database model/table.
* `tests`: Test function exercising symbol or route.

Every relationship carries provenance explaining *why* it was discovered:
```json
{
  "source_id": "python:app.main.login_endpoint",
  "relation": "exposes_api",
  "target_id": "api:POST:/api/v1/auth/login",
  "confidence": "HIGH_CONFIDENCE",
  "provenance": {
    "file_path": "app/main.py",
    "line_start": 12,
    "line_end": 12,
    "snippet": "@app.post('/api/v1/auth/login')",
    "confidence": "HIGH_CONFIDENCE",
    "rationale": "Handler exposed via POST /api/v1/auth/login"
  }
}
```

## 4. Traversal & Queries
* `get_downstream_impact(start_ids, max_depth)`: Cycle-safe breadth-first traversal identifying blast radius.
* `get_affected_apis(changed_symbol_ids)`: Discovers exposed HTTP routes reachable from changed symbols.
* `get_affected_ui(changed_symbol_ids)`: Discovers UI components downstream of changed client APIs or models.
* `get_affected_tests(changed_symbol_ids)`: Discovers test suites that exercise changed symbols.
