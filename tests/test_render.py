"""Unit tests for lens.render."""

from pathlib import Path

from lens.graph import KnowledgeGraph
from lens.models import EdgeRelation, KGEdge, KGNode, NodeKind, Provenance
from lens.render import render_analysis_report, render_explorer_html

_PROV = Provenance(source_file="demo.py", extraction_pass="syntax")


def _sample_graph() -> KnowledgeGraph:
    kg = KnowledgeGraph()
    a = KGNode(label="Alpha", kind=NodeKind.MODULE, provenance=_PROV, uid="a1")
    b = KGNode(label="Beta", kind=NodeKind.FUNCTION, provenance=_PROV, uid="b1")
    kg.add_node(a)
    kg.add_node(b)
    kg.add_edge(KGEdge(
        source_id="a1", target_id="b1",
        relation=EdgeRelation.CONTAINS, provenance=_PROV, uid="e1",
    ))
    kg.detect_clusters(algorithm="greedy")
    return kg


class TestExplorerHtml:
    def test_generates_html_file(self, tmp_path: Path):
        kg = _sample_graph()
        dest = tmp_path / "explorer.html"
        render_explorer_html(kg, dest)
        assert dest.exists()
        content = dest.read_text()
        assert "<!DOCTYPE html>" in content
        assert "Lens Explorer" in content
        assert "Alpha" in content

    def test_no_external_cdn(self, tmp_path: Path):
        kg = _sample_graph()
        dest = tmp_path / "explorer.html"
        render_explorer_html(kg, dest)
        content = dest.read_text()
        # Must not reference external CDNs
        assert "cdn." not in content.lower()
        assert "unpkg" not in content.lower()


class TestAnalysisReport:
    def test_generates_markdown(self, tmp_path: Path):
        kg = _sample_graph()
        dest = tmp_path / "analysis-report.md"
        render_analysis_report(kg, dest)
        assert dest.exists()
        content = dest.read_text()
        assert "# Lens Analysis Report" in content
        assert "Corpus Summary" in content
        assert "Clusters" in content
        assert "Key Entities" in content
        assert "Integrity Audit" in content
        assert "High-Connectivity Nodes" in content

    def test_correct_node_count(self, tmp_path: Path):
        kg = _sample_graph()
        dest = tmp_path / "report.md"
        render_analysis_report(kg, dest)
        content = dest.read_text()
        assert "| Nodes | 2 |" in content
