from pathlib import Path
from aegis.runners.registry import RunnerRegistry
from aegis.runners.unit_runner import UniversalUnitRunner
from aegis.runners.sanity_runner import SanityPreflightRunner
from aegis.runners.api_runner import ContractAPIRunner
from aegis.runners.integration_runner import IntegrationRunner
from aegis.runners.e2e_runner import E2EJourneyRunner, UserJourney, JourneyStep, JourneyStepAction
from aegis.runners.ui_runner import UIFunctionalRunner
from aegis.runners.base import ExecutionContext, RunnerCategory
from aegis.evidence.models import TestStatus


def test_runner_registry():
    registry = RunnerRegistry()
    unit = UniversalUnitRunner(workspace_root=".")
    sanity = SanityPreflightRunner(workspace_root=".")
    api = ContractAPIRunner(workspace_root=".")

    registry.register(unit)
    registry.register(sanity)
    registry.register(api)

    assert registry.get_runner("native_unit_runner") is not None
    assert len(registry.find_runners_for_category(RunnerCategory.UNIT)) == 1
    assert len(registry.find_runners_for_category(RunnerCategory.SANITY)) == 1


def test_unit_runner_targeted_and_dry_run(tmp_path: Path):
    runner = UniversalUnitRunner(workspace_root=tmp_path)
    ctx_dry = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.UNIT,
        dry_run=True,
    )

    plan = runner.plan(ctx_dry)
    assert plan.runner_name == "native_unit_runner"
    assert len(plan.command) >= 1

    results = runner.execute(plan, ctx_dry)
    assert len(results) >= 1
    assert results[0].status == TestStatus.PASSED


def test_sanity_runner_preflight(tmp_path: Path):
    runner = SanityPreflightRunner(workspace_root=tmp_path)
    # Create valid manifest and python file
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname='test'\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('Hello')", encoding="utf-8")

    ctx = ExecutionContext(workspace_root=str(tmp_path), category=RunnerCategory.SANITY)
    plan = runner.plan(ctx)
    results = runner.execute(plan, ctx)

    test_ids = [r.test_id for r in results]
    assert "sanity.manifest_integrity" in test_ids
    assert "sanity.syntax_compilation" in test_ids
    assert all(r.status == TestStatus.PASSED for r in results)


def test_api_contract_and_fuzzing_runner(tmp_path: Path):
    runner = ContractAPIRunner(workspace_root=tmp_path)
    ctx = ExecutionContext(workspace_root=str(tmp_path), category=RunnerCategory.API, dry_run=True)

    plan = runner.plan(ctx)
    results = runner.execute(plan, ctx)
    assert len(results) >= 1
    assert all(r.status == TestStatus.PASSED for r in results)


def test_integration_runner_boundary_safety(tmp_path: Path):
    runner = IntegrationRunner(workspace_root=tmp_path)
    # Refuse execution against production environment
    ctx_prod = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.INTEGRATION,
        environment={"ENV": "production"},
    )
    plan = runner.plan(ctx_prod)
    results = runner.execute(plan, ctx_prod)
    assert results[0].status == TestStatus.FAILED
    assert "production" in (results[0].raw_stderr or "").lower()


def test_e2e_and_ui_runners(tmp_path: Path):
    e2e = E2EJourneyRunner(workspace_root=tmp_path)
    ui = UIFunctionalRunner(workspace_root=tmp_path)

    ctx_e2e = ExecutionContext(workspace_root=str(tmp_path), category=RunnerCategory.E2E)
    plan_e2e = e2e.plan(ctx_e2e)
    results_e2e = e2e.execute(plan_e2e, ctx_e2e)
    assert len(results_e2e) >= 1
    assert results_e2e[0].status == TestStatus.PASSED

    ctx_ui = ExecutionContext(workspace_root=str(tmp_path), category=RunnerCategory.UI)
    plan_ui = ui.plan(ctx_ui)
    results_ui = ui.execute(plan_ui, ctx_ui)
    assert len(results_ui) >= 1
    assert results_ui[0].status == TestStatus.PASSED
