"""
Aegis Intelligent DAG Scheduler
Orchestrates parallel and dependency-ordered test execution with fast-fail cascading,
execution caching, controlled retries, and flakiness tracking.
"""

from __future__ import annotations
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

from aegis.evidence.collector import EvidenceCollector
from aegis.evidence.models import TestResult, TestStatus
from aegis.execution.models import ExecutionDAG, DAGNode, DAGNodeStatus, FailureClassification
from aegis.runners.base import (
    TestRunner,
    RunnerCategory,
    ExecutionContext,
    RunnerPlan,
)
from aegis.runners.registry import RunnerRegistry
from aegis.storage.base import StorageBackend


class DAGScheduler:
    """Executes DAG stages according to dependency constraints, fast-fail policies, and caches."""

    CACHE_FILE = "cache/execution_cache.json"
    HISTORY_FILE = "cache/flakiness_history.json"

    def __init__(
        self,
        registry: RunnerRegistry,
        storage: Optional[StorageBackend] = None,
        max_workers: int = 4,
    ) -> None:
        self.registry = registry
        self.storage = storage
        self.max_workers = max(1, max_workers)

    def execute_dag(
        self,
        dag: ExecutionDAG,
        context: ExecutionContext,
        collector: EvidenceCollector,
        tree_hash: str = "",
        fail_fast: bool = True,
        parallel: bool = True,
    ) -> List[TestResult]:
        """
        Executes the DAG to completion.
        Returns all accumulated TestResults across all executed stages.
        """
        all_results: List[TestResult] = []
        cache_data: Dict[str, Any] = {}
        if self.storage and not context.dry_run:
            cache_data = self.storage.load_json(self.CACHE_FILE) or {}

        # Loop until all nodes are in a terminal state
        while not dag.is_complete():
            ready_nodes = dag.get_ready_nodes()
            if not ready_nodes:
                # Check for remaining pending nodes that are unresolvable (e.g. cycles or blocked)
                for node in dag.nodes.values():
                    if node.status == DAGNodeStatus.PENDING:
                        node.status = DAGNodeStatus.BLOCKED
                        node.block_reason = "Unmet upstream dependencies"
                break

            # Execute ready nodes (either in parallel or serially)
            if parallel and len(ready_nodes) > 1 and not context.dry_run:
                with ThreadPoolExecutor(max_workers=min(self.max_workers, len(ready_nodes))) as executor:
                    futures = {
                        executor.submit(self._execute_single_node, node, context, tree_hash, cache_data): node
                        for node in ready_nodes
                    }
                    for future in as_completed(futures):
                        node = futures[future]
                        results = future.result()
                        self._process_node_completion(node, results, dag, collector, all_results, fail_fast)
            else:
                for node in ready_nodes:
                    results = self._execute_single_node(node, context, tree_hash, cache_data)
                    self._process_node_completion(node, results, dag, collector, all_results, fail_fast)

        # Save cache state
        if self.storage and not context.dry_run:
            self.storage.save_json(self.CACHE_FILE, cache_data)

        return all_results

    def _execute_single_node(
        self,
        node: DAGNode,
        context: ExecutionContext,
        tree_hash: str,
        cache_data: Dict[str, Any],
    ) -> List[TestResult]:
        """Executes a single DAG node with caching and retry logic."""
        node.status = DAGNodeStatus.RUNNING
        node.start_time = time.perf_counter()

        # 1. Check Execution Cache
        cache_key = f"{node.node_id}::{tree_hash}"
        if cache_key in cache_data and not context.dry_run:
            cached_entries = cache_data[cache_key]
            results = [TestResult(**entry) for entry in cached_entries]
            node.end_time = time.perf_counter()
            return results

        # 2. Find Runner
        node_context = context.model_copy(update={"category": node.category, "target_files": node.target_files})
        runner = self.registry.get_runner(node.runner_name) or self.registry.find_best_runner(node_context)

        if not runner:
            node.end_time = time.perf_counter()
            return [
                TestResult(
                    test_id=f"{node.test_id}.unavailable",
                    name=f"{node.name} (Runner Unavailable)",
                    category=node.category.value,
                    status=TestStatus.NOT_IMPLEMENTED,
                    duration_ms=0.0,
                    runner=node.runner_name,
                    raw_stderr=f"No runner registered for {node.runner_name} / {node.category.value}",
                )
            ]

        # 3. Plan & Execute with Retries
        plan = runner.plan(node_context)
        attempts = 0
        max_attempts = node.retry_policy.max_attempts if not context.dry_run else 1
        results: List[TestResult] = []

        while attempts < max_attempts:
            attempts += 1
            results = runner.execute(plan, node_context)
            has_failure = any(r.status in (TestStatus.FAILED, TestStatus.ERROR, TestStatus.TIMEOUT) for r in results)

            if not has_failure:
                break

            # Classify failure
            classification = self._classify_failure(results)
            node.failure_classification = classification

            if classification == FailureClassification.DETERMINISTIC_FAILURE and not node.retry_policy.retry_deterministic:
                break  # Don't waste retries on deterministic failures

        node.end_time = time.perf_counter()

        # Update cache data if passing
        if not context.dry_run and all(r.status == TestStatus.PASSED for r in results):
            cache_data[cache_key] = [r.model_dump() for r in results]

        return results

    def _process_node_completion(
        self,
        node: DAGNode,
        results: List[TestResult],
        dag: ExecutionDAG,
        collector: EvidenceCollector,
        all_results: List[TestResult],
        fail_fast: bool,
    ) -> None:
        """Processes node outcome, records evidence, and cascades fast-fail blocks."""
        node.results = results
        all_results.extend(results)

        # Record to evidence collector
        for res in results:
            collector.record_result(res)

        has_failed = any(r.status in (TestStatus.FAILED, TestStatus.ERROR, TestStatus.TIMEOUT) for r in results)

        if has_failed:
            node.status = DAGNodeStatus.FAILED
            if fail_fast:
                # Cascade blocks to all downstream dependent nodes
                self._cascade_block(node.node_id, dag, reason=f"Blocked by upstream failure in {node.name}")
        else:
            node.status = DAGNodeStatus.PASSED

    def _cascade_block(self, failed_node_id: str, dag: ExecutionDAG, reason: str) -> None:
        """Recursively marks all nodes that depend directly or indirectly on failed_node_id as BLOCKED."""
        to_block: Set[str] = set()
        queue = [failed_node_id]

        while queue:
            parent_id = queue.pop(0)
            for child in dag.nodes.values():
                if child.status == DAGNodeStatus.PENDING and parent_id in child.dependencies:
                    if child.node_id not in to_block:
                        to_block.add(child.node_id)
                        queue.append(child.node_id)

        for nid in to_block:
            node = dag.nodes[nid]
            node.status = DAGNodeStatus.BLOCKED
            node.block_reason = reason

    def _classify_failure(self, results: List[TestResult]) -> FailureClassification:
        """Categorizes failure for retry decision."""
        for r in results:
            if r.status == TestStatus.TIMEOUT:
                return FailureClassification.TIMEOUT_FAILURE
            if r.raw_stderr:
                err = r.raw_stderr.lower()
                if "connection refused" in err or "econnrefused" in err or "port in use" in err:
                    return FailureClassification.INFRASTRUCTURE_FAILURE
                if "assertionerror" in err or "expected" in err:
                    return FailureClassification.DETERMINISTIC_FAILURE
        return FailureClassification.UNKNOWN
