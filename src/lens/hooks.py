"""Git hook management for Lens.

Installs / uninstalls post-commit and post-checkout hooks that
automatically rebuild the knowledge graph when the repository changes.

The hooks invoke ``lens corpus ingest . --update`` so only changed files
are re-processed.  If the rebuild fails the hook exits non-zero so git
surfaces the error.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

# The hook script is a thin shell wrapper that calls the lens CLI.
# It works on both Unix (bash) and Windows (git-bash ships with Git for
# Windows, so #!/bin/sh is universally available in .git/hooks).

_HOOK_SCRIPT = """\
#!/bin/sh
# Lens auto-rebuild hook — installed by `lens hook install`
# Remove with `lens hook uninstall`
echo "[lens] Rebuilding knowledge graph (incremental)…"
lens corpus ingest . --update
exit_code=$?
if [ $exit_code -ne 0 ]; then
  echo "[lens] Graph rebuild failed (exit $exit_code)." >&2
fi
exit $exit_code
"""

_HOOK_TAG = "# Lens auto-rebuild hook"

HOOK_NAMES = ("post-commit", "post-checkout")


def _find_git_dir(start: Path | None = None) -> Path | None:
    """Walk up from *start* to find the nearest .git directory."""
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        git = parent / ".git"
        if git.is_dir():
            return git
    return None


def install_hooks(repo_root: Path | None = None) -> list[str]:
    """Install Lens git hooks.  Returns list of installed hook paths."""
    git_dir = _find_git_dir(repo_root)
    if git_dir is None:
        raise FileNotFoundError(
            "No .git directory found. Run this inside a git repository."
        )

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    installed: list[str] = []
    for name in HOOK_NAMES:
        hook_path = hooks_dir / name
        if hook_path.exists():
            content = hook_path.read_text(encoding="utf-8", errors="replace")
            if _HOOK_TAG in content:
                # Already installed — skip
                installed.append(str(hook_path))
                continue
            # There is an existing hook we don't own — don't overwrite
            raise FileExistsError(
                f"Hook {hook_path} already exists and was not installed by Lens. "
                "Remove it manually or add the Lens rebuild command to it."
            )
        hook_path.write_text(_HOOK_SCRIPT, encoding="utf-8")
        # Make executable (no-op on Windows but needed for Unix / WSL)
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)
        installed.append(str(hook_path))

    return installed


def uninstall_hooks(repo_root: Path | None = None) -> list[str]:
    """Remove Lens git hooks.  Returns list of removed hook paths."""
    git_dir = _find_git_dir(repo_root)
    if git_dir is None:
        raise FileNotFoundError("No .git directory found.")

    removed: list[str] = []
    for name in HOOK_NAMES:
        hook_path = git_dir / "hooks" / name
        if not hook_path.exists():
            continue
        content = hook_path.read_text(encoding="utf-8", errors="replace")
        if _HOOK_TAG not in content:
            continue  # Not ours
        hook_path.unlink()
        removed.append(str(hook_path))

    return removed


def hook_status(repo_root: Path | None = None) -> dict[str, str]:
    """Return a dict of hook_name → status string."""
    git_dir = _find_git_dir(repo_root)
    if git_dir is None:
        return {n: "no git repo" for n in HOOK_NAMES}

    result: dict[str, str] = {}
    for name in HOOK_NAMES:
        hook_path = git_dir / "hooks" / name
        if not hook_path.exists():
            result[name] = "not installed"
        else:
            content = hook_path.read_text(encoding="utf-8", errors="replace")
            if _HOOK_TAG in content:
                result[name] = "installed (lens)"
            else:
                result[name] = "installed (other)"
    return result
