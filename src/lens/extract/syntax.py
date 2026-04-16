"""Syntax-aware extraction pass.

Uses Python's built-in `ast` module for Python files and a lightweight
regex-based fallback for other languages.  (Full Tree-sitter integration
is planned for Phase 2; the adapter interface is already in place so the
swap is non-breaking.)
"""

from __future__ import annotations

import ast
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
# Result container
# ---------------------------------------------------------------------------

class SyntaxExtractionResult:
    """Collects nodes and edges emitted by a single syntax-pass run."""

    def __init__(self) -> None:
        self.nodes: list[KGNode] = []
        self.edges: list[KGEdge] = []

    def add_node(self, node: KGNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: KGEdge) -> None:
        self.edges.append(edge)


# ---------------------------------------------------------------------------
# Language handler protocol
# ---------------------------------------------------------------------------

class LanguageHandler(Protocol):
    def can_handle(self, lang: str | None) -> bool: ...
    def extract(self, corpus_file: CorpusFile) -> SyntaxExtractionResult: ...


# ---------------------------------------------------------------------------
# Python handler (ast-based)
# ---------------------------------------------------------------------------

class PythonSyntaxHandler:
    """Extracts declarations, call edges, and imports from Python files."""

    def can_handle(self, lang: str | None) -> bool:
        return lang == "python"

    def extract(self, corpus_file: CorpusFile) -> SyntaxExtractionResult:
        result = SyntaxExtractionResult()
        try:
            tree = ast.parse(corpus_file.content, filename=corpus_file.path)
        except SyntaxError:
            return result

        file_prov = _prov(corpus_file, None)

        # Module-level node
        module_node = KGNode(
            label=corpus_file.path,
            kind=NodeKind.MODULE,
            provenance=file_prov,
        )
        result.add_node(module_node)

        # Walk AST
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cls_node = KGNode(
                    label=node.name,
                    kind=NodeKind.CLASS,
                    provenance=_prov(corpus_file, node),
                    properties={"bases": [_name_of(b) for b in node.bases]},
                )
                result.add_node(cls_node)
                result.add_edge(KGEdge(
                    source_id=module_node.uid,
                    target_id=cls_node.uid,
                    relation=EdgeRelation.CONTAINS,
                    provenance=_prov(corpus_file, node),
                ))
                # Inheritance edges
                for base in node.bases:
                    base_name = _name_of(base)
                    if base_name:
                        base_node = KGNode(
                            label=base_name,
                            kind=NodeKind.CLASS,
                            provenance=_prov(corpus_file, node),
                        )
                        result.add_node(base_node)
                        result.add_edge(KGEdge(
                            source_id=cls_node.uid,
                            target_id=base_node.uid,
                            relation=EdgeRelation.INHERITS,
                            provenance=_prov(corpus_file, node),
                        ))

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_node = KGNode(
                    label=node.name,
                    kind=NodeKind.FUNCTION,
                    provenance=_prov(corpus_file, node),
                )
                result.add_node(fn_node)
                result.add_edge(KGEdge(
                    source_id=module_node.uid,
                    target_id=fn_node.uid,
                    relation=EdgeRelation.CONTAINS,
                    provenance=_prov(corpus_file, node),
                ))

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imp_node = KGNode(
                        label=alias.name,
                        kind=NodeKind.MODULE,
                        provenance=_prov(corpus_file, node),
                    )
                    result.add_node(imp_node)
                    result.add_edge(KGEdge(
                        source_id=module_node.uid,
                        target_id=imp_node.uid,
                        relation=EdgeRelation.IMPORTS,
                        provenance=_prov(corpus_file, node),
                    ))

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imp_node = KGNode(
                        label=node.module,
                        kind=NodeKind.MODULE,
                        provenance=_prov(corpus_file, node),
                    )
                    result.add_node(imp_node)
                    result.add_edge(KGEdge(
                        source_id=module_node.uid,
                        target_id=imp_node.uid,
                        relation=EdgeRelation.IMPORTS,
                        provenance=_prov(corpus_file, node),
                    ))

        return result


# ---------------------------------------------------------------------------
# Generic fallback handler (regex-based)
# ---------------------------------------------------------------------------

_GENERIC_PATTERNS: dict[str, list[tuple[re.Pattern[str], NodeKind]]] = {
    "javascript": [
        (re.compile(r"(?:function|const|let|var)\s+(\w+)"), NodeKind.FUNCTION),
        (re.compile(r"class\s+(\w+)"), NodeKind.CLASS),
    ],
    "typescript": [
        (re.compile(r"(?:function|const|let|var|export)\s+(\w+)"), NodeKind.FUNCTION),
        (re.compile(r"class\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"interface\s+(\w+)"), NodeKind.CLASS),
    ],
    "java": [
        (re.compile(r"class\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"interface\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"(?:public|private|protected|static)?\s*\w+\s+(\w+)\s*\("), NodeKind.FUNCTION),
    ],
    "csharp": [
        (re.compile(r"class\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"interface\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"struct\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"enum\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"namespace\s+([\w.]+)"), NodeKind.MODULE),
        (re.compile(r"(?:public|private|internal|protected|static|async|virtual|override|abstract)\s+[\w<>\[\],\s]+\s+(\w+)\s*\("), NodeKind.FUNCTION),
    ],
    "go": [
        (re.compile(r"func\s+(\w+)"), NodeKind.FUNCTION),
        (re.compile(r"type\s+(\w+)\s+struct"), NodeKind.CLASS),
        (re.compile(r"type\s+(\w+)\s+interface"), NodeKind.CLASS),
    ],
    "c": [
        (re.compile(r"^\s*(?:static\s+|extern\s+|inline\s+)*(?:unsigned\s+|signed\s+|const\s+)*\w+[\s*]+(\w+)\s*\(", re.MULTILINE), NodeKind.FUNCTION),
        (re.compile(r"typedef\s+struct\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"struct\s+(\w+)\s*\{"), NodeKind.CLASS),
        (re.compile(r"enum\s+(\w+)"), NodeKind.CLASS),
    ],
    "cpp": [
        (re.compile(r"class\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"struct\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"enum\s+(?:class\s+)?(\w+)"), NodeKind.CLASS),
        (re.compile(r"namespace\s+(\w+)"), NodeKind.MODULE),
        (re.compile(r"template\s*<[^>]*>\s*class\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"^\s*(?:static\s+|virtual\s+|inline\s+|explicit\s+|constexpr\s+)*(?:unsigned\s+|const\s+)*\w+[\s*&]+(\w+)\s*\(", re.MULTILINE), NodeKind.FUNCTION),
    ],
    "rust": [
        (re.compile(r"fn\s+(\w+)"), NodeKind.FUNCTION),
        (re.compile(r"struct\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"enum\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"trait\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"impl(?:\s*<[^>]*>)?\s+(\w+)"), NodeKind.CLASS),
        (re.compile(r"mod\s+(\w+)"), NodeKind.MODULE),
        (re.compile(r"type\s+(\w+)"), NodeKind.CLASS),
    ],
}

# Import-like patterns per language — matches that produce IMPORTS edges
_IMPORT_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "c": [re.compile(r'#include\s*[<"]([^>"]+)[>"]')],
    "cpp": [re.compile(r'#include\s*[<"]([^>"]+)[>"]')],
    "csharp": [re.compile(r"using\s+([\w.]+)\s*;")],
    "rust": [re.compile(r"use\s+([\w:]+)")],
    "java": [re.compile(r"import\s+([\w.]+)\s*;")],
    "go": [re.compile(r'"([\w./]+)"')],
    "javascript": [
        re.compile(r"import\s+.*?from\s+['\"]([^'\"]+)['\"]"),
        re.compile(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    ],
    "typescript": [
        re.compile(r"import\s+.*?from\s+['\"]([^'\"]+)['\"]"),
        re.compile(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"),
    ],
}

_SUPPORTED_GENERIC = frozenset(_GENERIC_PATTERNS.keys())


class GenericSyntaxHandler:
    """Regex-based fallback for languages without a dedicated handler."""

    def can_handle(self, lang: str | None) -> bool:
        return lang in _SUPPORTED_GENERIC

    def extract(self, corpus_file: CorpusFile) -> SyntaxExtractionResult:
        result = SyntaxExtractionResult()
        patterns = _GENERIC_PATTERNS.get(corpus_file.language or "", [])
        if not patterns:
            return result

        file_prov = _prov(corpus_file, None)
        module_node = KGNode(
            label=corpus_file.path,
            kind=NodeKind.MODULE,
            provenance=file_prov,
        )
        result.add_node(module_node)

        seen_names: set[str] = set()
        for line_no, line in enumerate(corpus_file.content.splitlines(), start=1):
            for pattern, kind in patterns:
                m = pattern.search(line)
                if m:
                    name = m.group(1)
                    if name in seen_names:
                        continue
                    seen_names.add(name)
                    prov = Provenance(
                        source_file=corpus_file.path,
                        line_range=(line_no, line_no),
                        extraction_pass="syntax",
                    )
                    child = KGNode(label=name, kind=kind, provenance=prov)
                    result.add_node(child)
                    result.add_edge(KGEdge(
                        source_id=module_node.uid,
                        target_id=child.uid,
                        relation=EdgeRelation.CONTAINS,
                        provenance=prov,
                    ))

        # Import / include edges
        import_pats = _IMPORT_PATTERNS.get(corpus_file.language or "", [])
        seen_imports: set[str] = set()
        for line_no, line in enumerate(corpus_file.content.splitlines(), start=1):
            for pat in import_pats:
                for m in pat.finditer(line):
                    imp_label = m.group(1)
                    if imp_label in seen_imports:
                        continue
                    seen_imports.add(imp_label)
                    prov = Provenance(
                        source_file=corpus_file.path,
                        line_range=(line_no, line_no),
                        extraction_pass="syntax",
                    )
                    imp_node = KGNode(
                        label=imp_label,
                        kind=NodeKind.MODULE,
                        provenance=prov,
                    )
                    result.add_node(imp_node)
                    result.add_edge(KGEdge(
                        source_id=module_node.uid,
                        target_id=imp_node.uid,
                        relation=EdgeRelation.IMPORTS,
                        provenance=prov,
                    ))

        return result


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

class SyntaxHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: list[LanguageHandler] = []

    def register(self, handler: LanguageHandler) -> None:
        self._handlers.append(handler)

    def find(self, lang: str | None) -> LanguageHandler | None:
        for h in self._handlers:
            if h.can_handle(lang):
                return h
        return None

    @classmethod
    def with_defaults(cls) -> "SyntaxHandlerRegistry":
        reg = cls()
        reg.register(PythonSyntaxHandler())
        reg.register(GenericSyntaxHandler())
        return reg


# ---------------------------------------------------------------------------
# Public API — run syntax extraction over a corpus
# ---------------------------------------------------------------------------

def extract_syntax(
    files: list[CorpusFile],
    registry: SyntaxHandlerRegistry | None = None,
) -> SyntaxExtractionResult:
    """Run the syntax-aware pass across all *files* and return merged results."""
    if registry is None:
        registry = SyntaxHandlerRegistry.with_defaults()

    merged = SyntaxExtractionResult()
    for cf in files:
        handler = registry.find(cf.language)
        if handler is None:
            continue
        partial = handler.extract(cf)
        merged.nodes.extend(partial.nodes)
        merged.edges.extend(partial.edges)
    return merged


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prov(cf: CorpusFile, node: ast.AST | None) -> Provenance:
    line_range = None
    if node is not None and hasattr(node, "lineno"):
        end = getattr(node, "end_lineno", node.lineno)
        line_range = (node.lineno, end)
    return Provenance(
        source_file=cf.path,
        line_range=line_range,
        extraction_pass="syntax",
    )


def _name_of(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""
