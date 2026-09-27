# Aegis Failure Intelligence & Classification

## 1. Volatile Noise Normalization & Secret Redaction

Before fingerprinting or storing error logs, the `FailureClassifier` sanitizes volatile runtime patterns:
- **Secrets & API Keys**: `password`, `token`, `bearer`, JWT tokens, and `ghp_...` tokens -> `<REDACTED_SECRET>`
- **Memory Addresses**: `0x7fff5bfc` -> `<HEX_ADDR>`
- **UUIDs**: `12345678-1234-1234-1234-123456789abc` -> `<UUID>`
- **Timestamps**: ISO8601 & RFC3339 timestamps -> `<TIMESTAMP>`
- **Temporary Paths**: `/tmp/...` & `/private/var/folders/...` -> `<TMP_PATH>`
- **Dynamic Ports**: `localhost:54321` -> `localhost:<PORT>`

## 2. Deterministic Failure Classification

Failures are categorized with confidence scores into:
- `PRODUCT_DEFECT`: Assertion failures, schema contract breaks, 500 error responses from application code.
- `TEST_DEFECT`: Unhandled exceptions, bad mock setups, or syntax errors in test files.
- `INFRASTRUCTURE`: Missing runner binaries, killed containers, daemon crashes.
- `ENVIRONMENT`: Missing environment variables or incompatible platforms.
- `TIMEOUT`: Execution exceeded allocated deadline.
- `NETWORK`: Socket connection refused, DNS lookup failure.
- `DEPENDENCY`: Missing packages or imports.
- `CONFIGURATION`: Missing config files or invalid YAML/JSON.

## 3. Fingerprint Clustering Lifecycle

Fingerprints are tracked across executions:
- `NEW_FAILURE`: First occurrence.
- `RECURRING_FAILURE`: Repeated occurrence across multiple runs.
- `RESOLVED_FAILURE`: Fingerprint absent after bug fix.
- `REGRESSED_FAILURE`: Previously resolved failure recurring in a newer run.
- `FLAKY_FAILURE`: Intermittent alternating pass/fail pattern.
