"""
Aegis Core Orchestrator Engine
Coordinates discovery, storage, change impact detection, evidence accumulation, and release gating.
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from aegis.core.config import AegisConfig
from aegis.core.events import (
    EventBus,
    DiscoveryStartedEvent,
    DiscoveryCompletedEvent,
    ReleaseVerdictComputedEvent,
    default_event_bus,
    generate_id,
)
from aegis.core.executor import ProcessExecutor
from aegis.discovery.detector import ProjectDiscoveryEngine, ProjectProfile
from aegis.storage.filesystem import FilesystemStorage
from aegis.storage.hashing import IncrementalChangeEngine, ChangeSet
from aegis.indexer.symbol_index import SymbolIndex
from aegis.graph.project_graph import ProjectGraph
from aegis.graph.models import GraphStats
from aegis.impact.analyzer import ChangeImpactEngine
from aegis.impact.models import ImpactReport
from aegis.planner.risk import AdaptiveRiskEngine
from aegis.planner.models import RiskAssessment, TestPlan
from aegis.planner.planner import AdaptiveTestPlanner
from aegis.runners.registry import RunnerRegistry
from aegis.runners.unit_runner import UniversalUnitRunner
from aegis.runners.sanity_runner import SanityPreflightRunner
from aegis.runners.api_runner import ContractAPIRunner
from aegis.runners.integration_runner import IntegrationRunner
from aegis.runners.e2e_runner import E2EJourneyRunner
from aegis.runners.ui_runner import UIFunctionalRunner
from aegis.runners.base import ExecutionContext, RunnerCategory
from aegis.execution.dag import ExecutionDAGBuilder
from aegis.execution.scheduler import DAGScheduler
from aegis.execution.models import ExecutionDAG, DAGNodeStatus
from aegis.evidence.models import (
    ReleaseAssessment,
    ReleaseGateVerdict,
    PolicyCheckResult,
    EvidenceReport,
    TestResult,
    TestStatus,
)
from aegis.evidence.collector import EvidenceCollector


class AegisEngine:
    """Central orchestrator for the Aegis quality engineering platform."""

    def __init__(
        self,
        workspace_root: Optional[Path | str] = None,
        config: Optional[AegisConfig] = None,
        storage: Optional[FilesystemStorage] = None,
        event_bus: Optional[EventBus] = None,
        executor: Optional[ProcessExecutor] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.config = config or AegisConfig.load(workspace_root=self.workspace_root)
        self.storage = storage or FilesystemStorage(self.workspace_root, dir_name=self.config.storage.dir_name)
        self.event_bus = event_bus or default_event_bus
        self.executor = executor or ProcessExecutor(
            default_cwd=str(self.workspace_root),
            default_timeout_seconds=self.config.execution.timeout_seconds,
        )

        self.discovery_engine = ProjectDiscoveryEngine(self.workspace_root, storage=self.storage)
        self.change_engine = IncrementalChangeEngine(self.workspace_root, storage=self.storage)
        self.symbol_index = SymbolIndex(self.workspace_root, storage=self.storage)
        self.graph = ProjectGraph(self.workspace_root)
        self.impact_engine = ChangeImpactEngine(
            self.workspace_root,
            graph=self.graph,
            symbol_index=self.symbol_index,
            change_engine=self.change_engine,
        )
        self.risk_engine = AdaptiveRiskEngine()
        self.planner = AdaptiveTestPlanner()

        # Phase 3 Execution Layer
        self.runner_registry = RunnerRegistry()
        self._register_default_runners()
        self.dag_builder = ExecutionDAGBuilder()
        self.dag_scheduler = DAGScheduler(
            registry=self.runner_registry,
            storage=self.storage,
            max_workers=self.config.execution.max_workers,
        )

    def _register_default_runners(self) -> None:
        """Registers all built-in universal test runners."""
        self.runner_registry.register(UniversalUnitRunner(self.workspace_root, executor=self.executor))
        self.runner_registry.register(SanityPreflightRunner(self.workspace_root))
        self.runner_registry.register(ContractAPIRunner(self.workspace_root))
        self.runner_registry.register(IntegrationRunner(self.workspace_root, executor=self.executor))
        self.runner_registry.register(E2EJourneyRunner(self.workspace_root))
        self.runner_registry.register(UIFunctionalRunner(self.workspace_root))

    def init_workspace(self) -> Path:
        """Initializes Aegis workspace structure and writes default configuration."""
        config_path = self.config.save(self.workspace_root / self.config.storage.dir_name / "config.yaml")
        # Run initial discovery and build semantic graph
        self.discover()
        self.build_graph()
        self.change_engine.commit_hashes()
        return config_path

    def discover(self, project_name: Optional[str] = None) -> ProjectProfile:
        """Discovers full repository structure and saves all machine-readable profiles."""
        corr_id = generate_id("corr")
        self.event_bus.publish(DiscoveryStartedEvent(correlation_id=corr_id, payload={"root": str(self.workspace_root)}))

        p_name = project_name or (self.config.project.name if self.config.project.name != "auto-detected" else self.workspace_root.name)
        profile = self.discovery_engine.discover(project_name=p_name)

        self.event_bus.publish(
            DiscoveryCompletedEvent(
                correlation_id=corr_id,
                payload={
                    "project_name": profile.project_name,
                    "languages": [l.name for l in profile.languages],
                    "frameworks": [f.name for f in profile.frameworks],
                    "tree_hash": profile.tree_hash,
                },
            )
        )
        return profile

    def build_graph(self, force_full: bool = False) -> GraphStats:
        """Indexes symbols and synchronizes them to the persistent graph database."""
        self.symbol_index.index_workspace(force_full=force_full)
        stats = self.graph.sync_from_symbol_index(self.symbol_index)
        return stats

    def analyze_impact(self, max_depth: int = 5) -> ImpactReport:
        """Calculates exact symbol modifications and downstream blast radius."""
        report = self.impact_engine.analyze_impact(max_depth=max_depth)
        if self.storage:
            self.storage.save_json("impact.json", report.model_dump())
        return report

    def assess_risk(self, impact: Optional[ImpactReport] = None) -> RiskAssessment:
        """Evaluates deterministic, explainable risk score for current change state."""
        imp = impact or self.analyze_impact()
        assessment = self.risk_engine.assess_risk(imp)
        if self.storage:
            self.storage.save_json("risk-assessment.json", assessment.model_dump())
        return assessment

    def plan_tests(self, changed_only: bool = False) -> TestPlan:
        """Generates an adaptive test plan based on impact and risk analysis."""
        profile = self.discover()
        imp = self.analyze_impact()
        risk = self.assess_risk(imp)
        plan = self.planner.plan_tests(
            impact=imp,
            risk=risk,
            available_suites=profile.test_suites,
            changed_only=changed_only,
        )
        if self.storage:
            self.storage.save_json("test-plan.json", plan.model_dump())
        return plan

    def execute_plan(
        self,
        test_plan: Optional[TestPlan] = None,
        categories: Optional[List[str]] = None,
        fail_fast: bool = True,
        parallel: bool = True,
        dry_run: bool = False,
    ) -> EvidenceReport:
        """
        Builds the execution DAG from the test plan and runs all stages via the DAGScheduler.
        Records machine-verifiable evidence and updates release readiness assessment.
        """
        profile = self.discover()
        plan = test_plan or self.plan_tests()
        dag = self.dag_builder.build_dag(plan, target_categories=categories)

        corr_id = generate_id("corr")
        collector = EvidenceCollector(
            project_name=profile.project_name,
            correlation_id=corr_id,
            storage=self.storage,
            event_bus=self.event_bus,
        )

        exec_context = ExecutionContext(
            workspace_root=str(self.workspace_root),
            dry_run=dry_run or self.config.execution.dry_run,
            timeout_seconds=self.config.execution.timeout_seconds,
            correlation_id=corr_id,
        )

        # Execute DAG
        self.dag_scheduler.execute_dag(
            dag=dag,
            context=exec_context,
            collector=collector,
            tree_hash=profile.tree_hash,
            fail_fast=fail_fast,
            parallel=parallel and self.config.execution.parallel,
        )

        report = collector.generate_report(tree_hash=profile.tree_hash)
        assessment = self.assess_release_readiness(report)
        report.release_assessment = assessment

        if self.storage:
            self.storage.save_json("report.json", report.model_dump())
            self.storage.save_json("execution-dag.json", dag.model_dump())

        return report

    def assess_release_readiness(self, report: EvidenceReport) -> ReleaseAssessment:
        """
        Evaluates release policies deterministically against the evidence report.
        Strict policy verification: zero AI hallucinations allowed in gating.
        """
        policy = self.config.release
        checks: List[PolicyCheckResult] = []
        reasons: List[str] = []
        verdict = ReleaseGateVerdict.READY

        # 1. Critical test failures check
        if policy.critical_tests_must_pass and report.failed > 0:
            checks.append(
                PolicyCheckResult(
                    policy_name="critical_tests_must_pass",
                    passed=False,
                    details=f"{report.failed} test(s) failed during validation run.",
                )
            )
            reasons.append(f"Blocked by {report.failed} failing test(s).")
            verdict = ReleaseGateVerdict.BLOCKED
        else:
            checks.append(
                PolicyCheckResult(
                    policy_name="critical_tests_must_pass",
                    passed=True,
                    details="All executed tests passed successfully.",
                )
            )

        # 2. Execution errors check
        if report.errors > 0:
            checks.append(
                PolicyCheckResult(
                    policy_name="zero_execution_errors",
                    passed=False,
                    details=f"{report.errors} test runner error(s) or timeout(s) detected.",
                )
            )
            reasons.append(f"{report.errors} runner error(s) occurred.")
            verdict = ReleaseGateVerdict.BLOCKED
        else:
            checks.append(
                PolicyCheckResult(
                    policy_name="zero_execution_errors",
                    passed=True,
                    details="Zero runner execution errors or timeouts.",
                )
            )

        # 3. Human approval requirement flag
        if policy.require_human_approval and verdict == ReleaseGateVerdict.READY:
            checks.append(
                PolicyCheckResult(
                    policy_name="require_human_approval",
                    passed=True,
                    details="Release meets automated criteria; awaiting required human approval.",
                )
            )
            verdict = ReleaseGateVerdict.REQUIRES_REVIEW
            reasons.append("Automated policies passed. Requires final human confirmation per release policy.")

        assessment = ReleaseAssessment(
            verdict=verdict,
            policy_checks=checks,
            reasons=reasons,
            total_tests=report.total_tests,
            passed_tests=report.passed,
            failed_tests=report.failed,
            critical_failures=report.failed + report.errors,
            security_vulnerabilities=0,
            accessibility_score=1.0,
            performance_regression_pct=0.0,
        )

        self.event_bus.publish(
            ReleaseVerdictComputedEvent(
                correlation_id=report.correlation_id,
                payload={"verdict": verdict.value, "reasons": reasons},
            )
        )

        return assessment
