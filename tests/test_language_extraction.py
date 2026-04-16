"""Unit tests for expanded language support in lens.extract.syntax.

Covers C++, C#, Rust, C, and import/include edge extraction.
"""

from lens.extract.syntax import GenericSyntaxHandler, extract_syntax
from lens.models import CorpusFile, NodeKind, EdgeRelation


# ---------------------------------------------------------------------------
# C++
# ---------------------------------------------------------------------------

SAMPLE_CPP = """\
#include <iostream>
#include "myheader.h"

namespace Engine {

class Renderer {
public:
    virtual void draw() = 0;
};

struct Vertex {
    float x, y, z;
};

enum class ShaderType {
    Vertex,
    Fragment
};

template<typename T>
class ResourcePool {
    T* allocate();
};

void initialize(int argc, char** argv) {
    // setup
}

}  // namespace Engine
"""


class TestCppExtraction:
    def test_extracts_classes_and_structs(self):
        cf = CorpusFile(path="engine.cpp", content=SAMPLE_CPP, language="cpp")
        handler = GenericSyntaxHandler()
        assert handler.can_handle("cpp")
        result = handler.extract(cf)
        labels = {n.label for n in result.nodes}
        assert "Renderer" in labels
        assert "Vertex" in labels

    def test_extracts_namespace(self):
        cf = CorpusFile(path="engine.cpp", content=SAMPLE_CPP, language="cpp")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes if n.kind == NodeKind.MODULE}
        assert "Engine" in labels

    def test_extracts_enum_class(self):
        cf = CorpusFile(path="engine.cpp", content=SAMPLE_CPP, language="cpp")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes}
        assert "ShaderType" in labels

    def test_extracts_functions(self):
        cf = CorpusFile(path="engine.cpp", content=SAMPLE_CPP, language="cpp")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes if n.kind == NodeKind.FUNCTION}
        assert "initialize" in labels

    def test_extracts_includes(self):
        cf = CorpusFile(path="engine.cpp", content=SAMPLE_CPP, language="cpp")
        result = GenericSyntaxHandler().extract(cf)
        import_edges = [e for e in result.edges if e.relation == EdgeRelation.IMPORTS]
        imported_labels = set()
        for e in import_edges:
            for n in result.nodes:
                if n.uid == e.target_id:
                    imported_labels.add(n.label)
        assert "iostream" in imported_labels
        assert "myheader.h" in imported_labels

    def test_extracts_template_class(self):
        cf = CorpusFile(path="engine.cpp", content=SAMPLE_CPP, language="cpp")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes}
        assert "ResourcePool" in labels


# ---------------------------------------------------------------------------
# C#
# ---------------------------------------------------------------------------

SAMPLE_CSHARP = """\
using System;
using System.Collections.Generic;
using Microsoft.Extensions.Logging;

namespace MyApp.Services
{
    public class UserService
    {
        private readonly ILogger _logger;

        public UserService(ILogger logger)
        {
            _logger = logger;
        }

        public async Task<User> GetUserAsync(int id)
        {
            return await _repo.FindAsync(id);
        }
    }

    public interface IRepository
    {
        Task<T> FindAsync<T>(int id);
    }

    public struct Point
    {
        public int X;
        public int Y;
    }

    public enum Status
    {
        Active,
        Inactive
    }
}
"""


class TestCsharpExtraction:
    def test_extracts_class(self):
        cf = CorpusFile(path="UserService.cs", content=SAMPLE_CSHARP, language="csharp")
        handler = GenericSyntaxHandler()
        assert handler.can_handle("csharp")
        result = handler.extract(cf)
        labels = {n.label for n in result.nodes}
        assert "UserService" in labels

    def test_extracts_interface(self):
        cf = CorpusFile(path="UserService.cs", content=SAMPLE_CSHARP, language="csharp")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes}
        assert "IRepository" in labels

    def test_extracts_struct_and_enum(self):
        cf = CorpusFile(path="UserService.cs", content=SAMPLE_CSHARP, language="csharp")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes}
        assert "Point" in labels
        assert "Status" in labels

    def test_extracts_namespace(self):
        cf = CorpusFile(path="UserService.cs", content=SAMPLE_CSHARP, language="csharp")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes if n.kind == NodeKind.MODULE}
        assert "MyApp.Services" in labels

    def test_extracts_using_statements(self):
        cf = CorpusFile(path="UserService.cs", content=SAMPLE_CSHARP, language="csharp")
        result = GenericSyntaxHandler().extract(cf)
        import_edges = [e for e in result.edges if e.relation == EdgeRelation.IMPORTS]
        imported = set()
        for e in import_edges:
            for n in result.nodes:
                if n.uid == e.target_id:
                    imported.add(n.label)
        assert "System" in imported
        assert "System.Collections.Generic" in imported
        assert "Microsoft.Extensions.Logging" in imported

    def test_extracts_methods(self):
        cf = CorpusFile(path="UserService.cs", content=SAMPLE_CSHARP, language="csharp")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes if n.kind == NodeKind.FUNCTION}
        assert "GetUserAsync" in labels


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------

SAMPLE_RUST = """\
use std::collections::HashMap;
use tokio::sync::Mutex;

mod config;

pub struct AppState {
    db: DatabasePool,
    cache: HashMap<String, String>,
}

pub enum Command {
    Start,
    Stop,
    Restart,
}

pub trait Handler {
    fn handle(&self, cmd: Command) -> Result<(), Error>;
}

impl AppState {
    pub fn new(db: DatabasePool) -> Self {
        Self { db, cache: HashMap::new() }
    }
}

pub fn run_server(state: AppState) -> Result<(), Error> {
    // ...
    Ok(())
}

type UserId = u64;
"""


class TestRustExtraction:
    def test_extracts_struct(self):
        cf = CorpusFile(path="main.rs", content=SAMPLE_RUST, language="rust")
        handler = GenericSyntaxHandler()
        assert handler.can_handle("rust")
        result = handler.extract(cf)
        labels = {n.label for n in result.nodes}
        assert "AppState" in labels

    def test_extracts_enum(self):
        cf = CorpusFile(path="main.rs", content=SAMPLE_RUST, language="rust")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes}
        assert "Command" in labels

    def test_extracts_trait(self):
        cf = CorpusFile(path="main.rs", content=SAMPLE_RUST, language="rust")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes}
        assert "Handler" in labels

    def test_extracts_function(self):
        cf = CorpusFile(path="main.rs", content=SAMPLE_RUST, language="rust")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes if n.kind == NodeKind.FUNCTION}
        assert "run_server" in labels

    def test_extracts_mod(self):
        cf = CorpusFile(path="main.rs", content=SAMPLE_RUST, language="rust")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes if n.kind == NodeKind.MODULE}
        assert "config" in labels

    def test_extracts_use_statements(self):
        cf = CorpusFile(path="main.rs", content=SAMPLE_RUST, language="rust")
        result = GenericSyntaxHandler().extract(cf)
        import_edges = [e for e in result.edges if e.relation == EdgeRelation.IMPORTS]
        imported = set()
        for e in import_edges:
            for n in result.nodes:
                if n.uid == e.target_id:
                    imported.add(n.label)
        assert "std::collections::HashMap" in imported
        assert "tokio::sync::Mutex" in imported

    def test_extracts_type_alias(self):
        cf = CorpusFile(path="main.rs", content=SAMPLE_RUST, language="rust")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes}
        assert "UserId" in labels


# ---------------------------------------------------------------------------
# C
# ---------------------------------------------------------------------------

SAMPLE_C = """\
#include <stdio.h>
#include "utils.h"

typedef struct Node {
    int value;
    struct Node* next;
} Node;

enum LogLevel {
    DEBUG,
    INFO,
    ERROR
};

void process_data(int* data, size_t len) {
    for (size_t i = 0; i < len; i++) {
        printf("%d\\n", data[i]);
    }
}

static int helper(void) {
    return 42;
}
"""


class TestCExtraction:
    def test_extracts_struct(self):
        cf = CorpusFile(path="data.c", content=SAMPLE_C, language="c")
        handler = GenericSyntaxHandler()
        assert handler.can_handle("c")
        result = handler.extract(cf)
        labels = {n.label for n in result.nodes}
        assert "Node" in labels

    def test_extracts_enum(self):
        cf = CorpusFile(path="data.c", content=SAMPLE_C, language="c")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes}
        assert "LogLevel" in labels

    def test_extracts_functions(self):
        cf = CorpusFile(path="data.c", content=SAMPLE_C, language="c")
        result = GenericSyntaxHandler().extract(cf)
        labels = {n.label for n in result.nodes if n.kind == NodeKind.FUNCTION}
        assert "process_data" in labels
        assert "helper" in labels

    def test_extracts_includes(self):
        cf = CorpusFile(path="data.c", content=SAMPLE_C, language="c")
        result = GenericSyntaxHandler().extract(cf)
        import_edges = [e for e in result.edges if e.relation == EdgeRelation.IMPORTS]
        imported = set()
        for e in import_edges:
            for n in result.nodes:
                if n.uid == e.target_id:
                    imported.add(n.label)
        assert "stdio.h" in imported
        assert "utils.h" in imported


# ---------------------------------------------------------------------------
# Cross-language merge
# ---------------------------------------------------------------------------

class TestMultiLanguageMerge:
    def test_mixed_corpus(self):
        files = [
            CorpusFile(path="main.py", content="def hello(): pass", language="python"),
            CorpusFile(path="app.rs", content="fn serve() {}", language="rust"),
            CorpusFile(path="engine.cpp", content="class Engine {};", language="cpp"),
            CorpusFile(path="svc.cs", content="class Service {}", language="csharp"),
        ]
        result = extract_syntax(files)
        labels = {n.label for n in result.nodes}
        assert "hello" in labels
        assert "serve" in labels
        assert "Engine" in labels
        assert "Service" in labels
