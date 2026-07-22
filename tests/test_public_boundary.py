from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "public-boundary.toml"


def _load_boundary_module() -> ModuleType:
    path = ROOT / "scripts" / "check_public_boundary.py"
    spec = importlib.util.spec_from_file_location("polyhorizon_public_boundary", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load public-boundary checker from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


boundary = _load_boundary_module()


def _git(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "--quiet", "--initial-branch=main")
    _git(root, "config", "user.name", "Boundary Test")
    _git(root, "config", "user.email", "boundary@example.invalid")
    return root


def _write(root: Path, relative: str, content: str = "test\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "--all")
    _git(root, "commit", "--quiet", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _run(root: Path, *mode: str, stdin: tuple[str, ...] | None = None) -> int:
    return boundary.run(
        ["--root", str(root), "--policy", str(POLICY), *mode],
        stdin=stdin,
    )


@pytest.mark.parametrize(
    "path",
    [
        ".ClAuDe/session.jsonl",
        "tools/.CoDeX/memory.md",
        "state/.PoLyHoRiZoN/session.json",
        "nested/InTeRnAl/decision.md",
        "nested/WoRkLoGs/2026-07-22.md",
        "service/.ENV.production",
        "service/.EnVrC",
        "config/runtime.LoCaL.toml",
    ],
)
def test_explicit_paths_are_blocked_case_insensitively(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    root = _repository(tmp_path)

    assert _run(root, "--paths", path) == 1

    captured = capsys.readouterr()
    assert "BLOCKED local-only content" in captured.err
    assert path in captured.err
    assert "explicit paths" in captured.err


@pytest.mark.parametrize(
    "path",
    [
        "docs/internals-guide.md",
        "worklog/summary.md",
        ".environment",
        "config/local.toml",
        "src/polyhorizon/runtime.py",
    ],
)
def test_similarly_named_public_paths_are_not_overblocked(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    root = _repository(tmp_path)

    assert _run(root, "--paths", path) == 0
    assert capsys.readouterr().out == "public-boundary: clean\n"


def test_staged_mode_reads_the_complete_index(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _repository(tmp_path)
    _write(root, "src/public.py")
    _write(root, "Docs/InTeRnAl/plan.md")
    _git(root, "add", "--all")

    assert _run(root, "--staged") == 1

    captured = capsys.readouterr()
    assert "Docs/InTeRnAl/plan.md" in captured.err
    assert "staged index" in captured.err


def test_history_mode_finds_denied_content_deleted_from_head(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _repository(tmp_path)
    denied = _write(root, "archive/WoRkLoGs/private.md")
    tainted = _commit(root, "add private worklog")
    denied.unlink()
    _write(root, "README.md", "public\n")
    _commit(root, "remove private worklog")

    assert _run(root, "--tree", "HEAD") == 0
    capsys.readouterr()
    assert _run(root, "--history") == 1

    captured = capsys.readouterr()
    assert "archive/WoRkLoGs/private.md" in captured.err
    assert f"history commit {tainted[:12]}" in captured.err


def test_pre_push_mode_checks_every_outgoing_commit_tree(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _repository(tmp_path)
    _write(root, "README.md", "public\n")
    remote_oid = _commit(root, "public baseline")
    _write(root, "service/.EnV.production", "TOKEN=not-a-real-token\n")
    local_oid = _commit(root, "add local environment")
    update = f"refs/heads/main {local_oid} refs/heads/main {remote_oid}\n"

    assert _run(root, "--pre-push", stdin=(update,)) == 1

    captured = capsys.readouterr()
    assert "service/.EnV.production" in captured.err
    assert f"outgoing refs/heads/main commit {local_oid[:12]}" in captured.err


def test_pre_push_mode_checks_a_new_branch_from_its_complete_history(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _repository(tmp_path)
    _write(root, "nested/.CoDeX/context.json")
    local_oid = _commit(root, "tainted root commit")
    update = f"refs/heads/main {local_oid} refs/heads/main {'0' * 40}\n"

    assert _run(root, "--pre-push", stdin=(update,)) == 1

    captured = capsys.readouterr()
    assert "nested/.CoDeX/context.json" in captured.err
    assert "outgoing refs/heads/main" in captured.err


def test_archive_mode_scans_wheel_and_sdist_member_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _repository(tmp_path)
    dist = root / "dist"
    dist.mkdir()
    wheel = dist / "polyhorizon_engineering-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, mode="w") as archive:
        archive.writestr("polyhorizon/__init__.py", "")
        archive.writestr("polyhorizon/.EnV.release", "not-a-real-secret")

    sdist = dist / "polyhorizon_engineering-0.1.0.tar.gz"
    payload = b"private design\n"
    member = tarfile.TarInfo("polyhorizon_engineering-0.1.0/Docs/InTeRnAl/design.md")
    member.size = len(payload)
    with tarfile.open(sdist, mode="w:gz") as archive:
        archive.addfile(member, io.BytesIO(payload))

    assert _run(root, "--archives", "dist/*") == 1

    captured = capsys.readouterr()
    assert "polyhorizon/.EnV.release" in captured.err
    assert "polyhorizon_engineering-0.1.0/Docs/InTeRnAl/design.md" in captured.err
    assert "archive dist/polyhorizon_engineering-0.1.0-py3-none-any.whl" in captured.err
    assert "archive dist/polyhorizon_engineering-0.1.0.tar.gz" in captured.err


def test_hooks_ci_and_manifest_keep_all_boundary_layers_wired() -> None:
    pre_commit = (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    pre_push = (ROOT / ".githooks" / "pre-push").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    assert 'run_public_boundary.sh" --staged' in pre_commit
    assert 'run_public_boundary.sh" --pre-push' in pre_push
    assert "fetch-depth: 0" in workflow
    assert "check_public_boundary.py --tree HEAD" in workflow
    assert "check_public_boundary.py --history" in workflow
    assert "check_public_boundary.py --archives dist/*" in workflow
    assert "include public-boundary.toml" in manifest
    assert "recursive-include scripts *.py *.sh" in manifest
    assert "prune internal" in manifest
    assert "prune worklogs" in manifest
    assert "global-exclude .env .env.* .envrc *.local.*" in manifest
