"""Unit tests for lens.extract.concepts."""

from lens.extract.concepts import (
    HeuristicConceptExtractor,
    extract_concepts,
)
from lens.models import CorpusFile, NodeKind, EdgeRelation


SAMPLE_MD = """\
# Architecture

The system uses `ServiceBus` for messaging.

## Data Layer

**CosmosClient** handles persistence.
"""

SAMPLE_PY_WITH_DOCSTRINGS = '''\
"""Module-level docstring about `DataProcessor`."""

class Transformer:
    """Transforms input using `Pipeline`."""
    def run(self):
        """Execute the transformer via `Engine`."""
        pass
'''


class TestHeuristicConceptExtractor:
    def test_extracts_headings_as_concepts(self):
        cf = CorpusFile(path="arch.md", content=SAMPLE_MD, language="markdown")
        ext = HeuristicConceptExtractor()
        result = ext.extract(cf)
        labels = {n.label for n in result.nodes if n.kind == NodeKind.CONCEPT}
        assert "Architecture" in labels
        assert "Data Layer" in labels

    def test_extracts_inline_references(self):
        cf = CorpusFile(path="arch.md", content=SAMPLE_MD, language="markdown")
        ext = HeuristicConceptExtractor()
        result = ext.extract(cf)
        labels = {n.label for n in result.nodes}
        assert "ServiceBus" in labels
        assert "CosmosClient" in labels

    def test_describes_edges(self):
        cf = CorpusFile(path="arch.md", content=SAMPLE_MD, language="markdown")
        ext = HeuristicConceptExtractor()
        result = ext.extract(cf)
        desc_edges = [e for e in result.edges if e.relation == EdgeRelation.DESCRIBES]
        assert len(desc_edges) >= 2

    def test_python_docstrings(self):
        cf = CorpusFile(path="transform.py", content=SAMPLE_PY_WITH_DOCSTRINGS, language="python")
        ext = HeuristicConceptExtractor()
        result = ext.extract(cf)
        labels = {n.label for n in result.nodes}
        # Should pick up cross-references inside docstrings
        assert any("Pipeline" in lbl for lbl in labels)

    def test_ignores_non_doc_languages(self):
        cf = CorpusFile(path="style.css", content="body { color: red; }", language="css")
        ext = HeuristicConceptExtractor()
        result = ext.extract(cf)
        assert result.nodes == []


class TestExtractConcepts:
    def test_merged(self):
        files = [
            CorpusFile(path="a.md", content="# Intro\n\nHello.", language="markdown"),
            CorpusFile(path="b.md", content="# Summary\n\nWorld.", language="markdown"),
        ]
        result = extract_concepts(files)
        labels = {n.label for n in result.nodes if n.kind == NodeKind.CONCEPT}
        assert "Intro" in labels
        assert "Summary" in labels
