# Aegis Adaptive Test Planning Foundation

## 1. Overview
The **Adaptive Test Planner** calculates an optimal test execution plan by maximizing test utility:

$$\text{Test Utility} = \frac{\text{Expected Regression Detection Value}}{\text{Execution Cost}}$$

## 2. Test Selection & Prioritization
* **Directly Impacted Tests (Priority 100):** Test files that explicitly test or import modified symbols.
* **Downstream Integration / API Tests (Priority 80):** Validations scheduled due to affected public routes or High/Critical risk scores.
* **Baseline Regression Tests (Priority 50):** Baseline sanity checks.
* **Safely Skipped Tests:** Suites with zero direct or transitive dependency to changed code when operating in `changed_only` mode under Low risk. Every skipped test includes a concrete reason.

## 3. Plan Output Schema
```json
{
  "plan_id": "plan_01...",
  "risk_level": "LOW",
  "total_planned": 1,
  "total_skipped": 2,
  "selected_tests": [
    {
      "test_id": "test.pytest.impacted",
      "name": "pytest Impacted Suite",
      "category": "unit",
      "runner_cmd": "pytest tests/test_service.py",
      "priority": 100,
      "selection_reason": "Directly exercises changed code in 1 file(s)"
    }
  ],
  "skipped_tests": [
    {
      "test_id": "test.vitest.skipped",
      "name": "vitest Suite",
      "category": "unit",
      "skip_reason": "No direct or transitive dependency to changed code (LOW risk)"
    }
  ]
}
```
