"""Unit tests for lens.graph."""

import json
from pathlib import Path

from lens.graph import KnowledgeGraph
from lens.models import (
    EdgeRelation,
    KGEdge,
    KGNode,
    NodeKind,
    Provenance,
)

_PROV = Provenance(source_file="test.py", extraction_pass="syntax")


def _make_graph() -> KnowledgeGraph:
    """Build a small test graph: A -> B -> C, A -> C."""
    kg = KnowledgeGraph()
    a = KGNode(label="A", kind=NodeKind.MODULE, provenance=_PROV, uid="a")
    b = KGNode(label="B", kind=NodeKind.CLASS, provenance=_PROV, uid="b")
    c = KGNode(label="C", kind=NodeKind.FUNCTION, provenance=_PROV, uid="c")
    kg.add_node(a)
    kg.add_node(b)
    kg.add_node(c)
    kg.add_edge(KGEdge(source_id="a", target_id="b", relation=EdgeRelation.CONTAINS, provenance=_PROV, uid="e1"))
    kg.add_edge(KGEdge(source_id="b", target_id="c", relation=EdgeRelation.CALLS, provenance=_PROV, uid="e2"))
    kg.add_edge(KGEdge(source_id="a", target_id="c", relation=EdgeRelation.IMPORTS, provenance=_PROV, uid="e3"))
    return kg


class TestKnowledgeGraph:
    def test_add_and_find(self):
        kg = _make_graph()
        assert len(kg.nodes) == 3
        assert len(kg.edges) == 3
        matches = kg.find_by_label("B")
        assert len(matches) == 1
        assert matches[0].kind == NodeKind.CLASS

    def test_neighbors_depth_1(self):
        kg = _make_graph()
        nbrs = kg.neighbors("a", depth=1)
        assert "b" in nbrs
        assert "c" in nbrs

    def test_neighbors_depth_2(self):
        kg = _make_graph()
        nbrs = kg.neighbors("a", depth=2)
        assert "b" in nbrs
        assert "c" in nbrs

    def test_subgraph(self):
        kg = _make_graph()
        sg = kg.subgraph(["a", "b"])
        assert len(sg.nodes) == 2
        assert len(sg.edges) == 1  # only a->b

    def test_detect_clusters(self):
        kg = _make_graph()
        kg.detect_clusters(algorithm="greedy")
        assert len(kg.clusters) >= 1
        # Every node should have a cluster_id
        for n in kg.nodes.values():
            assert n.cluster_id is not None


class TestSerialization:
    def test_jsonld_round_trip(self, tmp_path: Path):
        kg = _make_graph()
        kg.detect_clusters(algorithm="greedy")
        out = tmp_path / "knowledge-graph.jsonld"
        kg.save_jsonld(out, corpus_root="/repo")
        data = json.loads(out.read_text())
        assert data["@context"] == "https://schema.lens.microsoft.internal/kg/v1"
        assert len(data["@graph"]) == 3
        assert len(data["lens:edges"]) == 3
        assert data["lens:meta"]["lens:nodeCount"] == 3

    def test_graphml_output(self, tmp_path: Path):
        kg = _make_graph()
        out = tmp_path / "knowledge-graph.graphml"
        kg.save_graphml(out)
        content = out.read_text()
        assert "<graphml" in content
        assert 'id="a"' in content
