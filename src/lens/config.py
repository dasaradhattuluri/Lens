"""Configuration loader for Lens."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ExtractionConfig:
    syntax: bool = True
    concepts: bool = True


@dataclass
class ClusterConfig:
    algorithm: str = "leiden"
    resolution: float = 1.0


@dataclass
class ApiConfig:
    host: str = "127.0.0.1"
    port: int = 8400


@dataclass
class LensConfig:
    corpus_root: str = "."
    output_dir: str = ".lens/artifacts"
    cache_dir: str = ".lens/cache"
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    cluster: ClusterConfig = field(default_factory=ClusterConfig)
    api: ApiConfig = field(default_factory=ApiConfig)


def load_config(config_path: str | Path | None = None) -> LensConfig:
    """Load configuration from a YAML file, falling back to defaults."""
    if config_path is None:
        config_path = Path(os.getcwd()) / "lens.config.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        return LensConfig()

    with open(config_path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    ext_raw = raw.get("extraction", {})
    cluster_raw = raw.get("cluster", {})
    api_raw = raw.get("api", {})

    return LensConfig(
        corpus_root=raw.get("corpus_root", "."),
        output_dir=raw.get("output_dir", ".lens/artifacts"),
        cache_dir=raw.get("cache_dir", ".lens/cache"),
        extraction=ExtractionConfig(
            syntax=ext_raw.get("syntax", True),
            concepts=ext_raw.get("concepts", True),
        ),
        cluster=ClusterConfig(
            algorithm=cluster_raw.get("algorithm", "leiden"),
            resolution=cluster_raw.get("resolution", 1.0),
        ),
        api=ApiConfig(
            host=api_raw.get("host", "127.0.0.1"),
            port=api_raw.get("port", 8400),
        ),
    )
