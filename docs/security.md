# Aegis Security Quality Dimension

## 1. SARIF v2.1.0 Parser & Ingestion

Aegis implements an engine-agnostic SARIF v2.1.0 parser that ingests reports from SAST, DAST, dependency scanners (e.g. Bandit, Semgrep, Trivy, CodeQL, Snyk).

### 1.1 Ingestion Sources
- `.aegis/security/*.sarif`
- `*.sarif` in workspace root or `reports/*.sarif`
- Explicit SARIF report files specified via context options

## 2. Severity Mapping & Provenance

SARIF findings map to Aegis `FindingSeverity`:
- SARIF `level: "error"` or `security-severity >= 9.0` -> `FindingSeverity.CRITICAL` / `FindingSeverity.HIGH`
- SARIF `level: "warning"` -> `FindingSeverity.MEDIUM`
- SARIF `level: "note"` / `"info"` -> `FindingSeverity.LOW` / `FindingSeverity.INFO`

Every finding preserves complete provenance:
- Scanner name and tool driver version
- Rule ID and full description
- Physical location (file path, line, column, snippet)
- Help URI

## 3. Fingerprinting & Release Gating

Deterministic fingerprint:
$$\text{FP} = \text{SHA256}(\text{"security"} + \text{Scanner} + \text{RuleID} + \text{FilePath} + \text{Line})$$

Release policies enforce:
- `critical_new == 0`
- `high_new <= threshold`
- Existing findings permitted only with non-expired signed `Waiver`
