# Aegis Change Impact Engine

## 1. Overview
The **Change Impact Engine** connects file-level diffs to AST symbol modifications and traverses the Project Intelligence Graph to calculate downstream blast radius.

## 2. Pipeline
```
GIT / DISK CHANGE
       │
       ▼
SYMBOL DIFFING (Added, Modified, Deleted, Signature Changed)
       │
       ▼
GRAPH TRAVERSAL (Downstream dependents)
       │
       ▼
SURFACE CLASSIFICATION (Affected APIs, UI, DB, Tests)
       │
       ▼
BLAST RADIUS METRICS (Direct vs Indirect count)
```

## 3. Symbol Change Types
* `ADDED`: New symbol introduced.
* `MODIFIED`: Symbol body modified with signature unchanged.
* `SIGNATURE_CHANGED`: Function arguments, return type, or class inheritance altered (high contract breaking risk).
* `DELETED`: Symbol removed.
* `COMMENTS_ONLY`: Only docstrings/comments altered (zero downstream regression impact).

## 4. Impact Report Schema
```json
{
  "report_id": "imp_01...",
  "tree_hash": "sha256...",
  "has_changes": true,
  "changed_files": ["app/repositories.py"],
  "changed_symbols": [
    {
      "symbol_id": "python:app.repositories.UserRepository.get_by_id",
      "name": "get_by_id",
      "change_type": "SIGNATURE_CHANGED"
    }
  ],
  "affected_apis": [
    {
      "id": "api:GET:/api/v1/users",
      "name": "GET /api/v1/users",
      "confidence": "HIGH_CONFIDENCE",
      "hop_distance": 2
    }
  ],
  "blast_radius": {
    "direct_count": 2,
    "indirect_count": 5,
    "total_affected": 7,
    "max_depth": 5
  }
}
```
