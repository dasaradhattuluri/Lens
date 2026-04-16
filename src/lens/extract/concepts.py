"""Concept-mapping extraction pass.

Extracts semantic / domain-level relationship triples from documentation
and source-file docstrings.  In production this delegates to Azure OpenAI
GPT-4o via the internal gateway; for local / offline use an in-process
heuristic extractor is provided as a fallback.
"""

from __future__ import annotations

import re
from typing import Protocol

from lens.models import (
    CorpusFile,
    EdgeRelation,
    KGEdge,
    KGNode,
    NodeKind,
    Provenance,
)


# ---------------------------------------------------------------------------
# Result container (same shape as syntax pass for composability)
# ---------------------------------------------------------------------------

class ConceptExtractionResult:
    def __init__(self) -> None:
        self.nodes: list[KGNode] = []
        self.edges: list[KGEdge] = []

    def add_node(self, node: KGNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: KGEdge) -> None:
        self.edges.append(edge)


# ---------------------------------------------------------------------------
# Extractor protocol
# ---------------------------------------------------------------------------

class ConceptExtractor(Protocol):
    """Interface for concept-extraction backends."""

    def extract(self, corpus_file: CorpusFile) -> ConceptExtractionResult: ...


# ---------------------------------------------------------------------------
# Heuristic concept extractor (offline / no-LLM fallback)
# ---------------------------------------------------------------------------

# Matches Markdown headings and the paragraph that follows them
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Matches inline references like `module_name` or **ClassName**
_REF_RE = re.compile(r"`(\w[\w.]+)`|\*\*(\w[\w.]+)\*\*")


class HeuristicConceptExtractor:
    """Derives concept nodes and cross-reference edges from Markdown docs
    and Python docstrings without requiring an LLM."""

    _DOC_LANGUAGES = frozenset({"markdown", "rst", "text"})

    def extract(self, corpus_file: CorpusFile) -> ConceptExtractionResult:
        result = ConceptExtractionResult()

        if corpus_file.language in self._DOC_LANGUAGES:
            self._extract_from_doc(corpus_file, result)
        elif corpus_file.language == "python":
            self._extract_from_docstrings(corpus_file, result)

        return result

    # -- Markdown / text docs -----------------------------------------------

    def _extract_from_doc(
        self, cf: CorpusFile, result: ConceptExtractionResult
    ) -> None:
        doc_node = KGNode(
            label=cf.path,
            kind=NodeKind.DOCUMENT,
            provenance=_prov(cf),
        )
        result.add_node(doc_node)

        lines = cf.content.splitlines()
        for idx, line in enumerate(lines, start=1):
            hm = _HEADING_RE.match(line)
            if hm:
                heading_text = hm.group(2).strip()
                concept = KGNode(
                    label=heading_text,
                    kind=NodeKind.CONCEPT,
                    provenance=Provenance(
                        source_file=cf.path,
                        line_range=(idx, idx),
                        extraction_pass="concepts",
                    ),
                )
                result.add_node(concept)
                result.add_edge(KGEdge(
                    source_id=doc_node.uid,
                    target_id=concept.uid,
                    relation=EdgeRelation.CONTAINS,
                    provenance=concept.provenance,
                ))

            # Inline references → DESCRIBES edges from doc to referenced entity
            for rm in _REF_RE.finditer(line):
                ref_label = rm.group(1) or rm.group(2)
                ref_node = KGNode(
                    label=ref_label,
                    kind=NodeKind.CONCEPT,
                    provenance=Provenance(
                        source_file=cf.path,
                        line_range=(idx, idx),
                        extraction_pass="concepts",
                    ),
                )
                result.add_node(ref_node)
                result.add_edge(KGEdge(
                    source_id=doc_node.uid,
                    target_id=ref_node.uid,
                    relation=EdgeRelation.DESCRIBES,
                    provenance=ref_node.provenance,
                ))

    # -- Python docstrings --------------------------------------------------

    def _extract_from_docstrings(
        self, cf: CorpusFile, result: ConceptExtractionResult
    ) -> None:
        import ast as _ast

        try:
            tree = _ast.parse(cf.content, filename=cf.path)
        except SyntaxError:
            return

        for node in _ast.walk(tree):
            docstring: str | None = None
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef, _ast.Module)):
                docstring = _ast.get_docstring(node)
            if not docstring:
                continue

            owner_label = getattr(node, "name", cf.path)
            line_no = getattr(node, "lineno", 1)
            prov = Provenance(
                source_file=cf.path,
                line_range=(line_no, line_no),
                extraction_pass="concepts",
            )
            concept = KGNode(
                label=f"{owner_label} (docstring)",
                kind=NodeKind.CONCEPT,
                provenance=prov,
                properties={"summary": docstring[:200]},
            )
            result.add_node(concept)

            # Cross-references inside docstring
            for rm in _REF_RE.finditer(docstring):
                ref_label = rm.group(1) or rm.group(2)
                ref_node = KGNode(
                    label=ref_label,
                    kind=NodeKind.CONCEPT,
                    provenance=prov,
                )
                result.add_node(ref_node)
                result.add_edge(KGEdge(
                    source_id=concept.uid,
                    target_id=ref_node.uid,
                    relation=EdgeRelation.RELATED_TO,
                    provenance=prov,
                ))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_concepts(
    files: list[CorpusFile],
    extractor: ConceptExtractor | None = None,
) -> ConceptExtractionResult:
    """Run concept-mapping pass over *files* and return merged results."""
    if extractor is None:
        extractor = HeuristicConceptExtractor()

    merged = ConceptExtractionResult()
    for cf in files:
        partial = extractor.extract(cf)
        merged.nodes.extend(partial.nodes)
        merged.edges.extend(partial.edges)
    return merged


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prov(cf: CorpusFile) -> Provenance:
    return Provenance(
        source_file=cf.path,
        extraction_pass="concepts",
    )
