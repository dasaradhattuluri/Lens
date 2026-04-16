"""Lens CLI — noun-verb command structure.

Commands:
  lens corpus ingest <path>
  lens graph query --label <name>
  lens graph export [--format jsonld|graphml]
  lens report generate
  lens api serve
  lens hook install / uninstall / status
  lens copilot install / uninstall
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from lens.config import load_config


@click.group()
@click.version_option(version="0.1.0", prog_name="lens")
@click.option("--config", "config_path", default=None, type=click.Path(), help="Path to lens.config.yaml")
@click.pass_context
def main(ctx: click.Context, config_path: str | None) -> None:
    """Lens — knowledge-graph toolkit for codebases."""
    ctx.ensure_object(dict)
    ctx.obj["cfg"] = load_config(config_path)


# ── corpus ─────────────────────────────────────────────────────────────────

@main.group()
def corpus() -> None:
    """Corpus management commands."""


@corpus.command("ingest")
@click.argument("path", default=".")
@click.option("--update", is_flag=True, default=False, help="Incremental update — skip unchanged files.")
@click.option("--full", is_flag=True, default=False, help="Force full re-scan (ignore cache).")
@click.pass_context
def corpus_ingest(ctx: click.Context, path: str, update: bool, full: bool) -> None:
    """Ingest a directory tree into the knowledge graph."""
    from lens.ingest import scan_corpus
    from lens.extract.syntax import extract_syntax
    from lens.extract.concepts import extract_concepts
    from lens.graph import KnowledgeGraph
    from lens.render import render_explorer_html, render_analysis_report
    from lens.pipeline import Dag

    cfg = ctx.obj["cfg"]
    corpus_root = Path(path).resolve()
    output_dir = Path(cfg.output_dir)
    incremental = update and not full

    # Build pipeline DAG
    dag = Dag()

    def step_ingest(context: dict) -> None:
        mode = "incremental" if incremental else "full"
        click.echo(f"Scanning corpus at {corpus_root} ({mode}) …")
        context["files"] = scan_corpus(
            corpus_root,
            cache_dir=cfg.cache_dir if incremental else None,
            incremental=incremental,
        )
        click.echo(f"  Found {len(context['files'])} files to process.")

    def step_syntax(context: dict) -> None:
        if not cfg.extraction.syntax:
            context["syntax_result"] = None
            return
        click.echo("Running syntax-aware extraction …")
        context["syntax_result"] = extract_syntax(context["files"])
        click.echo(
            f"  {len(context['syntax_result'].nodes)} nodes, "
            f"{len(context['syntax_result'].edges)} edges."
        )

    def step_concepts(context: dict) -> None:
        if not cfg.extraction.concepts:
            context["concept_result"] = None
            return
        click.echo("Running concept-mapping extraction …")
        context["concept_result"] = extract_concepts(context["files"])
        click.echo(
            f"  {len(context['concept_result'].nodes)} nodes, "
            f"{len(context['concept_result'].edges)} edges."
        )

    def step_assemble(context: dict) -> None:
        click.echo("Assembling knowledge graph …")
        kg = KnowledgeGraph()
        for res in (context.get("syntax_result"), context.get("concept_result")):
            if res is None:
                continue
            for n in res.nodes:
                kg.add_node(n)
            for e in res.edges:
                kg.add_edge(e)
        kg.detect_clusters(cfg.cluster.algorithm, cfg.cluster.resolution)
        context["kg"] = kg
        click.echo(
            f"  {len(kg.nodes)} nodes, {len(kg.edges)} edges, "
            f"{len(kg.clusters)} clusters."
        )

    def step_export(context: dict) -> None:
        kg: KnowledgeGraph = context["kg"]
        kg.save_jsonld(output_dir / "knowledge-graph.jsonld", str(corpus_root))
        kg.save_graphml(output_dir / "knowledge-graph.graphml")
        click.echo(f"Exported graph to {output_dir}")

    def step_render(context: dict) -> None:
        kg: KnowledgeGraph = context["kg"]
        render_explorer_html(kg, output_dir / "explorer.html", str(corpus_root))
        render_analysis_report(kg, output_dir / "analysis-report.md", str(corpus_root))
        click.echo("Generated explorer.html and analysis-report.md")

    dag.add_task("ingest", step_ingest)
    dag.add_task("syntax", step_syntax, depends_on=["ingest"])
    dag.add_task("concepts", step_concepts, depends_on=["ingest"])
    dag.add_task("assemble", step_assemble, depends_on=["syntax", "concepts"])
    dag.add_task("export", step_export, depends_on=["assemble"])
    dag.add_task("render", step_render, depends_on=["assemble"])

    dag.run()
    click.echo("Done.")


# ── graph ──────────────────────────────────────────────────────────────────

@main.group()
def graph() -> None:
    """Graph query and export commands."""


@graph.command("query")
@click.option("--label", required=True, help="Node label to search for.")
@click.option("--depth", default=1, help="Neighbourhood traversal depth.")
@click.pass_context
def graph_query(ctx: click.Context, label: str, depth: int) -> None:
    """Look up a node and its neighbourhood."""
    cfg = ctx.obj["cfg"]
    jsonld_path = Path(cfg.output_dir) / "knowledge-graph.jsonld"
    if not jsonld_path.exists():
        click.echo("No graph found. Run `lens corpus ingest` first.", err=True)
        sys.exit(1)

    from lens.graph import KnowledgeGraph
    kg = _load_graph(jsonld_path)
    matches = kg.find_by_label(label)
    if not matches:
        click.echo(f"No nodes matching label '{label}'.")
        return
    for node in matches:
        nbrs = kg.neighbors(node.uid, depth)
        click.echo(f"Node: {node.label} ({node.kind.value})  id={node.uid}")
        click.echo(f"  Neighbours (depth {depth}): {len(nbrs)}")
        for nid in nbrs[:15]:
            n = kg.nodes.get(nid)
            if n:
                click.echo(f"    - {n.label} ({n.kind.value})")


@graph.command("export")
@click.option("--format", "fmt", type=click.Choice(["jsonld", "graphml"]), default="jsonld")
@click.pass_context
def graph_export(ctx: click.Context, fmt: str) -> None:
    """Re-export the graph in a specific format."""
    cfg = ctx.obj["cfg"]
    jsonld_path = Path(cfg.output_dir) / "knowledge-graph.jsonld"
    if not jsonld_path.exists():
        click.echo("No graph found. Run `lens corpus ingest` first.", err=True)
        sys.exit(1)
    kg = _load_graph(jsonld_path)
    output_dir = Path(cfg.output_dir)
    if fmt == "jsonld":
        kg.save_jsonld(output_dir / "knowledge-graph.jsonld")
    else:
        kg.save_graphml(output_dir / "knowledge-graph.graphml")
    click.echo(f"Exported to {output_dir / f'knowledge-graph.{fmt}'}")


# ── report ─────────────────────────────────────────────────────────────────

@main.group()
def report() -> None:
    """Report generation commands."""


@report.command("generate")
@click.pass_context
def report_generate(ctx: click.Context) -> None:
    """Regenerate analysis report from existing graph."""
    cfg = ctx.obj["cfg"]
    jsonld_path = Path(cfg.output_dir) / "knowledge-graph.jsonld"
    if not jsonld_path.exists():
        click.echo("No graph found. Run `lens corpus ingest` first.", err=True)
        sys.exit(1)
    from lens.render import render_analysis_report, render_explorer_html

    kg = _load_graph(jsonld_path)
    output_dir = Path(cfg.output_dir)
    render_analysis_report(kg, output_dir / "analysis-report.md")
    render_explorer_html(kg, output_dir / "explorer.html")
    click.echo("Reports regenerated.")


# ── api ────────────────────────────────────────────────────────────────────

@main.group()
def api() -> None:
    """Query API management."""


@api.command("serve")
@click.pass_context
def api_serve(ctx: click.Context) -> None:
    """Start the REST query API server."""
    import uvicorn
    from lens.query import create_app

    cfg = ctx.obj["cfg"]
    jsonld_path = Path(cfg.output_dir) / "knowledge-graph.jsonld"
    if not jsonld_path.exists():
        click.echo("No graph found. Run `lens corpus ingest` first.", err=True)
        sys.exit(1)

    kg = _load_graph(jsonld_path)
    app = create_app(kg)
    click.echo(f"Starting Lens query API on {cfg.api.host}:{cfg.api.port}")
    uvicorn.run(app, host=cfg.api.host, port=cfg.api.port)


# ── hook ───────────────────────────────────────────────────────────────────

@main.group()
def hook() -> None:
    """Git hook management."""


@hook.command("install")
def hook_install() -> None:
    """Install post-commit and post-checkout git hooks."""
    from lens.hooks import install_hooks
    try:
        paths = install_hooks()
        for p in paths:
            click.echo(f"  Installed: {p}")
        click.echo("Git hooks installed. The graph will rebuild on commit and checkout.")
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    except FileExistsError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@hook.command("uninstall")
def hook_uninstall() -> None:
    """Remove Lens git hooks."""
    from lens.hooks import uninstall_hooks
    try:
        paths = uninstall_hooks()
        if paths:
            for p in paths:
                click.echo(f"  Removed: {p}")
        else:
            click.echo("No Lens hooks found to remove.")
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@hook.command("status")
def hook_status_cmd() -> None:
    """Show git hook status."""
    from lens.hooks import hook_status
    for name, status in hook_status().items():
        click.echo(f"  {name}: {status}")


# ── install (top-level one-step setup) ─────────────────────────────────────

@main.command("install")
@click.argument("path", default=".")
@click.option("--no-ingest", is_flag=True, default=False, help="Skip automatic graph build after setup.")
def install_cmd(path: str, no_ingest: bool) -> None:
    """One-step setup: enable Lens in a workspace and build the graph.

    Installs Copilot integration (AGENTS.md, copilot-instructions), git hooks,
    and then automatically builds the knowledge graph — all in one command.

    \b
    Example:
      lens install              # set up + build graph for current dir
      lens install ./my-repo    # set up + build graph for another repo
      lens install --no-ingest  # set up only, skip graph build
    """
    from lens.copilot_integration import install_copilot
    from lens.hooks import install_hooks

    target = Path(path).resolve()

    click.echo(f"Setting up Lens in {target} …\n")

    # 1. Copilot integration
    click.echo("  [1/3] Copilot integration")
    for fpath, action in install_copilot(target):
        click.echo(f"         {action}: {fpath}")

    # 2. Git hooks (best-effort — repo may not be a git repo yet)
    click.echo("  [2/3] Git hooks")
    try:
        for fpath in install_hooks(target):
            click.echo(f"         installed: {fpath}")
    except FileNotFoundError:
        click.echo("         skipped (not a git repository)")
    except FileExistsError as exc:
        click.echo(f"         skipped ({exc})")

    # 3. Build the knowledge graph
    if no_ingest:
        click.echo("  [3/3] Graph build skipped (--no-ingest)")
        click.echo(
            "\nSetup complete.  Run `lens corpus ingest .` when ready to build the graph."
        )
    else:
        click.echo("  [3/3] Building knowledge graph …")
        ctx = click.get_current_context()
        ctx.invoke(corpus_ingest, path=path, update=False, full=False)
        click.echo(
            "\nDone. Open .lens/artifacts/explorer.html to explore the graph."
        )


# ── copilot ────────────────────────────────────────────────────────────────

@main.group()
def copilot() -> None:
    """GitHub Copilot integration management."""


@copilot.command("install")
def copilot_install() -> None:
    """Install Copilot integration files (AGENTS.md, instructions, skill)."""
    from lens.copilot_integration import install_copilot
    results = install_copilot()
    for path, action in results:
        click.echo(f"  {action}: {path}")
    click.echo("Copilot integration installed. Copilot will now consult the Lens graph.")


@copilot.command("uninstall")
def copilot_uninstall() -> None:
    """Remove Copilot integration files."""
    from lens.copilot_integration import uninstall_copilot
    results = uninstall_copilot()
    if results:
        for path in results:
            click.echo(f"  Removed: {path}")
    else:
        click.echo("No Lens Copilot files found.")


# ── helpers ────────────────────────────────────────────────────────────────

def _load_graph(jsonld_path: Path) -> "KnowledgeGraph":
    """Reconstruct a KnowledgeGraph from a saved JSON-LD file."""
    from lens.graph import KnowledgeGraph
    from lens.models import KGNode, KGEdge, NodeKind, EdgeRelation, Provenance

    with open(jsonld_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    kg = KnowledgeGraph()

    for raw in data.get("@graph", []):
        prov_raw = raw.get("lens:provenance", {})
        lr = prov_raw.get("lens:lineRange")
        prov = Provenance(
            source_file=prov_raw.get("lens:sourceFile", ""),
            line_range=tuple(lr) if lr else None,
            extraction_pass=prov_raw.get("lens:extractionPass", "unknown"),
            extracted_at=prov_raw.get("lens:extractedAt", ""),
            model_version=prov_raw.get("lens:modelVersion"),
        )
        uid = raw["@id"].replace("urn:lens:node:", "")
        kind_str = raw.get("lens:kind", "concept")
        try:
            kind = NodeKind(kind_str)
        except ValueError:
            kind = NodeKind.CONCEPT
        cluster_raw = raw.get("lens:cluster")
        cluster_id = cluster_raw.replace("urn:lens:cluster:", "") if cluster_raw else None
        node = KGNode(
            label=raw.get("lens:label", ""),
            kind=kind,
            provenance=prov,
            uid=uid,
            cluster_id=cluster_id,
            properties=raw.get("lens:properties", {}),
        )
        kg.add_node(node)

    for raw in data.get("lens:edges", []):
        prov_raw = raw.get("lens:provenance", {})
        lr = prov_raw.get("lens:lineRange")
        prov = Provenance(
            source_file=prov_raw.get("lens:sourceFile", ""),
            line_range=tuple(lr) if lr else None,
            extraction_pass=prov_raw.get("lens:extractionPass", "unknown"),
            extracted_at=prov_raw.get("lens:extractedAt", ""),
            model_version=prov_raw.get("lens:modelVersion"),
        )
        uid = raw["@id"].replace("urn:lens:edge:", "")
        source_id = raw["lens:source"].replace("urn:lens:node:", "")
        target_id = raw["lens:target"].replace("urn:lens:node:", "")
        relation_str = raw.get("lens:relation", "relatedTo")
        try:
            relation = EdgeRelation(relation_str)
        except ValueError:
            relation = EdgeRelation.RELATED_TO
        edge = KGEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            provenance=prov,
            uid=uid,
            weight=raw.get("lens:weight", 1.0),
        )
        kg.add_edge(edge)

    return kg
