"""
Aegis Execution DAG & Scheduler Data Models
Defines execution DAG nodes, dependency edges, node lifecycle states,
failure classifications, and execution cache schemas.
"""

from __future__ import annotations
import time
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field

from aegis.evidence.models import TestResult, TestStatus
from aegis.runners.base import RunnerCategory, FailureClassification


class DAGNodeStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RetryPolicy(BaseModel):
    max_attempts: int = 2
    retry_transient: bool = True
    retry_deterministic: bool = False


class DAGNode(BaseModel):
    """An executable node in the test execution directed acyclic graph."""
    node_id: str                             # E.g. "dag.sanity.preflight", "dag.unit.pytest"
    runner_name: str
    category: RunnerCategory
    test_id: str
    name: str
    priority: int = 50
    dependencies: List[str] = Field(default_factory=list)  # parent node_ids required to pass first
    target_files: List[str] = Field(default_factory=list)
    timeout_seconds: int = 120
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    status: DAGNodeStatus = DAGNodeStatus.PENDING
    results: List[TestResult] = Field(default_factory=list)
    failure_classification: Optional[FailureClassification] = None
    block_reason: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class ExecutionDAG(BaseModel):
    """Complete directed acyclic graph of test execution stages."""
    dag_id: str
    created_at: float = Field(default_factory=time.time)
    nodes: Dict[str, DAGNode] = Field(default_factory=dict)

    def get_ready_nodes(self) -> List[DAGNode]:
        """Returns nodes whose dependencies have all PASSED and are currently PENDING."""
        ready: List[DAGNode] = []
        for node in self.nodes.values():
            if node.status != DAGNodeStatus.PENDING:
                continue
            deps_met = True
            for dep_id in node.dependencies:
                dep_node = self.nodes.get(dep_id)
                if not dep_node or dep_node.status != DAGNodeStatus.PASSED:
                    deps_met = False
                    break
            if deps_met:
                ready.append(node)
        return ready

    def is_complete(self) -> bool:
        """Returns True when all nodes have reached a terminal status."""
        terminal_statuses = {
            DAGNodeStatus.PASSED,
            DAGNodeStatus.FAILED,
            DAGNodeStatus.BLOCKED,
            DAGNodeStatus.SKIPPED,
            DAGNodeStatus.CANCELLED,
            DAGNodeStatus.NOT_APPLICABLE,
        }
        return all(node.status in terminal_statuses for node in self.nodes.values())
