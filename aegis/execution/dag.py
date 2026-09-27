"""
Aegis Execution DAG Builder
Compiles high-level TestPlans and runner capabilities into structured,
dependency-ordered ExecutionDAGs.
"""

from __future__ import annotations
from typing import Dict, List, Set, Optional

from aegis.core.events import generate_id
from aegis.execution.models import ExecutionDAG, DAGNode, DAGNodeStatus
from aegis.planner.models import TestPlan, RiskLevel
from aegis.runners.base import RunnerCategory


class ExecutionDAGBuilder:
    """Builds dependency-ordered DAGs from test plans."""

    def build_dag(self, plan: TestPlan, target_categories: Optional[List[str]] = None) -> ExecutionDAG:
        nodes: Dict[str, DAGNode] = {}
        dag_id = generate_id("dag")

        # 1. Root Stage: Sanity Preflight Probe
        sanity_id = "dag.sanity.preflight"
        nodes[sanity_id] = DAGNode(
            node_id=sanity_id,
            runner_name="aegis_sanity_runner",
            category=RunnerCategory.SANITY,
            test_id="sanity.preflight",
            name="Sanity Preflight Probe",
            priority=100,
            dependencies=[],
        )

        unit_node_ids: List[str] = []
        api_node_ids: List[str] = []

        # 2. Level 1: Unit Tests
        for idx, pt in enumerate(plan.selected_tests):
            if pt.category == "unit":
                nid = f"dag.unit.{idx}"
                nodes[nid] = DAGNode(
                    node_id=nid,
                    runner_name="native_unit_runner",
                    category=RunnerCategory.UNIT,
                    test_id=pt.test_id,
                    name=pt.name,
                    priority=pt.priority,
                    dependencies=[sanity_id],
                )
                unit_node_ids.append(nid)

        # 3. Level 1: API Tests
        api_id = "dag.api.contract"
        nodes[api_id] = DAGNode(
            node_id=api_id,
            runner_name="aegis_api_runner",
            category=RunnerCategory.API,
            test_id="api.contract_suite",
            name="Contract API Validation Suite",
            priority=80 if plan.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) else 60,
            dependencies=[sanity_id],
        )
        api_node_ids.append(api_id)

        # 4. Level 2: Integration Tests (depends on unit + api passing)
        integration_id = "dag.integration.suite"
        nodes[integration_id] = DAGNode(
            node_id=integration_id,
            runner_name="aegis_integration_runner",
            category=RunnerCategory.INTEGRATION,
            test_id="integration.suite",
            name="Integration Test Suite",
            priority=70,
            dependencies=unit_node_ids + api_node_ids,
        )

        # 5. Level 3: End-to-End Tests (depends on integration passing)
        e2e_id = "dag.e2e.journeys"
        nodes[e2e_id] = DAGNode(
            node_id=e2e_id,
            runner_name="aegis_e2e_runner",
            category=RunnerCategory.E2E,
            test_id="e2e.journeys",
            name="E2E Browser Journey Suite",
            priority=50,
            dependencies=[integration_id],
        )

        # 6. Level 4: UI & Visual Regression (depends on E2E passing)
        ui_id = "dag.ui.visual"
        nodes[ui_id] = DAGNode(
            node_id=ui_id,
            runner_name="aegis_ui_runner",
            category=RunnerCategory.UI,
            test_id="ui.visual",
            name="UI Functional & Visual Suite",
            priority=40,
            dependencies=[e2e_id],
        )

        # 7. Add Skipped nodes from TestPlan
        for idx, st in enumerate(plan.skipped_tests):
            sk_id = f"dag.skipped.{idx}"
            nodes[sk_id] = DAGNode(
                node_id=sk_id,
                runner_name="none",
                category=RunnerCategory(st.category) if st.category in RunnerCategory.__members__.values() else RunnerCategory.UNIT,
                test_id=st.test_id,
                name=st.name,
                priority=0,
                status=DAGNodeStatus.SKIPPED,
                block_reason=st.skip_reason,
            )

        # Filter categories if a specific category was requested (e.g. `aegis test unit`)
        if target_categories and "all" not in target_categories:
            cats = set(target_categories)
            for nid, node in list(nodes.items()):
                if node.category.value not in cats and node.category != RunnerCategory.SANITY:
                    nodes.pop(nid, None)

        return ExecutionDAG(dag_id=dag_id, nodes=nodes)
