"""Unit tests for lens.extract.syntax."""

from lens.extract.syntax import (
    PythonSyntaxHandler,
    GenericSyntaxHandler,
    SyntaxHandlerRegistry,
    extract_syntax,
)
from lens.models import CorpusFile, NodeKind, EdgeRelation


SAMPLE_PYTHON = """\
import os
from pathlib import Path

class Animal:
    def speak(self):
        pass

class Dog(Animal):
    def speak(self):
        return "woof"

def main():
    d = Dog()
    d.speak()
"""

SAMPLE_JS = """\
class Widget {
    constructor(name) { this.name = name; }
}
function render() {}
const ITEMS = [];
"""


class TestPythonSyntaxHandler:
    def test_extracts_classes_and_functions(self):
        cf = CorpusFile(path="animal.py", content=SAMPLE_PYTHON, language="python")
        handler = PythonSyntaxHandler()
        result = handler.extract(cf)
        labels = {n.label for n in result.nodes}
        assert "Animal" in labels
        assert "Dog" in labels
        assert "main" in labels
        assert "speak" in labels

    def test_extracts_imports(self):
        cf = CorpusFile(path="animal.py", content=SAMPLE_PYTHON, language="python")
        handler = PythonSyntaxHandler()
        result = handler.extract(cf)
        labels = {n.label for n in result.nodes}
        assert "os" in labels
        assert "pathlib" in labels

    def test_import_edges(self):
        cf = CorpusFile(path="animal.py", content=SAMPLE_PYTHON, language="python")
        handler = PythonSyntaxHandler()
        result = handler.extract(cf)
        import_edges = [e for e in result.edges if e.relation == EdgeRelation.IMPORTS]
        assert len(import_edges) >= 2

    def test_handles_syntax_error(self):
        cf = CorpusFile(path="bad.py", content="def (broken", language="python")
        handler = PythonSyntaxHandler()
        result = handler.extract(cf)
        assert result.nodes == []
        assert result.edges == []

    def test_inheritance_edges(self):
        cf = CorpusFile(path="animal.py", content=SAMPLE_PYTHON, language="python")
        handler = PythonSyntaxHandler()
        result = handler.extract(cf)
        inherit_edges = [e for e in result.edges if e.relation == EdgeRelation.INHERITS]
        assert len(inherit_edges) >= 1


class TestGenericSyntaxHandler:
    def test_javascript(self):
        cf = CorpusFile(path="widget.js", content=SAMPLE_JS, language="javascript")
        handler = GenericSyntaxHandler()
        assert handler.can_handle("javascript")
        result = handler.extract(cf)
        labels = {n.label for n in result.nodes}
        assert "Widget" in labels
        assert "render" in labels

    def test_unsupported_language(self):
        handler = GenericSyntaxHandler()
        assert handler.can_handle("markdown") is False


class TestExtractSyntax:
    def test_merged_results(self):
        files = [
            CorpusFile(path="a.py", content="def hello(): pass", language="python"),
            CorpusFile(path="b.py", content="class Foo: pass", language="python"),
        ]
        result = extract_syntax(files)
        labels = {n.label for n in result.nodes}
        assert "hello" in labels
        assert "Foo" in labels
