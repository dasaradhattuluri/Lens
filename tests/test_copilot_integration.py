"""Unit tests for lens.copilot_integration."""

import json
from pathlib import Path

from lens.copilot_integration import install_copilot, uninstall_copilot


class TestInstallCopilot:
    def test_creates_all_files(self, tmp_path: Path):
        results = install_copilot(tmp_path)
        actions = {Path(p).name: a for p, a in results}
        assert actions["AGENTS.md"] == "created"
        assert actions["copilot-instructions.md"] == "created"
        assert actions["settings.json"] == "updated"

        # Verify contents
        agents = (tmp_path / "AGENTS.md").read_text()
        assert "Lens Knowledge Graph" in agents
        assert "analysis-report.md" in agents

        ci = (tmp_path / ".github" / "copilot-instructions.md").read_text()
        assert "knowledge-graph.jsonld" in ci

        settings = json.loads((tmp_path / ".vscode" / "settings.json").read_text())
        assert "**/.lens/cache" in settings["search.exclude"]

    def test_idempotent(self, tmp_path: Path):
        install_copilot(tmp_path)
        results = install_copilot(tmp_path)
        actions = {Path(p).name: a for p, a in results}
        assert actions["AGENTS.md"] == "already present"
        assert actions["copilot-instructions.md"] == "already present"
        assert actions["settings.json"] == "already present"


class TestUninstallCopilot:
    def test_removes_files(self, tmp_path: Path):
        install_copilot(tmp_path)
        removed = uninstall_copilot(tmp_path)
        assert len(removed) == 2  # AGENTS.md + copilot-instructions.md

    def test_noop_when_nothing_installed(self, tmp_path: Path):
        removed = uninstall_copilot(tmp_path)
        assert removed == []
