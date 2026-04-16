# Lens

Lens is an internal Microsoft tool that ingests a codebase and its associated
documentation, constructs a queryable knowledge graph, and produces analysis
artifacts — an interactive visualization, a structured report, and a JSON-LD
graph you can query from the CLI, a REST API, or GitHub Copilot.

---
gr
## Features

| Feature | What it does |
|---|---|
| **Structural extraction** | Parses source code into an AST and extracts classes, functions, imports, inheritance, and call edges. Full AST for Python; regex-based for C++, C#, C, Rust, JS, TS, Java, Go. |
| **Semantic extraction** | Extracts domain concepts, cross-references, and relationships from Markdown docs and Python docstrings. |
| **Knowledge graph** | Assembles all extractions into a directed NetworkX graph with nodes, edges, and provenance metadata. |
| **Cluster detection** | Groups related nodes into communities using Leiden (or greedy-modularity fallback). |
| **Interactive explorer** | Generates a self-contained `explorer.html` — search, click, and browse the graph in any browser. |
| **Analysis report** | Generates `analysis-report.md` with corpus stats, high-connectivity nodes, cross-cluster connections, cluster summaries, and an integrity audit. |
| **JSON-LD export** | Exports the graph to `knowledge-graph.jsonld` (W3C standard) with `urn:lens:` URIs. |
| **GraphML export** | Exports to `knowledge-graph.graphml` for use in Gephi, yEd, or other tools. |
| **Incremental update** | SHA256-based caching in SQLite — re-runs only process files that changed. |
| **Git hooks** | Auto-rebuild the graph on every commit and branch switch. |
| **REST query API** | FastAPI server with `/nodes`, `/neighbors`, `/path`, `/subgraph`, `/clusters` endpoints. |
| **GitHub Copilot integration** | Installs `AGENTS.md` and `copilot-instructions.md` so Copilot reads the graph before searching raw files. |

### Supported languages

| Language | Declarations extracted | Import/include edges |
|---|---|---|
| Python | classes, functions (full AST) | `import`, `from...import` |
| C++ | classes, structs, templates, enums, namespaces, functions | `#include` |
| C# | classes, interfaces, structs, enums, namespaces, methods | `using` |
| C | structs, enums, functions | `#include` |
| Rust | structs, enums, traits, impl, mods, functions, type aliases | `use` |
| JavaScript | classes, functions | `import...from`, `require()` |
| TypeScript | classes, interfaces, functions | `import...from`, `require()` |
| Java | classes, interfaces, methods | `import` |
| Go | functions, structs, interfaces | package imports |

---

## Install

```bash
pip install microsoft-lens-sdk
```

Then open your project and run:

```bash
lens install
```

That's it. Lens sets up Copilot integration, installs git hooks, and builds the
knowledge graph — all in one command.

> **Not on PyPI yet?** Install directly from GitHub:
> ```bash
> pip install git+https://github.com/dasaradhattuluri/Lens.git && lens install
> ```

### From source (for contributors)

```bash
git clone https://github.com/dasaradhattuluri/Lens.git
cd Lens
pip install -e ".[dev]"
```

### Ask GitHub Copilot to install it

In VS Code Copilot Chat, just say:

```
Install Lens and run it on my workspace:
pip install git+https://github.com/dasaradhattuluri/Lens.git
Then run: lens install
```

---

## Quick-start

```bash
# Install + build graph in one step
pip install git+https://github.com/dasaradhattuluri/Lens.git && lens install

# Open the interactive explorer
start .lens/artifacts/explorer.html       # Windows
# open .lens/artifacts/explorer.html      # macOS

# Query a specific node
lens graph query --label "MyService"

# Start the REST API
lens api serve
# → http://127.0.0.1:8400/docs (Swagger UI)
```

---

## CLI Reference

Every command supports `--help`. The CLI follows a **noun-verb** pattern.

### Top-level

```
lens [--version] [--config PATH] [--help] COMMAND
```

### `lens install` — One-step workspace setup

```bash
lens install              # Set up Lens + build graph for current dir
lens install ./my-repo    # Set up Lens + build graph for another repo
lens install --no-ingest  # Set up only, skip graph build
```

Writes Copilot integration files (`AGENTS.md`, `.github/copilot-instructions.md`,
`.vscode/settings.json`), installs git hooks, and automatically builds the
knowledge graph — all in one command.

### `lens corpus ingest` — Build the knowledge graph

```bash
lens corpus ingest .                    # Full scan of current directory
lens corpus ingest ./src                # Scan a specific folder
lens corpus ingest . --update           # Incremental — skip unchanged files
lens corpus ingest . --full             # Force full re-scan (ignore cache)
lens corpus ingest . --config my.yaml   # Use a custom config file
```

**What it does:**
1. Walks the directory tree and reads all recognised files
2. Runs the syntax-aware extraction pass (AST / regex per language)
3. Runs the concept-mapping pass (headings, cross-refs, docstrings)
4. Assembles the knowledge graph and detects communities
5. Exports JSON-LD, GraphML, interactive HTML, and analysis report to `.lens/artifacts/`

### `lens graph query` — Look up a node

```bash
lens graph query --label "UserService"
lens graph query --label "main" --depth 2
```

Shows the node's kind, ID, and its neighbours up to `--depth` hops.

### `lens graph export` — Re-export in a specific format

```bash
lens graph export --format jsonld
lens graph export --format graphml
```

### `lens report generate` — Regenerate report from existing graph

```bash
lens report generate
```

Rewrites `analysis-report.md` and `explorer.html` without re-scanning files.
Useful after manually editing the graph or changing config.

### `lens api serve` — Start the REST query API

```bash
lens api serve
```

Starts a FastAPI server on `http://127.0.0.1:8400` (configurable in `lens.config.yaml`).

**Endpoints:**

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | Health check |
| GET | `/nodes?label=X&kind=Y&limit=N` | List / filter nodes |
| GET | `/neighbors?node_id=X&depth=N` | Neighbourhood traversal |
| GET | `/path?source=X&target=Y` | Shortest path between two nodes |
| GET | `/subgraph?node_ids=A,B,C` | Extract a subgraph |
| GET | `/clusters` | List all clusters with member counts |

Interactive docs at `/docs` (Swagger UI) once the server is running.

### `lens hook install` — Auto-rebuild on git events

```bash
lens hook install       # Install post-commit + post-checkout hooks
lens hook status        # Check which hooks are installed
lens hook uninstall     # Remove Lens hooks
```

After install, the graph rebuilds incrementally on every `git commit` and
`git checkout`. Hooks are safe — they refuse to overwrite non-Lens hooks
and they exit non-zero on failure so git surfaces errors.

### `lens copilot install` — GitHub Copilot integration

```bash
lens copilot install    # Write AGENTS.md + copilot-instructions + VS Code settings
lens copilot uninstall  # Remove Lens Copilot files
```

Creates three files that make Copilot graph-aware (see next section).

---

## Using Lens with GitHub Copilot

### Setup (one-time)

```bash
# 1. Build the graph
lens corpus ingest .

# 2. Install Copilot integration
lens copilot install

# 3. (Optional) Install git hooks so the graph stays fresh
lens hook install
```

This creates:
- **`AGENTS.md`** — tells Copilot Chat to read the analysis report before searching raw files
- **`.github/copilot-instructions.md`** — Copilot-specific instructions loaded in every conversation
- **`.vscode/settings.json`** — excludes `.lens/cache/` from VS Code search

### How it works

Once installed, when you ask Copilot a question about the codebase:

1. Copilot reads `AGENTS.md` and `.github/copilot-instructions.md` automatically
2. It learns that `.lens/artifacts/analysis-report.md` exists
3. It reads the report **first** — getting the module structure, high-connectivity
   nodes, cluster layout, and key entities
4. It then navigates based on graph structure rather than grep-searching every file

### Examples in Copilot Chat

```
You: "How is the authentication module connected to the API layer?"
→ Copilot reads analysis-report.md, finds the relevant cluster and cross-cluster
  edges, and gives a graph-informed answer.

You: "What are the most critical classes in this repo?"
→ Copilot reads the High-Connectivity Nodes section of the report.

You: "What would break if I refactored DataProcessor?"
→ Copilot looks up DataProcessor's neighbours and incoming edges in the graph.
```

### Keeping the graph fresh

| Method | When it updates | Setup |
|---|---|---|
| Manual | When you run `lens corpus ingest .` | None |
| Incremental | When you run `lens corpus ingest . --update` | None |
| Git hooks | On every commit and branch switch | `lens hook install` |

---

## Configuration

Create `lens.config.yaml` in your working directory (all fields are optional):

```yaml
# Path to the codebase to analyse
corpus_root: .

# Where to write output artifacts
output_dir: .lens/artifacts

# Where to store incremental-update cache
cache_dir: .lens/cache

# Extraction passes
extraction:
  syntax: true        # AST-based structural extraction
  concepts: true      # Semantic concept-mapping extraction

# Community detection
cluster:
  algorithm: leiden    # "leiden" or "greedy"
  resolution: 1.0     # Higher = more clusters

# REST API settings
api:
  host: 127.0.0.1
  port: 8400
```

---

## Output artifacts

After running `lens corpus ingest`, you'll find these in `.lens/artifacts/`:

| File | Format | Purpose |
|---|---|---|
| `knowledge-graph.jsonld` | JSON-LD | Machine-readable graph with `urn:lens:` URIs, provenance, and cluster assignments |
| `knowledge-graph.graphml` | GraphML/XML | Import into Gephi, yEd, or other graph tools |
| `explorer.html` | HTML | Self-contained interactive visualization (no CDN, works air-gapped) |
| `analysis-report.md` | Markdown | Corpus stats, high-connectivity nodes, cross-cluster bridges, cluster summaries, entity inventory, integrity audit |

The incremental cache lives in `.lens/cache/corpus-state.db` (SQLite).

---

## Running tests

```bash
pytest              # Run all 96 tests
pytest -v           # Verbose output
pytest tests/test_hooks.py  # Run a specific test file
```

---

## Project structure

```
src/lens/
├── cli.py                  # Click CLI (lens command)
├── config.py               # YAML config loader
├── models.py               # Shared types: KGNode, KGEdge, KGCluster, Provenance
├── ingest.py               # File discovery, hashing, adapter registry
├── extract/
│   ├── syntax.py           # AST / regex structural extraction (10 languages)
│   └── concepts.py         # Semantic concept extraction (heuristic)
├── graph.py                # KnowledgeGraph: NetworkX, clustering, JSON-LD/GraphML export
├── render.py               # HTML explorer + Markdown report generation
├── query.py                # FastAPI REST API
├── pipeline.py             # DAG-based task runner
├── hooks.py                # Git hook install / uninstall / status
└── copilot_integration.py  # Copilot / VS Code file installer
```
