from pathlib import Path
from aegis.evidence.collector import EvidenceCollector
from aegis.evidence.models import TestResult, TestStatus
from aegis.execution.dag import ExecutionDAGBuilder
from aegis.execution.models import DAGNodeStatus
from aegis.execution.scheduler import DAGScheduler
from aegis.planner.models import TestPlan, PlannedTest, RiskLevel
from aegis.runners.base import (
    TestRunner,
    RunnerCapability,
    RunnerCategory,
    ExecutionContext,
    RunnerPlan,
)
from aegis.runners.registry import RunnerRegistry
from aegis.storage.filesystem import FilesystemStorage


class MockPassingRunner(TestRunner):
    @property
    def capability(self) -> RunnerCapability:
        return RunnerCapability(name="mock_pass", categories=[RunnerCategory.SANITY, RunnerCategory.UNIT, RunnerCategory.API, RunnerCategory.INTEGRATION, RunnerCategory.E2E, RunnerCategory.UI])

    def supports(self, context: ExecutionContext) -> bool:
        return True

    def plan(self, context: ExecutionContext) -> RunnerPlan:
        return RunnerPlan(runner_name="mock_pass", category=context.category, command=["echo", "pass"], cwd=str(self.workspace_root))

    def execute(self, plan: RunnerPlan, context: ExecutionContext) -> list[TestResult]:
        return [TestResult(test_id=f"{context.category.value}.pass", name=f"{context.category.value} Pass", category=context.category.value, status=TestStatus.PASSED, duration_ms=5.0)]


class MockFailingSanityRunner(TestRunner):
    @property
    def capability(self) -> RunnerCapability:
        return RunnerCapability(name="mock_fail_sanity", categories=[RunnerCategory.SANITY])

    def supports(self, context: ExecutionContext) -> bool:
        return True

    def plan(self, context: ExecutionContext) -> RunnerPlan:
        return RunnerPlan(runner_name="mock_fail_sanity", category=RunnerCategory.SANITY, command=["echo", "fail"], cwd=str(self.workspace_root))

    def execute(self, plan: RunnerPlan, context: ExecutionContext) -> list[TestResult]:
        return [TestResult(test_id="sanity.fail", name="Sanity Crash", category="sanity", status=TestStatus.FAILED, duration_ms=5.0, raw_stderr="Database connection refused")]


def test_dag_scheduler_success_run(tmp_path: Path):
    storage = FilesystemStorage(workspace_root=tmp_path)
    registry = RunnerRegistry()
    mock_runner = MockPassingRunner(workspace_root=tmp_path)
    registry.register(mock_runner)

    scheduler = DAGScheduler(registry=registry, storage=storage, max_workers=2)
    builder = ExecutionDAGBuilder()
    plan = TestPlan(
        plan_id="p1",
        risk_level=RiskLevel.MEDIUM,
        selected_tests=[PlannedTest(test_id="u1", name="Unit", category="unit", runner_cmd="pytest")],
    )

    dag = builder.build_dag(plan)
    # Re-point runner names to mock
    for n in dag.nodes.values():
        if n.status != DAGNodeStatus.SKIPPED:
            n.runner_name = "mock_pass"

    collector = EvidenceCollector(project_name="test_proj", storage=storage)
    ctx = ExecutionContext(workspace_root=str(tmp_path))

    results = scheduler.execute_dag(dag, context=ctx, collector=collector, tree_hash="hash_123")
    assert len(results) >= 5
    assert all(r.status == TestStatus.PASSED for r in results)
    assert dag.is_complete()
    assert all(n.status in (DAGNodeStatus.PASSED, DAGNodeStatus.SKIPPED) for n in dag.nodes.values())


def test_dag_scheduler_fast_fail_cascade(tmp_path: Path):
    storage = FilesystemStorage(workspace_root=tmp_path)
    registry = RunnerRegistry()
    registry.register(MockFailingSanityRunner(workspace_root=tmp_path))
    registry.register(MockPassingRunner(workspace_root=tmp_path))

    scheduler = DAGScheduler(registry=registry, storage=storage, max_workers=2)
    builder = ExecutionDAGBuilder()
    plan = TestPlan(
        plan_id="p2",
        risk_level=RiskLevel.HIGH,
        selected_tests=[PlannedTest(test_id="u2", name="Unit", category="unit", runner_cmd="pytest")],
    )

    dag = builder.build_dag(plan)
    dag.nodes["dag.sanity.preflight"].runner_name = "mock_fail_sanity"
    for nid, n in dag.nodes.items():
        if nid != "dag.sanity.preflight" and n.status != DAGNodeStatus.SKIPPED:
            n.runner_name = "mock_pass"

    collector = EvidenceCollector(project_name="fail_proj", storage=storage)
    ctx = ExecutionContext(workspace_root=str(tmp_path))

    results = scheduler.execute_dag(dag, context=ctx, collector=collector, tree_hash="hash_fail", fail_fast=True)
    
    # Sanity failed
    assert dag.nodes["dag.sanity.preflight"].status == DAGNodeStatus.FAILED

    # Dependent stages must be BLOCKED
    assert dag.nodes["dag.unit.0"].status == DAGNodeStatus.BLOCKED
    assert dag.nodes["dag.api.contract"].status == DAGNodeStatus.BLOCKED
    assert dag.nodes["dag.integration.suite"].status == DAGNodeStatus.BLOCKED
    assert dag.nodes["dag.e2e.journeys"].status == DAGNodeStatus.BLOCKED

    assert "Blocked by upstream failure" in (dag.nodes["dag.unit.0"].block_reason or "")
