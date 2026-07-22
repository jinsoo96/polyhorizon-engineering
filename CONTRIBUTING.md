# Contributing

## Install the public-boundary guards

Run this once in every clone before creating a commit:

```bash
python scripts/install_git_guards.py
```

`public-boundary.toml` is the single path policy for material that must remain local. Pre-commit
checks the complete staged index. Pre-push checks every outgoing commit tree, including a denied
file added and deleted before the push. CI checks both `HEAD` and all fetched history, then scans
the wheel and source distribution. Internal documents, nested `internal/` and `worklogs/` folders,
`.codex`, `.claude`, `.env`, `.env.*`, `.envrc`, and `*.local.*` files are denied
case-insensitively.

This is a path boundary, not a content-aware secret scanner. Credentials must never be stored under
another name. Do not bypass the hooks with `--no-verify`; protect the CI check with the remote
repository's branch rules as well.

## Preserve the engine contract

Changes should retain these invariants:

1. The kernel proposes effects; a host adapter executes them and returns bound receipts.
2. Horizon kinds and integrations are namespaced data, not closed enums or symptom tables.
3. Hard violations deny, while unknown or uncovered consequences escalate instead of passing.
4. Multi-horizon results remain vector-valued; a favorable scalar cannot erase another horizon.
5. Obligations keep an accountable owner and affected parties retain executable recourse.
6. A horizon, evaluator, or authority cannot authorize its own replacement at the same layer.
7. Transport-specific behavior belongs in adapters, not in the deterministic transition core.

State the invariant or falsifiable claim affected by a change. Add adversarial and failure-injection
tests before broadening a public claim. Keep domain thresholds, horizon taxonomies, and authority
rules in versioned manifests or adapters rather than hard-coding them in the kernel.

Run before submitting:

```bash
ruff format --check .
ruff check .
mypy
pytest
python -m build
python -m twine check dist/*
python scripts/check_public_boundary.py --archives dist/*
```

Commit messages should record the cause, approach, invariant, impact, and verification. Do not add
AI co-author trailers.
