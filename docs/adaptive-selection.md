# Aegis Adaptive Test Selection 2.0 & Selection Explanations

## 1. Multi-Factor Adaptive Planning

Adaptive Test Selection 2.0 combines:
1. **Change Impact Blast Radius**: Directly affected tests receive top priority ($100$).
2. **Historical Defect Correlations**: Tests historically correlated with modified symbols receive priority boosts ($85$).
3. **Risk Tier & Recommendation**: High/Critical risk triggers full regression coverage.
4. **Execution Cost Awareness**: Lower-cost equivalent validations are prioritized.

## 2. Explainable Selection Rationale (`--explain`)

Every planned and skipped test provides concrete, machine-verifiable explanations:

```text
[✓ SELECTED] test.pytest.impacted (Value Score: 95.0)
    • Directly exercises changed code across 2 file(s).
    • Test framework: pytest
    • Historical correlation confidence: 0.85

[✗ SKIPPED] test.jest.skipped (Value Score: 10.0)
    • No direct or transitive dependency to changed code (LOW risk, changed-only mode)
```
