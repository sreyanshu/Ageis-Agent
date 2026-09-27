# Aegis Test Effectiveness & Value Model

## 1. Distinguishing Real Defects from Infrastructure Noise

Aegis separates raw test failures from real product defects:
- Failures classified as `PRODUCT_DEFECT` or `CONFIGURATION` contribute to `defects_detected` and `regressions_detected`.
- Failures caused by `INFRASTRUCTURE`, `TIMEOUT`, or `NETWORK` are tracked separately as `false_infra_failures`.

## 2. Test Value Scoring Model

$$\text{ValueScore} = \text{BaseScore} + \text{DefectBonus} - \text{CostPenalty} - \text{FlakinessPenalty}$$

- **Defect Yield Rate**: $\frac{\text{Defects Detected}}{\text{Total Executions}}$ (contributes up to 45 points)
- **Cost Score**: Normalized execution duration ($0.0$ for $<50\text{ms}$, $1.0$ for $>5000\text{ms}$)
- **Flakiness Penalty**: Up to $-20$ points for unstable tests
- **Composite Value Range**: Clamped between $5.0$ and $100.0$.
