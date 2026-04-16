"""Knowledge-graph assembly, clustering, and serialisation.

Consumes extraction results, builds a NetworkX graph, runs cluster
detection (Leiden by default, with a greedy-modularity fallback when
``leidenalg`` is not installed), and exports to JSON-LD / GraphML.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, SubElement, ElementTree

import networkx as nx

from lens.models import (
    EdgeRelation,
    KGCluster,
    KGEdge,
    KGNode,
    NodeKind,
    Provenance,
)

# ---------------------------------------------------------------------------
# Knowledge-graph container
# ---------------------------------------------------------------------------


class KnowledgeGraph:
    """In-memory knowledge graph backed by NetworkX."""

    def __init__(self) -> None:
        self._nx: nx.DiGraph = nx.DiGraph()
        self.nodes: dict[str, KGNode] = {}
        self.edges: dict[str, KGEdge] = {}
        self.clusters: dict[str, KGCluster] = {}

    # -- Mutation -----------------------------------------------------------

    def add_node(self, node: KGNode) -> None:
        self.nodes[node.uid] = node
        self._nx.add_node(node.uid, label=node.label, kind=node.kind.value)

    def add_edge(self, edge: KGEdge) -> None:
        self.edges[edge.uid] = edge
        self._nx.add_edge(
            edge.source_id,
            edge.target_id,
            key=edge.uid,
            relation=edge.relation.value,
            weight=edge.weight,
        )

    # -- Query helpers ------------------------------------------------------

    def neighbors(self, node_id: str, depth: int = 1) -> list[str]:
        """Return node ids reachable within *depth* hops."""
        visited: set[str] = set()
        frontier: set[str] = {node_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                if nid in visited:
                    continue
                visited.add(nid)
                next_frontier.update(self._nx.successors(nid))
                next_frontier.update(self._nx.predecessors(nid))
            frontier = next_frontier - visited
        visited.update(frontier)
        visited.discard(node_id)
        return sorted(visited)

    def find_by_label(self, label: str) -> list[KGNode]:
        return [n for n in self.nodes.values() if n.label == label]

    def subgraph(self, node_ids: list[str]) -> "KnowledgeGraph":
        """Return a new KnowledgeGraph containing only the given node ids and
        the edges between them."""
        sg = KnowledgeGraph()
        id_set = set(node_ids)
        for nid in node_ids:
            if nid in self.nodes:
                sg.add_node(self.nodes[nid])
        for edge in self.edges.values():
            if edge.source_id in id_set and edge.target_id in id_set:
                sg.add_edge(edge)
        return sg

    # -- Cluster detection --------------------------------------------------

    def detect_clusters(self, algorithm: str = "leiden", resolution: float = 1.0) -> None:
        """Run community detection and populate ``self.clusters``."""
        undirected = self._nx.to_undirected()

        if algorithm == "leiden":
            partition = self._leiden_partition(undirected, resolution)
        else:
            partition = self._greedy_partition(undirected)

        # Build KGCluster objects from partition
        community_map: dict[int, list[str]] = {}
        for nid, comm in partition.items():
            community_map.setdefault(comm, []).append(nid)

        self.clusters.clear()
        for comm_id, members in community_map.items():
            cluster = KGCluster(
                label=f"cluster-{comm_id}",
                summary=f"Auto-detected community {comm_id} ({len(members)} members)",
                member_ids=members,
            )
            self.clusters[cluster.uid] = cluster
            for mid in members:
                if mid in self.nodes:
                    self.nodes[mid].cluster_id = cluster.uid

    @staticmethod
    def _leiden_partition(g: nx.Graph, resolution: float) -> dict[str, int]:
        try:
            import leidenalg  # type: ignore[import-untyped]
            import igraph as ig  # type: ignore[import-untyped]

            mapping = {n: i for i, n in enumerate(g.nodes())}
            reverse = {i: n for n, i in mapping.items()}
            ig_graph = ig.Graph(
                n=len(mapping),
                edges=[(mapping[u], mapping[v]) for u, v in g.edges()],
                directed=False,
            )
            part = leidenalg.find_partition(
                ig_graph,
                leidenalg.CPMVertexPartition,
                resolution_parameter=resolution,
            )
            return {reverse[i]: comm for i, comm in enumerate(part.membership)}
        except ImportError:
            return KnowledgeGraph._greedy_partition(g)

    @staticmethod
    def _greedy_partition(g: nx.Graph) -> dict[str, int]:
        if g.number_of_nodes() == 0:
            return {}
        communities = nx.community.greedy_modularity_communities(g)
        partition: dict[str, int] = {}
        for idx, comm in enumerate(communities):
            for nid in comm:
                partition[nid] = idx
        return partition

    # -- Serialisation: JSON-LD ---------------------------------------------

    def to_jsonld(self, corpus_root: str = ".") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "@context": "https://schema.lens.microsoft.internal/kg/v1",
            "@graph": [self._node_to_jsonld(n) for n in self.nodes.values()],
            "lens:edges": [self._edge_to_jsonld(e) for e in self.edges.values()],
            "lens:clusters": [self._cluster_to_jsonld(c) for c in self.clusters.values()],
            "lens:meta": {
                "lens:version": "1.0.0",
                "lens:generatedAt": now,
                "lens:corpusRoot": corpus_root,
                "lens:fileCount": len({n.provenance.source_file for n in self.nodes.values()}),
                "lens:nodeCount": len(self.nodes),
                "lens:edgeCount": len(self.edges),
                "lens:clusterCount": len(self.clusters),
            },
        }

    def save_jsonld(self, path: str | Path, corpus_root: str = ".") -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_jsonld(corpus_root), fh, indent=2)

    # -- Serialisation: GraphML ---------------------------------------------

    def save_graphml(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        root = Element("graphml")
        root.set("xmlns", "http://graphml.graphstruct.org/xmlns")
        graph_el = SubElement(root, "graph", id="lens-kg", edgedefault="directed")

        for node in self.nodes.values():
            n_el = SubElement(graph_el, "node", id=node.uid)
            _data(n_el, "label", node.label)
            _data(n_el, "kind", node.kind.value)

        for edge in self.edges.values():
            SubElement(
                graph_el, "edge",
                id=edge.uid, source=edge.source_id, target=edge.target_id,
            )

        ElementTree(root).write(str(path), encoding="unicode", xml_declaration=True)

    # -- Private helpers ----------------------------------------------------

    @staticmethod
    def _node_to_jsonld(n: KGNode) -> dict[str, Any]:
        return {
            "@id": f"urn:lens:node:{n.uid}",
            "@type": f"lens:{n.kind.value.title()}",
            "lens:label": n.label,
            "lens:kind": n.kind.value,
            "lens:cluster": f"urn:lens:cluster:{n.cluster_id}" if n.cluster_id else None,
            "lens:provenance": _prov_dict(n.provenance),
            "lens:properties": n.properties,
        }

    @staticmethod
    def _edge_to_jsonld(e: KGEdge) -> dict[str, Any]:
        return {
            "@id": f"urn:lens:edge:{e.uid}",
            "lens:source": f"urn:lens:node:{e.source_id}",
            "lens:target": f"urn:lens:node:{e.target_id}",
            "lens:relation": e.relation.value,
            "lens:weight": e.weight,
            "lens:provenance": _prov_dict(e.provenance),
        }

    @staticmethod
    def _cluster_to_jsonld(c: KGCluster) -> dict[str, Any]:
        return {
            "@id": f"urn:lens:cluster:{c.uid}",
            "lens:label": c.label,
            "lens:summary": c.summary,
            "lens:members": [f"urn:lens:node:{m}" for m in c.member_ids],
        }


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _prov_dict(p: Provenance) -> dict[str, Any]:
    return {
        "lens:sourceFile": p.source_file,
        "lens:lineRange": list(p.line_range) if p.line_range else None,
        "lens:extractionPass": p.extraction_pass,
        "lens:extractedAt": p.extracted_at,
        "lens:modelVersion": p.model_version,
    }


def _data(parent: Element, key: str, value: str) -> None:
    d = SubElement(parent, "data", key=key)
    d.text = value
