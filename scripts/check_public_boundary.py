from __future__ import annotations

import argparse
import fnmatch
import glob
import os
import re
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class BoundaryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Violation:
    path: str
    pattern: str
    source: str


@dataclass(frozen=True, slots=True)
class BoundaryPolicy:
    version: int
    deny: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> BoundaryPolicy:
        try:
            value = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise BoundaryError(f"cannot load boundary policy {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise BoundaryError("public boundary policy must be a TOML table")
        unknown = set(value).difference({"version", "deny"})
        if unknown:
            names = ", ".join(sorted(unknown))
            raise BoundaryError(f"public boundary policy has unknown keys: {names}")
        version = value.get("version")
        patterns = value.get("deny")
        if isinstance(version, bool) or not isinstance(version, int) or version != 1:
            raise BoundaryError("public boundary policy version must be 1")
        if not isinstance(patterns, list) or not patterns:
            raise BoundaryError("public boundary policy deny must be a non-empty array")
        normalized = tuple(_normalize_pattern(item) for item in patterns)
        folded = tuple(item.casefold() for item in normalized)
        if len(folded) != len(set(folded)):
            raise BoundaryError("public boundary policy contains duplicate patterns")
        return cls(version=version, deny=normalized)

    def match(self, path: str) -> str | None:
        candidate = _normalize_path(path).casefold()
        for pattern in self.deny:
            if fnmatch.fnmatchcase(candidate, pattern.casefold()):
                return pattern
        return None

    def violations(self, paths: Iterable[str], *, source: str) -> tuple[Violation, ...]:
        found: list[Violation] = []
        normalized = {_normalize_path(item) for item in paths}
        for path in sorted(normalized, key=str.casefold):
            pattern = self.match(path)
            if pattern is not None:
                found.append(Violation(path=path, pattern=pattern, source=source))
        return tuple(found)


def _normalize_pattern(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BoundaryError("public boundary patterns must be non-empty strings")
    pattern = value.replace("\\", "/").strip()
    parsed = PurePosixPath(pattern)
    if parsed.is_absolute() or ".." in parsed.parts or re.match(r"^[A-Za-z]:", pattern):
        raise BoundaryError(f"public boundary pattern must be repository-relative: {value!r}")
    return pattern


def _normalize_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise BoundaryError("encountered an invalid empty or NUL-containing path")
    path = value.replace("\\", "/")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts or re.match(r"^[A-Za-z]:", path):
        raise BoundaryError(f"path escapes repository boundary: {value!r}")
    normalized = parsed.as_posix()
    if normalized in {"", "."}:
        raise BoundaryError(f"invalid repository path: {value!r}")
    return normalized


def _git(root: Path, *args: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", os.fspath(root), *args],
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.decode(errors="replace").strip()
        raise BoundaryError(f"git {' '.join(args)} failed: {detail}")
    return process.stdout


def _decode_paths(value: bytes) -> tuple[str, ...]:
    return tuple(os.fsdecode(item) for item in value.split(b"\0") if item)


def _index_paths(root: Path) -> tuple[str, ...]:
    return _decode_paths(_git(root, "ls-files", "--cached", "-z", "--"))


def _tree_paths(root: Path, revision: str) -> tuple[str, ...]:
    return _decode_paths(_git(root, "ls-tree", "-r", "--name-only", "-z", revision))


def _revision_commits(root: Path, local_oid: str, remote_oid: str) -> tuple[str, ...]:
    if _is_zero_oid(remote_oid):
        value = _git(root, "rev-list", local_oid)
    else:
        value = _git(root, "rev-list", local_oid, f"^{remote_oid}")
    return tuple(line for line in value.decode("ascii").splitlines() if line)


def _is_zero_oid(value: str) -> bool:
    return bool(value) and set(value) == {"0"}


def _pre_push_violations(
    root: Path,
    policy: BoundaryPolicy,
    lines: Iterable[str],
) -> tuple[Violation, ...]:
    violations: list[Violation] = []
    checked: set[str] = set()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) != 4:
            raise BoundaryError(f"malformed pre-push input at line {line_number}")
        local_ref, local_oid, _remote_ref, remote_oid = fields
        if _is_zero_oid(local_oid):
            continue
        for commit in _revision_commits(root, local_oid, remote_oid):
            if commit in checked:
                continue
            checked.add(commit)
            violations.extend(
                policy.violations(
                    _tree_paths(root, commit),
                    source=f"outgoing {local_ref} commit {commit[:12]}",
                )
            )
    return tuple(violations)


def _history_violations(root: Path, policy: BoundaryPolicy) -> tuple[Violation, ...]:
    commits = tuple(
        line for line in _git(root, "rev-list", "--all").decode("ascii").splitlines() if line
    )
    violations: list[Violation] = []
    checked_trees: set[str] = set()
    for commit in commits:
        tree = _git(root, "rev-parse", f"{commit}^{{tree}}").decode("ascii").strip()
        if tree in checked_trees:
            continue
        checked_trees.add(tree)
        violations.extend(
            policy.violations(
                _tree_paths(root, tree),
                source=f"history commit {commit[:12]}",
            )
        )
    return tuple(violations)


def _archive_paths(path: Path) -> tuple[str, ...]:
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                return tuple(item.filename for item in archive.infolist())
        if tarfile.is_tarfile(path):
            with tarfile.open(path, mode="r:*") as archive:
                return tuple(item.name for item in archive.getmembers())
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise BoundaryError(f"cannot inspect archive {path}: {exc}") from exc
    raise BoundaryError(f"unsupported or invalid distribution archive: {path}")


def _expand_archives(root: Path, values: Iterable[str]) -> tuple[Path, ...]:
    found: set[Path] = set()
    for value in values:
        candidate = Path(value)
        pattern = os.fspath(candidate if candidate.is_absolute() else root / candidate)
        matches = glob.glob(pattern)
        if not matches:
            raise BoundaryError(f"archive pattern matched no files: {value}")
        for match in matches:
            path = Path(match).resolve()
            try:
                path.relative_to(root)
            except ValueError as exc:
                raise BoundaryError(f"archive is outside repository root: {path}") from exc
            if not path.is_file():
                raise BoundaryError(f"archive is not a file: {path}")
            found.add(path)
    return tuple(sorted(found, key=lambda item: os.fspath(item).casefold()))


def _archive_violations(
    root: Path,
    policy: BoundaryPolicy,
    values: Iterable[str],
) -> tuple[Violation, ...]:
    violations: list[Violation] = []
    for archive in _expand_archives(root, values):
        display = archive.relative_to(root).as_posix()
        violations.extend(policy.violations(_archive_paths(archive), source=f"archive {display}"))
    return tuple(violations)


def _repository_root(explicit: Path | None) -> Path:
    start = Path.cwd() if explicit is None else explicit.resolve()
    process = subprocess.run(
        ["git", "-C", os.fspath(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise BoundaryError(f"not inside a Git worktree: {start}")
    root = Path(os.fsdecode(process.stdout).strip()).resolve()
    if explicit is not None and os.path.normcase(os.fspath(root)) != os.path.normcase(
        os.fspath(start)
    ):
        raise BoundaryError(f"explicit root is not the Git worktree root: {start}")
    return root


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail closed when local-only paths cross the public Git or package boundary."
    )
    parser.add_argument("--root", type=Path, help="Git worktree root; defaults to current Git root")
    parser.add_argument(
        "--policy",
        type=Path,
        help="policy path; defaults to <root>/public-boundary.toml",
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--staged", action="store_true", help="check the complete staged index")
    modes.add_argument("--tree", metavar="REVISION", help="check every path in one Git tree")
    modes.add_argument(
        "--history",
        action="store_true",
        help="check every unique tree reachable from all local refs",
    )
    modes.add_argument(
        "--pre-push",
        action="store_true",
        help="read pre-push updates from stdin and check every outgoing commit tree",
    )
    modes.add_argument(
        "--archives",
        nargs="+",
        metavar="ARCHIVE",
        help="check wheel/sdist member paths; shell-style globs are supported",
    )
    modes.add_argument("--paths", nargs="+", help="check explicit repository-relative paths")
    return parser


def run(argv: Sequence[str] | None = None, *, stdin: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root = _repository_root(args.root)
        if args.policy is None:
            policy_path = root / "public-boundary.toml"
        else:
            policy_path = args.policy if args.policy.is_absolute() else root / args.policy
        policy = BoundaryPolicy.load(policy_path.resolve())
        if args.staged:
            violations = policy.violations(_index_paths(root), source="staged index")
        elif args.tree is not None:
            violations = policy.violations(_tree_paths(root, args.tree), source=f"tree {args.tree}")
        elif args.history:
            violations = _history_violations(root, policy)
        elif args.pre_push:
            violations = _pre_push_violations(root, policy, sys.stdin if stdin is None else stdin)
        elif args.archives is not None:
            violations = _archive_violations(root, policy, args.archives)
        else:
            violations = policy.violations(args.paths, source="explicit paths")
    except BoundaryError as exc:
        print(f"public-boundary: ERROR: {exc}", file=sys.stderr)
        return 2

    if not violations:
        print("public-boundary: clean")
        return 0

    print("public-boundary: BLOCKED local-only content", file=sys.stderr)
    for item in violations:
        print(
            f"  {item.path} (matched {item.pattern!r}; {item.source})",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
