"""GitHub Copilot / VS Code integration installer for Lens.

Writes the files that make Copilot (and other VS Code agents) aware of
the Lens knowledge graph so they consult it before raw file search:

  AGENTS.md                             — agent-level instructions
  .github/copilot-instructions.md       — Copilot-specific instructions
  .vscode/settings.json                 — search.exclude for .lens/cache
"""

from __future__ import annotations

import json
from pathlib import Path

_LENS_TAG = "# Lens Knowledge Graph"

# ---------------------------------------------------------------------------
# File contents
# ---------------------------------------------------------------------------

_AGENTS_MD = """\
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
"""

_COPILOT_INSTRUCTIONS = """\
When answering questions about this codebase, check if
`.lens/artifacts/analysis-report.md` exists. If it does, read it first
to understand the module structure and key entities before searching files.

The knowledge graph in `.lens/artifacts/knowledge-graph.jsonld` contains
node relationships (calls, imports, contains, describes, inherits) that
can help you navigate the architecture more accurately than keyword search.
"""

_VSCODE_SETTINGS_PATCH = {
    "search.exclude": {
        "**/.lens/cache": True,
    },
}


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

def install_copilot(repo_root: Path | None = None) -> list[tuple[str, str]]:
    """Write Copilot integration files. Returns [(path, action), ...]."""
    root = (repo_root or Path.cwd()).resolve()
    results: list[tuple[str, str]] = []

    # AGENTS.md
    agents_path = root / "AGENTS.md"
    if agents_path.exists():
        content = agents_path.read_text(encoding="utf-8", errors="replace")
        if _LENS_TAG not in content:
            with open(agents_path, "a", encoding="utf-8") as fh:
                fh.write("\n\n" + _AGENTS_MD)
            results.append((str(agents_path), "appended"))
        else:
            results.append((str(agents_path), "already present"))
    else:
        agents_path.write_text(_AGENTS_MD, encoding="utf-8")
        results.append((str(agents_path), "created"))

    # .github/copilot-instructions.md
    gh_dir = root / ".github"
    gh_dir.mkdir(exist_ok=True)
    ci_path = gh_dir / "copilot-instructions.md"
    if ci_path.exists():
        content = ci_path.read_text(encoding="utf-8", errors="replace")
        if "analysis-report.md" not in content:
            with open(ci_path, "a", encoding="utf-8") as fh:
                fh.write("\n\n" + _COPILOT_INSTRUCTIONS)
            results.append((str(ci_path), "appended"))
        else:
            results.append((str(ci_path), "already present"))
    else:
        ci_path.write_text(_COPILOT_INSTRUCTIONS, encoding="utf-8")
        results.append((str(ci_path), "created"))

    # .vscode/settings.json — merge search.exclude
    vsc_dir = root / ".vscode"
    vsc_dir.mkdir(exist_ok=True)
    settings_path = vsc_dir / "settings.json"
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            existing = {}
    else:
        existing = {}

    se = existing.setdefault("search.exclude", {})
    changed = False
    for k, v in _VSCODE_SETTINGS_PATCH["search.exclude"].items():
        if k not in se:
            se[k] = v
            changed = True
    if changed:
        settings_path.write_text(
            json.dumps(existing, indent=4) + "\n", encoding="utf-8"
        )
        results.append((str(settings_path), "updated"))
    else:
        results.append((str(settings_path), "already present"))

    return results


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

def uninstall_copilot(repo_root: Path | None = None) -> list[str]:
    """Remove Lens-specific Copilot files. Returns list of removed paths."""
    root = (repo_root or Path.cwd()).resolve()
    removed: list[str] = []

    agents_path = root / "AGENTS.md"
    if agents_path.exists():
        content = agents_path.read_text(encoding="utf-8", errors="replace")
        if _LENS_TAG in content:
            # If the whole file is ours, delete it; otherwise strip our section
            if content.strip().startswith(_LENS_TAG):
                agents_path.unlink()
                removed.append(str(agents_path))

    ci_path = root / ".github" / "copilot-instructions.md"
    if ci_path.exists():
        content = ci_path.read_text(encoding="utf-8", errors="replace")
        if "analysis-report.md" in content and "lens" in content.lower():
            ci_path.unlink()
            removed.append(str(ci_path))

    return removed
