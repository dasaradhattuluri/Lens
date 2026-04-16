"""Unit tests for lens.models."""

from lens.models import (
    CorpusFile,
    EdgeRelation,
    KGCluster,
    KGEdge,
    KGNode,
    NodeKind,
    Provenance,
)


class TestProvenance:
    def test_defaults(self):
        p = Provenance(source_file="a.py")
        assert p.source_file == "a.py"
        assert p.line_range is None
        assert p.extraction_pass == "unknown"
        assert p.model_version is None

    def test_with_line_range(self):
        p = Provenance(source_file="b.py", line_range=(10, 20))
        assert p.line_range == (10, 20)


class TestKGNode:
    def test_uid_generated(self):
        n = KGNode(label="foo", kind=NodeKind.FUNCTION, provenance=Provenance(source_file="x.py"))
        assert n.uid  # non-empty
        assert n.label == "foo"

    def test_unique_uids(self):
        prov = Provenance(source_file="x.py")
        n1 = KGNode(label="a", kind=NodeKind.CLASS, provenance=prov)
        n2 = KGNode(label="a", kind=NodeKind.CLASS, provenance=prov)
        assert n1.uid != n2.uid


class TestKGEdge:
    def test_defaults(self):
        e = KGEdge(
            source_id="s", target_id="t",
            relation=EdgeRelation.CALLS,
            provenance=Provenance(source_file="z.py"),
        )
        assert e.weight == 1.0
        assert e.relation == EdgeRelation.CALLS


class TestCorpusFile:
    def test_creation(self):
        cf = CorpusFile(path="foo/bar.py", content="x = 1", language="python")
        assert cf.language == "python"
