"""Unit tests for lens.hooks."""

import os
from pathlib import Path

import pytest

from lens.hooks import install_hooks, uninstall_hooks, hook_status, _HOOK_TAG


class TestInstallHooks:
    def test_installs_into_git_dir(self, tmp_path: Path):
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        paths = install_hooks(tmp_path)
        assert len(paths) == 2
        for p in paths:
            content = Path(p).read_text()
            assert _HOOK_TAG in content

    def test_idempotent(self, tmp_path: Path):
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        install_hooks(tmp_path)
        # Second call should not fail
        paths = install_hooks(tmp_path)
        assert len(paths) == 2

    def test_refuses_to_overwrite_foreign_hook(self, tmp_path: Path):
        hooks_dir = tmp_path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "post-commit").write_text("#!/bin/sh\necho hello\n")
        with pytest.raises(FileExistsError):
            install_hooks(tmp_path)

    def test_no_git_dir_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            install_hooks(tmp_path)


class TestUninstallHooks:
    def test_removes_lens_hooks(self, tmp_path: Path):
        hooks_dir = tmp_path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        install_hooks(tmp_path)
        removed = uninstall_hooks(tmp_path)
        assert len(removed) == 2
        for name in ("post-commit", "post-checkout"):
            assert not (hooks_dir / name).exists()

    def test_leaves_foreign_hooks_alone(self, tmp_path: Path):
        hooks_dir = tmp_path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "post-commit").write_text("#!/bin/sh\necho foreign\n")
        removed = uninstall_hooks(tmp_path)
        assert removed == []
        assert (hooks_dir / "post-commit").exists()


class TestHookStatus:
    def test_not_installed(self, tmp_path: Path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        status = hook_status(tmp_path)
        assert status["post-commit"] == "not installed"

    def test_installed(self, tmp_path: Path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        install_hooks(tmp_path)
        status = hook_status(tmp_path)
        assert status["post-commit"] == "installed (lens)"
        assert status["post-checkout"] == "installed (lens)"

    def test_no_git_repo(self, tmp_path: Path):
        status = hook_status(tmp_path)
        assert status["post-commit"] == "no git repo"
