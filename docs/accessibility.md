# Aegis Accessibility Quality Dimension

## 1. Architecture & Adapters

The Accessibility Runner executes WCAG 2.1 compliance audits via pluggable adapters:
- **`AxeCoreAdapter`**: Integrates with axe-core via Node.js/browser substrate.
- **`SimulatedAxeAdapter`**: Deterministic simulated audit for offline and CI fallback testing.

## 2. Finding Normalization

Axe violations are normalized to `QualityFinding` models:
- **Critical impact**: `FindingSeverity.CRITICAL`
- **Serious impact**: `FindingSeverity.HIGH`
- **Moderate impact**: `FindingSeverity.MEDIUM`
- **Minor impact**: `FindingSeverity.LOW`

Each finding includes:
- Target DOM selector (`button.btn-primary`)
- HTML snippet context
- WCAG tags (e.g. `wcag2aa`, `wcag143`)
- Help reference URL and remediation guide
- Deterministic fingerprint `qf_...`

## 3. Baseline & Waiver Policy

Violations are compared against `.aegis/baselines/` reference datasets. Expired or un-waived `CRITICAL` or `HIGH` accessibility findings block production release evaluation.
