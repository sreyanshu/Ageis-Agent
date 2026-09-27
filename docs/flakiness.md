# Aegis Flakiness Analysis Engine

## 1. Instability Rate & State Transitions

Aegis avoids labeling tests as flaky based on a single retry. The `FlakinessEngine` evaluates outcome sequences across chronological executions:

$$\text{InstabilityRate} = \frac{\text{Transitions}(\text{PASS} \leftrightarrow \text{FAIL})}{\max(1, N - 1)}$$

## 2. Flakiness Statuses

- **`STABLE`**: Low or zero instability across sufficient runs ($N \ge 4$).
- **`SUSPECTED_FLAKY`**: Instability rate $\ge 0.10$ with mixed pass and fail outcomes.
- **`FLAKY`**: Instability rate $\ge 0.25$ or retry count $> 0$ with mixed outcomes.
- **`UNKNOWN`**: Insufficient historical sample count ($N < 4$).
