"""Shared domain types for the Lens knowledge-graph toolkit."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Provenance:
    """Tracks where a graph element was extracted from."""

    source_file: str
    line_range: tuple[int, int] | None = None
    extraction_pass: str = "unknown"
    extracted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    model_version: str | None = None


# ---------------------------------------------------------------------------
# Node / Edge kinds
# ---------------------------------------------------------------------------

class NodeKind(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    VARIABLE = "variable"
    CONCEPT = "concept"
    DOCUMENT = "document"
    FILE = "file"


class EdgeRelation(str, Enum):
    CALLS = "calls"
    IMPORTS = "imports"
    DESCRIBES = "describes"
    CONTAINS = "contains"
    RELATED_TO = "relatedTo"
    INHERITS = "inherits"


# ---------------------------------------------------------------------------
# Core graph elements
# ---------------------------------------------------------------------------

@dataclass
class KGNode:
    """A single node in the knowledge graph."""

    label: str
    kind: NodeKind
    provenance: Provenance
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    cluster_id: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class KGEdge:
    """A directed edge between two nodes."""

    source_id: str
    target_id: str
    relation: EdgeRelation
    provenance: Provenance
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    weight: float = 1.0


@dataclass
class KGCluster:
    """A community / cluster of nodes."""

    label: str
    summary: str
    member_ids: list[str] = field(default_factory=list)
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Corpus-level types
# ---------------------------------------------------------------------------

@dataclass
class CorpusFile:
    """Represents a single ingested file."""

    path: str
    content: str
    language: str | None = None
    content_hash: str = ""
