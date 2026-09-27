from pathlib import Path
from aegis.graph.store import SQLiteGraphStore
from aegis.graph.project_graph import ProjectGraph
from aegis.graph.models import GraphNode, GraphEdge
from aegis.indexer.base import SymbolType, RelationType, ConfidenceLevel, Provenance


def test_sqlite_graph_store(tmp_path: Path):
    db_path = tmp_path / "test_graph.db"
    store = SQLiteGraphStore(db_path)

    # Add nodes
    n1 = GraphNode(id="py:A", name="A", symbol_type=SymbolType.FUNCTION, language="python", file_path="a.py")
    n2 = GraphNode(id="py:B", name="B", symbol_type=SymbolType.FUNCTION, language="python", file_path="b.py")
    n3 = GraphNode(id="api:GET:/users", name="GET /users", symbol_type=SymbolType.ROUTE, language="http", file_path="api.py")
    store.upsert_nodes([n1, n2, n3])

    assert store.get_node("py:A") is not None
    assert len(store.get_nodes_by_file("a.py")) == 1

    # Add edges: A -> calls -> B, A -> exposes_api -> GET /users
    e1 = GraphEdge(
        source_id="py:A",
        relation=RelationType.CALLS,
        target_id="py:B",
        confidence=ConfidenceLevel.DIRECT,
        provenance=Provenance(file_path="a.py"),
    )
    e2 = GraphEdge(
        source_id="py:A",
        relation=RelationType.EXPOSES_API,
        target_id="api:GET:/users",
        confidence=ConfidenceLevel.HIGH_CONFIDENCE,
        provenance=Provenance(file_path="a.py"),
    )
    store.add_edges([e1, e2])

    stats = store.get_stats()
    assert stats.total_nodes == 3
    assert stats.total_edges == 2


def test_graph_downstream_traversal(tmp_path: Path):
    graph = ProjectGraph(workspace_root=tmp_path)
    # Graph: Repo -> Service -> API Route -> Test
    n_repo = GraphNode(id="py:Repo", name="Repo", symbol_type=SymbolType.CLASS, language="python", file_path="repo.py")
    n_svc = GraphNode(id="py:Service", name="Service", symbol_type=SymbolType.CLASS, language="python", file_path="svc.py")
    n_api = GraphNode(id="api:POST:/login", name="POST /login", symbol_type=SymbolType.ROUTE, language="http", file_path="api.py")
    n_test = GraphNode(id="py:TestLogin", name="TestLogin", symbol_type=SymbolType.TEST, language="python", file_path="test_api.py")

    graph.store.upsert_nodes([n_repo, n_svc, n_api, n_test])

    graph.store.add_edges([
        GraphEdge(
            source_id="py:Service",
            relation=RelationType.CALLS,
            target_id="py:Repo",
            provenance=Provenance(file_path="svc.py"),
        ),
        GraphEdge(
            source_id="py:Service",
            relation=RelationType.EXPOSES_API,
            target_id="api:POST:/login",
            provenance=Provenance(file_path="api.py"),
        ),
        GraphEdge(
            source_id="py:TestLogin",
            relation=RelationType.TESTS,
            target_id="api:POST:/login",
            provenance=Provenance(file_path="test_api.py"),
        ),
    ])

    # Downstream impact of Repo change
    impact_path = graph.get_affected_downstream(["py:Repo"], max_depth=5)
    node_ids = [n.id for n in impact_path.nodes]

    assert "py:Service" in node_ids
    assert "api:POST:/login" in node_ids
    assert "py:TestLogin" in node_ids

    # Query helper methods
    affected_apis = graph.get_affected_apis(["py:Repo"])
    assert len(affected_apis) >= 1
    assert affected_apis[0].id == "api:POST:/login"

    affected_tests = graph.get_affected_tests(["py:Repo"])
    assert len(affected_tests) >= 1
    assert affected_tests[0].id == "py:TestLogin"
