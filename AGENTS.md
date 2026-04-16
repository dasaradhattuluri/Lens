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
- `lens corpus ingest . --update` — incremental update (changed files only)
- `lens graph query --label <name>` — look up a node and its neighbours
- `lens report generate` — regenerate the analysis report
- `lens api serve` — start the REST query API on port 8400
