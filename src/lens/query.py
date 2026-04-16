"""REST query API for the Lens knowledge graph.

Exposes three endpoints:
  GET /neighbors?node_id=…&depth=…
  GET /path?source=…&target=…
  GET /subgraph?node_ids=…
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query

from lens.graph import KnowledgeGraph

# ---------------------------------------------------------------------------
# Factory — creates a FastAPI app bound to a specific KnowledgeGraph instance
# ---------------------------------------------------------------------------


def create_app(kg: KnowledgeGraph) -> FastAPI:
    app = FastAPI(title="Lens Query API", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/nodes")
    def list_nodes(
        label: str | None = Query(None),
        kind: str | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        results = list(kg.nodes.values())
        if label:
            results = [n for n in results if n.label == label]
        if kind:
            results = [n for n in results if n.kind.value == kind]
        return [_node_summary(n) for n in results[:limit]]

    @app.get("/neighbors")
    def neighbors(
        node_id: str = Query(...),
        depth: int = Query(1, ge=1, le=5),
    ) -> dict[str, Any]:
        if node_id not in kg.nodes:
            raise HTTPException(404, f"Node {node_id!r} not found")
        ids = kg.neighbors(node_id, depth)
        return {
            "origin": node_id,
            "depth": depth,
            "neighbors": [_node_summary(kg.nodes[nid]) for nid in ids if nid in kg.nodes],
        }

    @app.get("/path")
    def shortest_path(
        source: str = Query(...),
        target: str = Query(...),
    ) -> dict[str, Any]:
        if source not in kg.nodes:
            raise HTTPException(404, f"Source node {source!r} not found")
        if target not in kg.nodes:
            raise HTTPException(404, f"Target node {target!r} not found")
        import networkx as nx
        try:
            path_ids = nx.shortest_path(kg._nx, source, target)
        except nx.NetworkXNoPath:
            return {"source": source, "target": target, "path": None}
        return {
            "source": source,
            "target": target,
            "path": [_node_summary(kg.nodes[nid]) for nid in path_ids if nid in kg.nodes],
        }

    @app.get("/subgraph")
    def subgraph(
        node_ids: str = Query(..., description="Comma-separated node IDs"),
    ) -> dict[str, Any]:
        ids = [nid.strip() for nid in node_ids.split(",") if nid.strip()]
        missing = [nid for nid in ids if nid not in kg.nodes]
        if missing:
            raise HTTPException(404, f"Nodes not found: {missing}")
        sg = kg.subgraph(ids)
        return sg.to_jsonld()

    @app.get("/clusters")
    def list_clusters() -> list[dict[str, Any]]:
        return [
            {
                "id": c.uid,
                "label": c.label,
                "summary": c.summary,
                "member_count": len(c.member_ids),
            }
            for c in kg.clusters.values()
        ]

    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node_summary(n: Any) -> dict[str, Any]:
    return {
        "id": n.uid,
        "label": n.label,
        "kind": n.kind.value,
        "cluster": n.cluster_id,
    }
