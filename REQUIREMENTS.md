# Lens — Requirements & Constraints

| Field | Value |
|---|---|
| **Document owner** | Platform Engineering — Internal Tools |
| **Classification** | Microsoft Confidential |
| **Status** | Draft |
| **Last updated** | 2026-04-13 |

---

## 1  Purpose

Lens is an internal Microsoft tool that ingests a heterogeneous corpus (source code, documentation, diagrams, media) and produces a queryable knowledge graph together with human-readable analysis artifacts. It is designed to accelerate codebase onboarding, architectural review, and cross-team knowledge transfer within Microsoft engineering orgs.

### 1.1  Industry Context

A publicly available MIT-licensed project ("Graphify", github.com/safishamsi/graphify) demonstrates the general capability of:

- constructing a knowledge graph from mixed inputs (code, docs, images, video);
- exporting interactive HTML visualizations and summary reports;
- performing both structural and semantic extraction passes.

Lens addresses the same problem domain but is an independent, ground-up implementation governed by Microsoft's internal engineering standards. This document codifies the constraints that prevent architectural or surface-level similarity.

---

## 2  Functional Requirements

### 2.1  Ingestion

| ID | Requirement |
|---|---|
| FR-ING-01 | Accept a directory tree (local or ADO repo path) containing source files, Markdown/RST/AsciiDoc, and image assets (.png, .jpg, .svg). |
| FR-ING-02 | Support incremental re-ingestion: only reprocess files whose content hash has changed since the last run. |
| FR-ING-03 | Provide a pluggable file-type adapter registry so new languages or doc formats can be added without modifying core pipeline code. |
| FR-ING-04 | Video and binary asset support is **Phase 2**; Phase 1 focuses on text-based and image inputs only. |

### 2.2  Extraction Pipeline

| ID | Requirement |
|---|---|
| FR-EXT-01 | **Syntax-aware pass** — parse source files into ASTs using language-specific grammars (Tree-sitter) and extract declarations, call edges, import/dependency edges, and type relationships. |
| FR-EXT-02 | **Concept-mapping pass** — apply an LLM-backed extraction step to derive domain concepts, intent annotations, and cross-artifact semantic links (e.g., a README section that explains a module). |
| FR-EXT-03 | Each pass must be independently runnable and produce its own intermediate artifact so failures in one pass do not block the other. |
| FR-EXT-04 | Extraction passes must emit provenance metadata (source file, line range, model version, timestamp) for every graph element they produce. |

### 2.3  Knowledge Graph

| ID | Requirement |
|---|---|
| FR-KG-01 | The graph must be stored in an open, documented schema (see §5 — Output Schema). |
| FR-KG-02 | Support community/cluster detection to group related nodes into coherent topic areas. |
| FR-KG-03 | Expose a query interface (programmatic API; CLI query sub-command) that supports at minimum: node lookup by label, neighborhood traversal to depth N, and cluster listing. |
| FR-KG-04 | Graph must be exportable to standard formats: JSON-LD and GraphML. |

### 2.4  Reporting & Visualization

| ID | Requirement |
|---|---|
| FR-VIS-01 | Generate a self-contained interactive HTML visualization of the graph (single-file, no external CDN dependencies for air-gapped use). |
| FR-VIS-02 | Generate a structured analysis report in Markdown containing: corpus summary statistics, top-level cluster descriptions, key entity inventory, and an integrity/coverage audit section. |
| FR-VIS-03 | All output filenames must follow the naming conventions in §5.2. |

### 2.5  Integration

| ID | Requirement |
|---|---|
| FR-INT-01 | Publish a Python SDK (`microsoft-lens-sdk`) for programmatic use. |
| FR-INT-02 | Provide an Azure DevOps pipeline task for CI-triggered graph rebuilds. |
| FR-INT-03 | Optionally push the graph to an Azure Cosmos DB (Gremlin API) instance for persistent, team-shared querying. |

---

## 3  Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Process a 50 000-file monorepo in under 30 minutes on a Standard_D16s_v5 VM. |
| NFR-02 | All LLM calls must go through the Microsoft-internal Azure OpenAI gateway; no external model endpoints. |
| NFR-03 | Comply with Microsoft SDL: threat model, fuzz testing of parsers, credential-scanning of ingested content. |
| NFR-04 | Telemetry via 1DS / Geneva; no third-party analytics. |
| NFR-05 | Support Windows, Linux, and macOS (x64 and ARM64 where Python 3.11+ is available). |
| NFR-06 | All dependencies must pass Component Governance review. |

---

## 4  Non-Goals / Avoidance Constraints

These constraints exist **specifically** to ensure Lens is architecturally, nominally, and superficially distinct from any existing open-source project addressing the same domain — including the reference project "Graphify."

### 4.1  Naming & Surface Identity

| Constraint | Rationale |
|---|---|
| NC-N-01: The CLI entry point must be named `lens`, never `graphify` or any derivative. | Distinct identity. |
| NC-N-02: No output directory may be named `graphify-out`, `graphify_output`, or any variant containing "graphify." The default output directory is `.lens/artifacts/`. | Prevent output-path collision. |
| NC-N-03: The analysis report file must be named `analysis-report.md`, not `GRAPH_REPORT.md` or any `*_REPORT*` variant. | Distinct artifact naming. |
| NC-N-04: The interactive visualization file must be named `explorer.html`, not `index.html`, `graph.html`, or any name matching known third-party outputs. | Distinct artifact naming. |
| NC-N-05: The JSON graph export must be named `knowledge-graph.jsonld`, not `graph.json`, `output.json`, or any name used by reference projects. | Distinct artifact naming. |

### 4.2  Module & Package Boundaries

| Constraint | Rationale |
|---|---|
| NC-M-01: Internal package layout must use a domain-driven structure: `lens.ingest`, `lens.extract.syntax`, `lens.extract.concepts`, `lens.graph`, `lens.render`, `lens.query`. These names must not mirror the module tree of any reference project. | Architectural independence. |
| NC-M-02: No module may be named `builder`, `community`, `parser`, or `reporter` at the top level if such names exist as top-level modules in the reference project. Prefer descriptive compound names (e.g., `cluster_detector`, `report_composer`). | Prevent structural mimicry. |
| NC-M-03: The extraction pipeline must be orchestrated via a DAG-based task runner (e.g., internal `lens.pipeline.Dag`), not a linear pass list. | Architectural differentiation; also enables parallelism. |

### 4.3  CLI Command Design

| Constraint | Rationale |
|---|---|
| NC-C-01: CLI must follow a noun-verb pattern (`lens corpus ingest`, `lens graph query`, `lens report generate`), not a flat verb pattern. | Distinct UX. |
| NC-C-02: No sub-command may be named `run`, `build`, or `analyze` at the top level if those names are used by the reference project. Use `ingest`, `query`, `generate` instead. | Prevent command-name overlap. |
| NC-C-03: Configuration must be via a YAML file named `lens.config.yaml` (never `graphify.yaml`, `config.json`, `.graphifyrc`, or similar). | Distinct configuration surface. |

### 4.4  Algorithm & Approach Defaults

| Constraint | Rationale |
|---|---|
| NC-A-01: Community detection must default to the **Leiden algorithm** (not Louvain) unless benchmarking on internal corpora shows Leiden is demonstrably worse. Justification must be documented. | Independent algorithm choice; Leiden improves on Louvain's known resolution-limit issue. |
| NC-A-02: Graph storage format must default to **JSON-LD** (not plain adjacency-list JSON) to leverage W3C standards and enable interop with Microsoft Graph and RDF tooling. | Standards alignment; differentiates output schema. |
| NC-A-03: Semantic extraction must use **Azure OpenAI GPT-4o** via the internal gateway, with a structured-output JSON-schema contract — not free-form prompt-and-parse. | Microsoft-internal model path; deterministic output contract. |
| NC-A-04: Syntax-aware parsing must use **Tree-sitter** grammars loaded at runtime via a registry, not regex-based or per-language ad-hoc parsers. | Robustness; distinct implementation strategy. |

### 4.5  Documentation & Prose

| Constraint | Rationale |
|---|---|
| NC-D-01: README and doc prose must not reuse phrases from the reference project. Specifically avoid: "any input → knowledge graph," "clustered communities → HTML," or similar pipeline-arrow descriptions. | Prevent textual similarity. |
| NC-D-02: Architecture diagrams must use Microsoft Visio or Mermaid authored internally; never adapt diagrams from external projects. | IP hygiene. |
| NC-D-03: All doc examples must use Microsoft-internal sample repos (e.g., `1ES-example-service`) as demo corpora, never external repos. | Context appropriateness. |

---

## 5  Output Schema

### 5.1  Knowledge Graph Schema (`knowledge-graph.jsonld`)

```jsonc
{
  "@context": "https://schema.lens.microsoft.internal/kg/v1",
  "@graph": [
    {
      "@id": "urn:lens:node:<uuid>",
      "@type": "lens:Entity",               // or lens:Module, lens:Function, lens:Concept, …
      "lens:label": "string",
      "lens:kind": "string",
      "lens:cluster": "urn:lens:cluster:<uuid>",
      "lens:provenance": {
        "lens:sourceFile": "string",
        "lens:lineRange": [1, 42],
        "lens:extractionPass": "syntax | concepts",
        "lens:extractedAt": "ISO-8601",
        "lens:modelVersion": "string | null"
      },
      "lens:properties": {}                  // open extension map
    }
  ],
  "lens:edges": [
    {
      "@id": "urn:lens:edge:<uuid>",
      "lens:source": "urn:lens:node:<uuid>",
      "lens:target": "urn:lens:node:<uuid>",
      "lens:relation": "calls | imports | describes | contains | relatedTo",
      "lens:weight": 0.0,
      "lens:provenance": { /* same structure */ }
    }
  ],
  "lens:clusters": [
    {
      "@id": "urn:lens:cluster:<uuid>",
      "lens:label": "string",
      "lens:summary": "string",
      "lens:members": ["urn:lens:node:<uuid>"]
    }
  ],
  "lens:meta": {
    "lens:version": "1.0.0",
    "lens:generatedAt": "ISO-8601",
    "lens:corpusRoot": "string",
    "lens:fileCount": 0,
    "lens:nodeCount": 0,
    "lens:edgeCount": 0,
    "lens:clusterCount": 0
  }
}
```

### 5.2  Output File Naming Convention

| Artifact | Filename | Location |
|---|---|---|
| Knowledge graph (JSON-LD) | `knowledge-graph.jsonld` | `.lens/artifacts/` |
| Knowledge graph (GraphML) | `knowledge-graph.graphml` | `.lens/artifacts/` |
| Interactive visualization | `explorer.html` | `.lens/artifacts/` |
| Analysis report | `analysis-report.md` | `.lens/artifacts/` |
| Run metadata | `run-manifest.json` | `.lens/artifacts/` |
| Incremental state | `corpus-state.db` | `.lens/cache/` |

---

## 6  Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        lens CLI                             │
│   lens corpus ingest | lens graph query | lens report gen   │
├─────────────────────────────────────────────────────────────┤
│                   Pipeline DAG Runner                       │
│          (lens.pipeline — task scheduling, caching)         │
├────────────┬────────────┬────────────┬──────────────────────┤
│  Ingest    │  Extract   │  Graph     │  Render              │
│ ┌────────┐ │ ┌────────┐ │ ┌────────┐ │ ┌──────────────────┐ │
│ │Adapter │ │ │Syntax  │ │ │Builder │ │ │Report Composer   │ │
│ │Registry│ │ │  Pass  │ │ │        │ │ │Explorer Renderer │ │
│ └────────┘ │ ├────────┤ │ ├────────┤ │ └──────────────────┘ │
│            │ │Concept │ │ │Cluster │ │                      │
│            │ │  Pass  │ │ │Detector│ │                      │
│            │ └────────┘ │ └────────┘ │                      │
├────────────┴────────────┴────────────┴──────────────────────┤
│            Shared: Provenance · Telemetry · Config          │
└─────────────────────────────────────────────────────────────┘
```

---

## 7  Milestones

| Phase | Scope | Target |
|---|---|---|
| **Phase 1** | Ingest (text + images), syntax pass, concept pass, JSON-LD export, basic HTML explorer, analysis report | Q3 2026 |
| **Phase 2** | Video/binary ingestion, Cosmos DB push, ADO pipeline task, incremental rebuild | Q4 2026 |
| **Phase 3** | Query API + SDK GA, cross-repo graph federation, Copilot integration | Q1 2027 |

---

## 8  Similarity-Risk Review Checklist

Use this checklist before every design review or release gate. Every item must be marked **PASS** before proceeding.

### 8.1  Naming

- [ ] CLI binary/entry point is `lens`, with no "graphify" reference anywhere in help text or `--version` output.
- [ ] Default output directory is `.lens/artifacts/`, not `graphify-out` or any variant.
- [ ] No output file is named `GRAPH_REPORT.md`, `graph.json`, `index.html`, or any name known to be used by the reference project.
- [ ] Python package name is `microsoft-lens-sdk`; no PyPI or internal feed package contains "graphify."
- [ ] Config file is `lens.config.yaml`; no config file references "graphify."

### 8.2  Architecture

- [ ] Module tree follows the `lens.*` domain-driven layout defined in NC-M-01.
- [ ] Pipeline is DAG-based, not a sequential pass list.
- [ ] No top-level module shares a name with a top-level module in the reference project.
- [ ] Community detection defaults to Leiden (or deviation is documented with internal benchmark data).
- [ ] Graph serialization defaults to JSON-LD, not plain adjacency-list JSON.

### 8.3  Output Schema

- [ ] JSON-LD context URI is `schema.lens.microsoft.internal`, not any external project's namespace.
- [ ] Node/edge ID URIs use the `urn:lens:` prefix.
- [ ] Schema field names use the `lens:` namespace prefix; no field names overlap with reference project schema keys.
- [ ] Output schema version is independently tracked in `run-manifest.json`.

### 8.4  CLI & UX

- [ ] CLI uses noun-verb command structure (`lens corpus ingest`), not flat verbs.
- [ ] No sub-command is named `run`, `build`, or `analyze` (or any command name known from the reference project).
- [ ] `--help` text and error messages are authored internally; grep confirms zero phrases borrowed from reference docs.

### 8.5  Documentation & Prose

- [ ] README does not contain the phrases "any input → knowledge graph," "clustered communities → HTML," or pipeline-arrow shorthand from the reference project.
- [ ] All architecture diagrams are original (authored in Mermaid or Visio by the team).
- [ ] Example corpora reference Microsoft-internal sample repos, not external projects.
- [ ] No copied sentences or near-duplicates found by running a diff/plagiarism check against reference project docs.

### 8.6  Dependencies & Licensing

- [ ] No runtime dependency pulls in the reference project's package.
- [ ] Component Governance scan confirms no transitive dependency on the reference project.
- [ ] LICENSE file declares Microsoft-internal proprietary terms; no MIT license text carried over.

---

*End of document.*
