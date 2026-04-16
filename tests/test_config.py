"""Unit tests for lens.config."""

import textwrap
from pathlib import Path

from lens.config import LensConfig, load_config


class TestLoadConfig:
    def test_defaults_when_no_file(self, tmp_path: Path):
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert cfg.corpus_root == "."
        assert cfg.output_dir == ".lens/artifacts"
        assert cfg.extraction.syntax is True
        assert cfg.cluster.algorithm == "leiden"
        assert cfg.api.port == 8400

    def test_loads_yaml(self, tmp_path: Path):
        yaml_file = tmp_path / "lens.config.yaml"
        yaml_file.write_text(textwrap.dedent("""\
            corpus_root: /data/repo
            output_dir: out
            extraction:
              syntax: false
              concepts: true
            cluster:
              algorithm: greedy
              resolution: 0.5
            api:
              port: 9000
        """))
        cfg = load_config(yaml_file)
        assert cfg.corpus_root == "/data/repo"
        assert cfg.extraction.syntax is False
        assert cfg.cluster.algorithm == "greedy"
        assert cfg.api.port == 9000
