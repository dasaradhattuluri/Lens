"""Unit tests for lens.query (REST API)."""

from fastapi.testclient import TestClient

from lens.graph import KnowledgeGraph
from lens.models import EdgeRelation, KGEdge, KGNode, NodeKind, Provenance
from lens.query import create_app

_PROV = Provenance(source_file="api_test.py", extraction_pass="syntax")


def _build_app() -> TestClient:
    kg = KnowledgeGraph()
    kg.add_node(KGNode(label="Svc", kind=NodeKind.MODULE, provenance=_PROV, uid="n1"))
    kg.add_node(KGNode(label="Handler", kind=NodeKind.CLASS, provenance=_PROV, uid="n2"))
    kg.add_node(KGNode(label="process", kind=NodeKind.FUNCTION, provenance=_PROV, uid="n3"))
    kg.add_edge(KGEdge(source_id="n1", target_id="n2", relation=EdgeRelation.CONTAINS, provenance=_PROV, uid="e1"))
    kg.add_edge(KGEdge(source_id="n2", target_id="n3", relation=EdgeRelation.CALLS, provenance=_PROV, uid="e2"))
    kg.detect_clusters(algorithm="greedy")
    return TestClient(create_app(kg))


class TestHealthz:
    def test_ok(self):
        client = _build_app()
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestListNodes:
    def test_all(self):
        client = _build_app()
        r = client.get("/nodes")
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_filter_by_label(self):
        client = _build_app()
        r = client.get("/nodes", params={"label": "Svc"})
        data = r.json()
        assert len(data) == 1
        assert data[0]["label"] == "Svc"

    def test_filter_by_kind(self):
        client = _build_app()
        r = client.get("/nodes", params={"kind": "function"})
        data = r.json()
        assert len(data) == 1
        assert data[0]["label"] == "process"


class TestNeighbors:
    def test_depth_1(self):
        client = _build_app()
        r = client.get("/neighbors", params={"node_id": "n1", "depth": 1})
        assert r.status_code == 200
        data = r.json()
        labels = {n["label"] for n in data["neighbors"]}
        assert "Handler" in labels

    def test_not_found(self):
        client = _build_app()
        r = client.get("/neighbors", params={"node_id": "bogus"})
        assert r.status_code == 404


class TestPath:
    def test_exists(self):
        client = _build_app()
        r = client.get("/path", params={"source": "n1", "target": "n3"})
        assert r.status_code == 200
        assert r.json()["path"] is not None
        assert len(r.json()["path"]) == 3

    def test_not_found(self):
        client = _build_app()
        r = client.get("/path", params={"source": "nope", "target": "n1"})
        assert r.status_code == 404


class TestSubgraph:
    def test_returns_subgraph(self):
        client = _build_app()
        r = client.get("/subgraph", params={"node_ids": "n1,n2"})
        assert r.status_code == 200
        data = r.json()
        assert len(data["@graph"]) == 2


class TestClusters:
    def test_lists_clusters(self):
        client = _build_app()
        r = client.get("/clusters")
        assert r.status_code == 200
        assert len(r.json()) >= 1
