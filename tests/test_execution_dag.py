from aegis.execution.dag import ExecutionDAGBuilder
from aegis.execution.models import DAGNodeStatus
from aegis.planner.models import TestPlan, PlannedTest, SkippedTest, RiskLevel
from aegis.runners.base import RunnerCategory


def test_dag_builder_structure():
    builder = ExecutionDAGBuilder()
    plan = TestPlan(
        plan_id="plan_1",
        risk_level=RiskLevel.HIGH,
        selected_tests=[
            PlannedTest(test_id="t1", name="Unit Suite", category="unit", runner_cmd="pytest", priority=100),
        ],
        skipped_tests=[
            SkippedTest(test_id="t2", name="Vitest Suite", category="unit", skip_reason="Unchanged"),
        ],
    )

    dag = builder.build_dag(plan)
    assert "dag.sanity.preflight" in dag.nodes
    assert "dag.unit.0" in dag.nodes
    assert "dag.api.contract" in dag.nodes
    assert "dag.integration.suite" in dag.nodes
    assert "dag.e2e.journeys" in dag.nodes
    assert "dag.ui.visual" in dag.nodes

    # Check dependencies: Unit and API depend on Sanity
    assert "dag.sanity.preflight" in dag.nodes["dag.unit.0"].dependencies
    assert "dag.sanity.preflight" in dag.nodes["dag.api.contract"].dependencies

    # Integration depends on Unit and API
    assert "dag.unit.0" in dag.nodes["dag.integration.suite"].dependencies

    # Initially, only root nodes (Sanity) are READY
    ready = dag.get_ready_nodes()
    assert len(ready) == 1
    assert ready[0].node_id == "dag.sanity.preflight"
