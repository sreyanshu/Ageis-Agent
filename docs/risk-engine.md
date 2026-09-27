# Aegis Adaptive Risk Engine

## 1. Overview
The **Adaptive Risk Engine** calculates a deterministic, explainable risk score (0.0 to 1.0) and assigns an operational risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) to any proposed code change.

## 2. Weighted Factor Model
Risk is computed as the weighted sum of five transparent dimensions:

$$\text{Composite Risk} = \sum (\text{Weight}_i \times \text{Raw Score}_i)$$

1. **Change Magnitude ($\text{Weight} = 0.20$):** Number of modified files and changed symbols.
2. **Downstream Blast Radius ($\text{Weight} = 0.25$):** Count of direct and indirect dependent symbols.
3. **API Exposure ($\text{Weight} = 0.25$):** Public API endpoints reachable from changed symbols.
4. **Data Sensitivity ($\text{Weight} = 0.15$):** Database models and tables affected by the change.
5. **Signature Breaking Risk ($\text{Weight} = 0.15$):** Count of altered function/method signatures.

## 3. Operational Categories
* **`LOW` (Score < 0.20):** Isolated, low-blast-radius modifications. Recommendation: Targeted unit tests only.
* **`MEDIUM` (Score 0.20 - 0.44):** Moderate modifications with direct dependents. Recommendation: Targeted tests + direct dependents.
* **`HIGH` (Score 0.45 - 0.74):** Significant blast radius or exposed API alterations. Recommendation: Targeted tests + integration validations.
* **`CRITICAL` (Score $\ge$ 0.75):** Broad cross-cutting contract, database, or API breaking changes. Recommendation: Full regression test suite mandatory.
