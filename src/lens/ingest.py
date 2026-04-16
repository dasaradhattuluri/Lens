"""Corpus ingestion — file discovery, hashing, and adapter dispatch."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Protocol

from lens.models import CorpusFile


# ---------------------------------------------------------------------------
# Adapter protocol — one per file type family
# ---------------------------------------------------------------------------

class FileAdapter(Protocol):
    """Interface that all format adapters must satisfy."""

    extensions: frozenset[str]

    def can_handle(self, path: Path) -> bool: ...
    def read(self, path: Path) -> CorpusFile: ...


# ---------------------------------------------------------------------------
# Built-in adapters
# ---------------------------------------------------------------------------

class PlainTextAdapter:
    """Handles source code and documentation files."""

    extensions = frozenset({
        ".py", ".js", ".ts", ".java", ".cs", ".go", ".rs", ".c", ".cpp", ".h",
        ".md", ".rst", ".txt", ".yaml", ".yml", ".json", ".toml", ".xml",
        ".html", ".css", ".sh", ".ps1", ".bat",
    })

    _LANG_MAP: dict[str, str] = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".java": "java", ".cs": "csharp", ".go": "go", ".rs": "rust",
        ".c": "c", ".cpp": "cpp", ".h": "c", ".md": "markdown",
        ".rst": "rst", ".txt": "text", ".yaml": "yaml", ".yml": "yaml",
        ".json": "json", ".toml": "toml", ".xml": "xml", ".html": "html",
        ".css": "css", ".sh": "shell", ".ps1": "powershell", ".bat": "batch",
    }

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def read(self, path: Path) -> CorpusFile:
        content = path.read_text(encoding="utf-8", errors="replace")
        return CorpusFile(
            path=str(path),
            content=content,
            language=self._LANG_MAP.get(path.suffix.lower()),
            content_hash=_hash_content(content),
        )


class ImageAdapter:
    """Placeholder adapter for image files (content stored as empty; metadata only)."""

    extensions = frozenset({".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"})

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def read(self, path: Path) -> CorpusFile:
        raw = path.read_bytes()
        return CorpusFile(
            path=str(path),
            content="",
            language="image",
            content_hash=hashlib.sha256(raw).hexdigest(),
        )


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

class AdapterRegistry:
    """Manages file-type adapters and dispatches reads."""

    def __init__(self) -> None:
        self._adapters: list[FileAdapter] = []

    def register(self, adapter: FileAdapter) -> None:
        self._adapters.append(adapter)

    def find_adapter(self, path: Path) -> FileAdapter | None:
        for adapter in self._adapters:
            if adapter.can_handle(path):
                return adapter
        return None

    @classmethod
    def with_defaults(cls) -> "AdapterRegistry":
        registry = cls()
        registry.register(PlainTextAdapter())
        registry.register(ImageAdapter())
        return registry


# ---------------------------------------------------------------------------
# Corpus scanner
# ---------------------------------------------------------------------------

_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "__pycache__", "node_modules",
    ".lens", ".venv", "venv", "env", ".tox",
})


def scan_corpus(
    root: str | Path,
    registry: AdapterRegistry | None = None,
    cache_dir: str | Path | None = None,
    incremental: bool = False,
) -> list[CorpusFile]:
    """Walk *root* and return a `CorpusFile` for every recognised file.

    When *incremental* is True and *cache_dir* is provided, only files
    whose content hash differs from the previous run are returned.  The
    hash state is persisted in ``corpus-state.db`` inside *cache_dir*.
    """
    root = Path(root).resolve()
    if registry is None:
        registry = AdapterRegistry.with_defaults()

    state: _CorpusState | None = None
    if incremental and cache_dir is not None:
        state = _CorpusState(Path(cache_dir))

    results: list[CorpusFile] = []
    for item in sorted(root.rglob("*")):
        if item.is_dir():
            continue
        # skip hidden / vendor dirs
        if any(part in _SKIP_DIRS for part in item.parts):
            continue
        adapter = registry.find_adapter(item)
        if adapter is not None:
            cf = adapter.read(item)
            if state is not None and state.is_unchanged(cf.path, cf.content_hash):
                continue
            results.append(cf)

    # Persist hashes after a successful scan
    if state is not None:
        for cf in results:
            state.update(cf.path, cf.content_hash)
        state.close()

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Incremental state store (SQLite)
# ---------------------------------------------------------------------------

class _CorpusState:
    """SQLite-backed hash store for incremental ingestion."""

    def __init__(self, cache_dir: Path) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(cache_dir / "corpus-state.db"))
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS file_hashes "
            "(path TEXT PRIMARY KEY, content_hash TEXT NOT NULL)"
        )
        self._db.commit()

    def is_unchanged(self, path: str, content_hash: str) -> bool:
        row = self._db.execute(
            "SELECT content_hash FROM file_hashes WHERE path = ?", (path,)
        ).fetchone()
        return row is not None and row[0] == content_hash

    def update(self, path: str, content_hash: str) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO file_hashes (path, content_hash) VALUES (?, ?)",
            (path, content_hash),
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()
