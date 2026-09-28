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

        from aegis.adapters.registry import AdapterRegistry, default_adapter_registry
        self.adapter_registry = default_adapter_registry
        self.discovery_engine = ProjectDiscoveryEngine(
            self.workspace_root,
            storage=self.storage,
            adapter_registry=self.adapter_registry,
        )
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

        # Phase 4 Quality Dimensions Layer
        from aegis.quality.registry import QualityRegistry
        self.quality_registry = QualityRegistry(self.workspace_root)

        # Phase 5 Historical Intelligence Layer
        from aegis.history.store import HistoryStore
        from aegis.history.failures import FailureIntelligenceEngine
        self.history_store = HistoryStore(self.workspace_root / self.config.storage.dir_name / "history")
        self.failure_intelligence = FailureIntelligenceEngine(self.history_store)

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

    def plan_tests(self, changed_only: bool = False, explain: bool = False) -> TestPlan:
        """Generates an adaptive test plan based on impact, risk analysis, and historical intelligence."""
        profile = self.discover()
        imp = self.analyze_impact()
        risk = self.assess_risk(imp)
        plan = self.planner.plan_tests(
            impact=imp,
            risk=risk,
            available_suites=profile.test_suites,
            changed_only=changed_only,
            history_store=self.history_store,
            explain=explain,
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
        Records machine-verifiable evidence, tracks historical intelligence, and updates release readiness assessment.
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

        # Record Execution History & Failure Intelligence
        from aegis.history.models import ExecutionRecord
        from aegis.history.correlations import CorrelationEngine
        correlator = CorrelationEngine(self.history_store)
        changed_syms = [s.name for s in plan.metadata.get("changed_symbols", [])]

        history_records: List[ExecutionRecord] = []
        for res in report.test_results:
            cat_enum = None
            fp = res.failure_fingerprint
            if res.status in (TestStatus.FAILED, TestStatus.ERROR, TestStatus.TIMEOUT):
                cluster = self.failure_intelligence.process_failure(
                    test_id=res.test_id,
                    exception_type=res.normalized_error.exception_type if res.normalized_error else "TestFailure",
                    message=res.normalized_error.message if res.normalized_error else (res.raw_stderr or res.raw_stdout or "Failure"),
                    top_stack_frame=res.normalized_error.top_stack_frame if res.normalized_error else None,
                    raw_stderr=res.raw_stderr,
                )
                cat_enum = cluster.classification
                fp = cluster.fingerprint

                for sym in changed_syms:
                    correlator.record_change_failure_link(
                        symbol_name=sym,
                        file_path="workspace",
                        failure_fingerprint=fp,
                        test_id=res.test_id,
                    )

            rec = ExecutionRecord(
                execution_id=generate_id("exec"),
                run_id=report.report_id,
                timestamp=report.created_at,
                project_name=report.project_name,
                commit_or_tree_hash=report.tree_hash,
                test_id=res.test_id,
                category=res.category,
                status=res.status.value,
                duration_ms=res.duration_ms,
                retry_count=res.metadata.get("retries", 0),
                execution_mode="SIMULATED" if dry_run else "REAL",
                failure_fingerprint=fp,
                failure_category=cat_enum,
                risk_level=plan.risk_level.value,
                affected_symbols=changed_syms,
                metadata=res.metadata,
            )
            history_records.append(rec)

        self.history_store.record_executions(history_records)

        if self.storage:
            self.storage.save_json("report.json", report.model_dump())
            self.storage.save_json("execution-dag.json", dag.model_dump())

        return report

    def plan_quality(self, mode: str = "default") -> QualityPlan:
        """Generates an impact and risk-weighted quality dimensions plan."""
        from aegis.quality.planner import QualityPlanner, QualityPlan
        imp = self.analyze_impact()
        risk = self.assess_risk(imp)
        plan = QualityPlanner.plan(impact=imp, risk=risk, mode=mode)
        if self.storage:
            self.storage.save_json("quality-plan.json", plan.model_dump())
        return plan

    def execute_quality(
        self,
        dimension: Optional[str] = None,
        mode: str = "default",
        dry_run: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Executes targeted or full quality dimension evaluations."""
        from aegis.quality.models import QualityDimension, QualityResult
        opts = dict(options or {})
        if dry_run:
            opts["simulate"] = True
            opts["dry_run"] = True

        exec_context = ExecutionContext(
            workspace_root=str(self.workspace_root),
            dry_run=dry_run,
            options=opts,
        )

        results: Dict[str, QualityResult] = {}
        if dimension and dimension.lower() not in ("all", "quality"):
            dim_enum = QualityDimension(dimension.lower())
            res = self.quality_registry.execute_dimension(dim_enum, exec_context)
            results[dim_enum.value] = res
        else:
            all_res = self.quality_registry.execute_all(exec_context)
            results = {dim.value: res for dim, res in all_res.items()}

        if self.storage:
            serialized = {k: v.model_dump() for k, v in results.items()}
            self.storage.save_json("quality-results.json", serialized)

        return results

    def assess_release_readiness(
        self,
        report: EvidenceReport,
        quality_results: Optional[Dict[str, Any]] = None,
    ) -> ReleaseAssessment:
        """
        Evaluates release policies deterministically against the evidence report and quality dimensions.
        Strict policy verification: zero AI hallucinations allowed in gating.
        """
        from aegis.quality.gate import QualityPolicyEvaluator, QualityReleasePolicy
        from aegis.quality.models import QualityResult

        q_res = quality_results
        if q_res is None and self.storage:
            stored_q = self.storage.load_json("quality-results.json")
            if stored_q:
                try:
                    q_res = {k: QualityResult(**v) for k, v in stored_q.items()}
                except Exception:
                    q_res = None

        assessment = QualityPolicyEvaluator.evaluate(
            report=report,
            quality_results=q_res,
            policy=QualityReleasePolicy(
                require_real_execution=False if self.config.execution.dry_run else False,
                require_human_approval=self.config.release.require_human_approval,
            ),
        )

        self.event_bus.publish(
            ReleaseVerdictComputedEvent(
                correlation_id=report.correlation_id,
                payload={"verdict": assessment.verdict.value, "reasons": assessment.reasons},
            )
        )

        return assessment

    def get_init_summary(self) -> Dict[str, Any]:
        """Gathers deterministic summary data for the onboarding CLI."""
        profile = self.discover()
        graph_stats = self.build_graph()
        active_adapters = self.adapter_registry.detect_active_adapters(self.workspace_root)

        return {
            "project_name": profile.project_name,
            "root_path": profile.root_path,
            "languages": [l.name for l in profile.languages],
            "frameworks": [f.name for f in profile.frameworks],
            "infrastructure": {
                "has_docker": profile.infrastructure.has_docker,
                "dockerfiles": len(profile.infrastructure.dockerfiles),
                "has_compose": profile.infrastructure.has_compose,
                "compose_files": len(profile.infrastructure.compose_files),
                "databases": profile.infrastructure.detected_databases,
                "queues": profile.infrastructure.detected_queues,
                "ci_providers": profile.infrastructure.ci_providers,
            },
            "test_systems": [ts.framework for ts in profile.test_suites],
            "total_estimated_tests": sum(ts.test_count_estimate for ts in profile.test_suites),
            "discovered_test_files": sum(len(ts.test_files) for ts in profile.test_suites),
            "api_surface": {
                "rest_endpoints": len(profile.interfaces.rest_endpoints),
                "has_openapi": profile.interfaces.has_openapi,
                "has_graphql": profile.interfaces.has_graphql,
                "has_grpc": profile.interfaces.has_grpc,
            },
            "architecture": {
                "symbols_indexed": graph_stats.total_nodes,
                "dependency_edges": graph_stats.total_edges,
                "indexed_files": graph_stats.file_count,
            },
            "capabilities_count": len(profile.capabilities),
            "active_adapters": [a.name for a in active_adapters],
        }

    def list_capabilities(self) -> List[Any]:
        """Returns all resolved capabilities for the workspace."""
        profile = self.discover()
        return profile.capabilities

    def list_adapters(self) -> List[Dict[str, Any]]:
        """Returns all registered adapters with active status."""
        active_ids = {a.adapter_id for a in self.adapter_registry.detect_active_adapters(self.workspace_root)}
        results = []
        for adapter in self.adapter_registry.list_adapters():
            results.append({
                "adapter_id": adapter.adapter_id,
                "name": adapter.name,
                "category": adapter.category,
                "version": adapter.version,
                "active": adapter.adapter_id in active_ids,
            })
        return results

    def check(
        self,
        changed_only: bool = True,
        dry_run: bool = False,
        ci: bool = False,
    ) -> Dict[str, Any]:
        """
        Orchestrates full unified verification workflow:
        DISCOVER -> IMPACT -> RISK -> PLAN -> VALIDATE -> QUALITY -> EVIDENCE -> RELEASE DECISION
        """
        profile = self.discover()
        impact = self.analyze_impact()
        risk = self.assess_risk(impact)
        plan = self.planner.plan_tests(
            impact=impact,
            risk=risk,
            available_suites=profile.test_suites,
            changed_only=changed_only,
            history_store=self.history_store,
            explain=True,
        )
        report = self.execute_plan(test_plan=plan, dry_run=dry_run, fail_fast=True)
        quality_results = self.execute_quality(dimension="all", dry_run=dry_run)
        release_assessment = self.assess_release_readiness(report, quality_results=quality_results)

        return {
            "project_name": profile.project_name,
            "tree_hash": profile.tree_hash,
            "risk_level": risk.level.value,
            "total_planned_tests": plan.total_planned,
            "tests_executed": report.total_tests,
            "tests_passed": report.passed,
            "tests_failed": report.failed,
            "quality_dimensions_evaluated": list(quality_results.keys()),
            "release_verdict": release_assessment.verdict.value,
            "policy_checks": [c.model_dump() for c in release_assessment.policy_checks],
            "reasons": release_assessment.reasons,
        }

