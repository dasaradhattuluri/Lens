# Lens — Internal Audit Report

| Field | Value |
|---|---|
| Auditor | Principal Platform Engineering |
| Scope | Full codebase at `Lens/` (commit as of 2026-04-13) |
| Reference benchmark | Graphify v0.4.11 (github.com/safishamsi/graphify) |
| Classification | Microsoft Confidential |

---

## 1  Feature Parity — Capability Matrix

| # | Capability | Reference (Graphify) | Lens Status | Notes |
|---|---|---|---|---|
| 1 | **AST-based structural extraction** | tree-sitter, 23 languages | ✅ Implemented | Python via `ast`; JS/TS/Java/C#/Go via regex fallback. Only Python is full-fidelity; others are partial. Tree-sitter planned Phase 2. |
| 2 | **Semantic / concept extraction** | Claude subagents, parallel, with confidence scores | ⚠️ Partial | Heuristic extractor (headings, backtick refs, docstrings). No LLM integration yet — Azure OpenAI GPT-4o gateway call is spec'd but not wired. |
| 3 | **Knowledge graph construction** | NetworkX, directed/undirected toggle | ✅ Implemented | NetworkX DiGraph, add_node/add_edge, subgraph, neighbors, find_by_label. No undirected toggle. |
| 4 | **Cluster / community detection** | Leiden via graspologic | ✅ Implemented | Leiden with leidenalg (optional), greedy-modularity fallback. |
| 5 | **JSON-LD graph export** | `graph.json` (adjacency) | ✅ Implemented | `knowledge-graph.jsonld` with `urn:lens:` namespace. Different schema by design. |
| 6 | **GraphML export** | `--graphml` flag | ✅ Implemented | `knowledge-graph.graphml` via XML ElementTree. |
| 7 | **Interactive HTML visualization** | vis.js, `graph.html` | ✅ Implemented | Self-contained `explorer.html`, inline SVG force-layout (no CDN). Simpler than vis.js but functional. |
| 8 | **Markdown analysis report** | `GRAPH_REPORT.md` (god nodes, surprises, questions) | ⚠️ Partial | `analysis-report.md` has summary stats, cluster list, entity inventory, integrity audit. Missing: god nodes, surprising connections, suggested questions, confidence-score reporting. |
| 9 | **CLI** | slash-command (`/graphify .`) + terminal CLI | ✅ Implemented | Click-based noun-verb: `lens corpus ingest`, `lens graph query`, `lens report generate`, `lens api serve`. |
| 10 | **REST / MCP query server** | `python -m graphify.serve` (MCP stdio) with `query_graph`, `get_node`, `get_neighbors`, `shortest_path` | ⚠️ Partial | FastAPI with `/nodes`, `/neighbors`, `/path`, `/subgraph`, `/clusters`. No MCP stdio protocol — HTTP only. |
| 11 | **Incremental update (`--update`)** | SHA256 cache, `--update` re-extracts changed files only | ❌ Missing | `content_hash` is computed per file but never persisted or compared. No `corpus-state.db`. Full re-scan every run. |
| 12 | **Watch mode (`--watch`)** | File-system watcher, auto-rebuild on save | ❌ Missing | Not implemented. |
| 13 | **Git hooks (`hook install`)** | post-commit / post-checkout auto-rebuild | ❌ Missing | Not implemented. |
| 14 | **Agent / Copilot integration** | AGENTS.md, CLAUDE.md hooks, `.cursor/rules/`, Copilot skill, Gemini skill | ❌ Missing | No AGENTS.md, no `.copilot/skills/`, no MCP config, no PreToolUse hooks. |
| 15 | **`/lens` slash command** | `/graphify` triggers skill in Claude Code, Codex, Copilot, etc. | ❌ Missing | No skill file, no slash-command registration. |
| 16 | **`query` / `path` / `explain` commands** | CLI + slash-command: `graphify query`, `graphify path`, `graphify explain` | ⚠️ Partial | `lens graph query --label` and API `/path` exist. No `explain` (plain-language node summary). No free-text graph query. |
| 17 | **Content fetching (`add <url>`)** | Fetch papers, tweets, video URLs, add to corpus | ❌ Missing | No URL/content fetching capability. |
| 18 | **Video / audio transcription** | faster-whisper + yt-dlp, local transcription | ❌ Missing | Phase 2 per REQUIREMENTS.md. |
| 19 | **PDF / Office extraction** | .pdf, .docx, .xlsx via conversion | ❌ Missing | Not implemented. |
| 20 | **Confidence scoring on edges** | EXTRACTED / INFERRED / AMBIGUOUS tags, 0.0–1.0 scores | ❌ Missing | Edges have `weight` but no confidence/provenance-type tagging. |
| 21 | **Hyperedges** | Group relationships connecting 3+ nodes | ❌ Missing | |
| 22 | **Neo4j / Cosmos DB push** | `--neo4j-push`, Cypher export | ❌ Missing | Cosmos DB Gremlin push spec'd for Phase 2 but not implemented. |
| 23 | **Multi-platform install** | `graphify install --platform <X>` for 13+ platforms | ❌ Missing | No platform-specific install commands. |
| 24 | **`.lensignore` file** | `.graphifyignore` for excluding paths | ❌ Missing | Uses hardcoded `_SKIP_DIRS` only. |
| 25 | **Wiki generation (`--wiki`)** | Markdown wiki per community + index.md | ❌ Missing | |
| 26 | **SVG export** | `--svg` flag | ❌ Missing | |
| 27 | **Token benchmark reporting** | Printed after every run | ❌ Missing | |
| 28 | **Unit tests** | CI with test suite | ✅ Implemented | 55 tests, all passing. Good coverage across all modules. |

### Summary

| Status | Count |
|---|---|
| ✅ Implemented | 9 |
| ⚠️ Partially implemented | 4 |
| ❌ Missing | 15 |

**Lens covers the core pipeline** (ingest → extract → graph → cluster → export → visualize → query API) but is missing the wrapper capabilities that make the reference project practically useful in daily workflows: incremental updates, agent integration, watch mode, and advanced reporting.

---

## 2  Update & Freshness Model

### Current state

| Mode | Supported? | Evidence |
|---|---|---|
| **(a) Manual refresh only** | ✅ Yes | `lens corpus ingest` always does a full re-scan. This is the only path. |
| **(b) Incremental update via git diff** | ❌ No | `CorpusFile.content_hash` is computed in [`ingest.py`](src/lens/ingest.py#L57) but never persisted. No `corpus-state.db` exists. No diff logic. |
| **(c) Git hook–based auto update** | ❌ No | No hook installer. No file-system watcher. |

### Evidence

- [`ingest.py` L57](src/lens/ingest.py#L57): `content_hash=_hash_content(content)` — hash is computed but discarded after the run.
- [`REQUIREMENTS.md` §5.2](REQUIREMENTS.md): spec calls for `corpus-state.db` in `.lens/cache/` — file is never created.
- No `--update`, `--watch`, or `hook` subcommands in [`cli.py`](src/lens/cli.py).

### Recommendation (enterprise-friendly)

Implement **option (b) first** — a SQLite-backed hash store (`corpus-state.db`):

1. On ingest, load the previous hash map from `.lens/cache/corpus-state.db`.
2. Compare `content_hash` per file path; skip unchanged files.
3. After extraction, write updated hashes back.
4. Add `lens corpus ingest --full` to bypass the cache when needed.

This is safe (no background process, no git dependency), auditable (the DB is inspectable), and aligns with REQUIREMENTS.md FR-ING-02.

**Option (c)** (git hooks) should be Phase 2 — install via `lens hook install` writing a `post-commit` script that calls `lens corpus ingest --update`.

---

## 3  GitHub Copilot Integration

### Current state

| Integration mechanism | Present? |
|---|---|
| `AGENTS.md` | ❌ No |
| `.github/copilot-instructions.md` | ❌ No |
| `.copilot/skills/lens/SKILL.md` | ❌ No |
| `.cursor/rules/*.mdc` | ❌ No |
| MCP server config (`.mcp.json`) | ❌ No |
| PreToolUse / BeforeTool hooks | ❌ No |

### What the reference project does

Graphify installs per-platform always-on rules that tell the AI assistant to read `GRAPH_REPORT.md` before searching raw files, and optionally exposes the graph as an MCP stdio server for structured queries.

### Proposed minimal `AGENTS.md`

A file that makes Copilot (and other agents) aware of the knowledge graph:

```markdown
# Lens Knowledge Graph

This repository has a pre-built knowledge graph in `.lens/artifacts/`.

## Before answering architecture questions

1. Read `.lens/artifacts/analysis-report.md` for a summary of modules,
   clusters, and key entities.
2. Use the graph structure to navigate — prefer cluster-aware traversal
   over grep.
3. If `.lens/artifacts/knowledge-graph.jsonld` exists, consult it for
   node relationships before reading raw source files.

## Available commands

- `lens corpus ingest .` — rebuild the graph from current files
- `lens graph query --label <name>` — look up a node and its neighbours
- `lens api serve` — start the REST query API on port 8400
```

### Proposed `.github/copilot-instructions.md`

```markdown
When answering questions about this codebase, check if
`.lens/artifacts/analysis-report.md` exists. If it does, read it first
to understand the module structure and key entities before searching files.
```

---

## 4  CLI & UX Audit

### Available commands

| Command | Description | `--help` | Status |
|---|---|---|---|
| `lens --help` | Top-level help | ✅ | Works |
| `lens corpus ingest [PATH]` | Ingest a directory | ✅ | Works |
| `lens graph query --label X` | Node lookup + neighbours | ✅ | Works |
| `lens graph export --format F` | Re-export graph | ✅ | Works |
| `lens report generate` | Regenerate report + HTML | ✅ | Works |
| `lens api serve` | Start REST API server | ✅ | Works |

### Gaps

| Gap | Severity |
|---|---|
| No `lens corpus ingest --update` (incremental) | P0 |
| No `lens corpus ingest --watch` | P1 |
| No `lens hook install / uninstall / status` | P1 |
| No `lens graph explain --label X` (plain-language summary) | P2 |
| No `lens query "free-text question"` (NL query) | P2 |
| No `--version` flag | P1 |
| No `--verbose / --quiet` flags | P2 |
| No `lens corpus status` (show file count, last run, stale files) | P1 |

---

## 5  Slash-Command Behaviour

### Current state

`/lens` is **not supported or simulated** anywhere in this repo. There is:

- No skill file registered with any AI coding assistant
- No `SKILL.md` that would be picked up by Copilot, Claude Code, or Gemini CLI
- No MCP stdio server that would expose graph operations as tool calls

### How users should trigger Lens-powered reasoning today

1. **Manual CLI workflow**: Run `lens corpus ingest .`, then ask Copilot questions while `.lens/artifacts/analysis-report.md` is open in the editor — Copilot will include it as context.
2. **REST API**: Run `lens api serve`, then write a custom Copilot extension or MCP wrapper that calls the HTTP endpoints.
3. **AGENTS.md** (once added): Copilot will read it automatically and learn to consult graph artifacts.

### Path to `/lens` support

To enable `/lens` as a Copilot slash command:

1. Create `.copilot/skills/lens/SKILL.md` describing the tool.
2. Implement `lens.serve` as an MCP stdio server (JSON-RPC over stdin/stdout) exposing `query_graph`, `get_neighbors`, `shortest_path` tools.
3. Add `.mcp.json` to the repo root pointing to the server.

---

## 6  Trial & Onboarding

### Step-by-step local setup

```powershell
# 1. Clone / navigate to the Lens repo
cd Lens

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1    # Windows
# source .venv/bin/activate   # Linux/Mac

# 3. Install in editable mode with dev dependencies
pip install -e ".[dev]"

# 4. Run the test suite to verify installation
pytest

# 5. Ingest a target codebase (e.g., itself)
lens corpus ingest .

# 6. View the outputs
dir .lens\artifacts\
# => knowledge-graph.jsonld, knowledge-graph.graphml,
#    explorer.html, analysis-report.md

# 7. Open the interactive explorer
start .lens\artifacts\explorer.html

# 8. Query the graph
lens graph query --label "KnowledgeGraph"

# 9. Start the REST API
lens api serve
# => http://127.0.0.1:8400/docs  (Swagger UI)
```

### Missing docs / scripts / guardrails

| Item | Status | Action needed |
|---|---|---|
| Step-by-step onboarding in README | ⚠️ Minimal | Expand with the steps above |
| `lens.config.yaml` example with comments | ✅ Exists | Fine |
| `.gitignore` for `.lens/` directory | ❌ Missing | Add to prevent committing artifacts |
| `CONTRIBUTING.md` | ❌ Missing | Add for internal contributors |
| CI pipeline (ADO or GitHub Actions) | ❌ Missing | Add `pytest` step |
| `--version` output | ❌ Missing | Wire to `pyproject.toml` version |
| Error handling for missing dependencies | ⚠️ Partial | `leidenalg` fallback exists; others unclear |
| Security: credential scanning of ingested content | ❌ Missing | Required by REQUIREMENTS.md NFR-03 |

---

## 7  Prioritised Improvements

### P0 — Must-fix before any internal trial

| # | Item | Effort |
|---|---|---|
| P0-1 | **Incremental update** — persist `content_hash` in SQLite `corpus-state.db`, skip unchanged files, add `--full` flag to force re-scan | M |
| P0-2 | **AGENTS.md + copilot-instructions.md** — so Copilot reads the graph report before raw file search | S |
| P0-3 | **`.gitignore`** — exclude `.lens/`, `__pycache__/`, `*.egg-info` | S |
| P0-4 | **`--version` flag** | S |
| P0-5 | **Richer analysis report** — add god-node detection (top-N highest-degree nodes), cross-cluster bridge edges | M |

### P1 — Required for production readiness

| # | Item | Effort |
|---|---|---|
| P1-1 | **MCP stdio server** (`lens.serve`) — expose `query_graph`, `get_neighbors`, `shortest_path` as JSON-RPC tools for Copilot / Claude Code | L |
| P1-2 | **`lens hook install`** — git post-commit / post-checkout hooks | M |
| P1-3 | **Confidence tagging** — EXTRACTED vs INFERRED on edges, 0.0–1.0 score from LLM pass | M |
| P1-4 | **Azure OpenAI integration** — wire concept-extraction to GPT-4o structured output via internal gateway, replacing heuristic fallback | L |
| P1-5 | **`lens corpus status`** — show last run timestamp, file count, stale-file count | S |
| P1-6 | **CI pipeline** — ADO YAML with `pytest`, linting, Component Governance scan | M |
| P1-7 | **`.lensignore` file support** — gitignore-syntax exclusion patterns | S |

### P2 — Nice-to-have / future phases

| # | Item | Effort |
|---|---|---|
| P2-1 | **Watch mode** (`--watch`) — file-system watcher for live rebuild | M |
| P2-2 | **`lens graph explain --label X`** — LLM-generated plain-language node summary | M |
| P2-3 | **Free-text NL query** (`lens query "what connects X to Y?"`) | L |
| P2-4 | **Tree-sitter integration** — replace regex fallback for non-Python languages | L |
| P2-5 | **SVG export** | S |
| P2-6 | **PDF / Office ingestion** | M |
| P2-7 | **Cosmos DB Gremlin push** | L |
| P2-8 | **Wiki generation** — one Markdown article per cluster + index.md | M |
| P2-9 | **Token benchmark** — report token savings vs raw-file reading | S |

Effort: **S** = < 1 day, **M** = 1–3 days, **L** = 3–5 days

---

## 8  Concrete Next Steps for Copilot Production Readiness

```
Week 1:  P0-1 (incremental update), P0-2 (AGENTS.md), P0-3 (.gitignore),
         P0-4 (--version), P0-5 (god-node report)

Week 2:  P1-1 (MCP stdio server), P1-5 (corpus status), P1-7 (.lensignore)

Week 3:  P1-4 (Azure OpenAI wiring), P1-3 (confidence tagging)

Week 4:  P1-2 (git hooks), P1-6 (CI pipeline), validation + internal dogfood
```

After Week 4, Lens can be trialled on an internal repo with Copilot reading
`AGENTS.md` + `analysis-report.md` and optionally querying the MCP server.

---

*End of audit.*
