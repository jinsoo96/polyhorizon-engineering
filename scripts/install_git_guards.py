from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path

EXPECTED_HOOKS_PATH = ".githooks"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", os.fspath(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _root() -> Path:
    process = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if process.returncode != 0:
        raise RuntimeError("run this installer inside the Polyhorizon Engineering Git worktree")
    return Path(process.stdout.strip()).resolve()


def _check(root: Path, mode: str) -> None:
    process = subprocess.run(
        [sys.executable, os.fspath(root / "scripts" / "check_public_boundary.py"), mode],
        cwd=root,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(f"hooks installed, but the repository failed boundary check {mode}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install repository-local public-boundary hooks.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace a different existing core.hooksPath",
    )
    args = parser.parse_args()
    try:
        root = _root()
        for name in ("pre-commit", "pre-push"):
            hook = root / EXPECTED_HOOKS_PATH / name
            if not hook.is_file():
                raise RuntimeError(f"missing hook: {hook}")
            hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        runner = root / "scripts" / "run_public_boundary.sh"
        runner.chmod(runner.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        current = _git(root, "config", "--local", "--get", "core.hooksPath")
        configured = current.stdout.strip() if current.returncode == 0 else ""
        if configured and configured.rstrip("/\\") != EXPECTED_HOOKS_PATH and not args.force:
            raise RuntimeError(
                f"core.hooksPath is already {configured!r}; use --force only after merging hooks"
            )
        result = _git(root, "config", "--local", "core.hooksPath", EXPECTED_HOOKS_PATH)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "failed to configure core.hooksPath")

        _check(root, "--staged")
        head = _git(root, "rev-parse", "--verify", "HEAD")
        if head.returncode == 0:
            _check(root, "--history")
    except (OSError, RuntimeError) as exc:
        print(f"install-git-guards: ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"install-git-guards: core.hooksPath={EXPECTED_HOOKS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
