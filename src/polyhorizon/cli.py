from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from polyhorizon.canonical import to_jsonable
from polyhorizon.errors import PolyhorizonError
from polyhorizon.kernel import DecisionEffect, StepResult
from polyhorizon.models import Charter, Proposal
from polyhorizon.runtime import Engine
from polyhorizon.serde import effect_receipt_from_dict, step_to_dict
from polyhorizon.store import FileSessionStore, MemorySessionStore
from polyhorizon.version import __version__
from polyhorizon.wire import DEFAULT_MAX_LINE_BYTES, WireEngine, decode_json, serve


def _load_json(path: Path) -> Any:
    return decode_json(path.read_text(encoding="utf-8"))


def _write(value: object) -> None:
    print(json.dumps(to_jsonable(value), ensure_ascii=False, sort_keys=True, indent=2))


def _engine(state_dir: Path | None) -> Engine:
    store = MemorySessionStore() if state_dir is None else FileSessionStore(state_dir)
    return Engine(store=store)


def _wire_stdio() -> tuple[TextIO, TextIO]:
    if isinstance(sys.stdin, io.TextIOWrapper):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    return sys.stdin, sys.stdout


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polyhorizon",
        description="Transport-neutral admission engine for plural consequence horizons.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("capabilities", help="print supported protocol surfaces")

    validate_charter = subparsers.add_parser("validate-charter", help="validate a charter")
    validate_charter.add_argument("charter", type=Path)

    validate_proposal = subparsers.add_parser("validate-proposal", help="validate proposal binding")
    validate_proposal.add_argument("--charter", required=True, type=Path)
    validate_proposal.add_argument("--candidate", type=Path)
    validate_proposal.add_argument("proposal", type=Path)

    open_parser = subparsers.add_parser("open", help="open a persisted admission session")
    open_parser.add_argument("--state-dir", required=True, type=Path)
    open_parser.add_argument("--charter", required=True, type=Path)
    open_parser.add_argument("--candidate", type=Path)
    open_parser.add_argument("proposal", type=Path)

    advance = subparsers.add_parser("advance", help="submit bound effect receipts")
    advance.add_argument("--state-dir", required=True, type=Path)
    advance.add_argument("--charter", required=True, type=Path)
    advance.add_argument("--session", required=True)
    advance.add_argument("--expected-sequence", required=True, type=int)
    advance.add_argument("receipts", type=Path)

    inspect = subparsers.add_parser("inspect", help="inspect persisted session state")
    inspect.add_argument("--state-dir", required=True, type=Path)
    inspect.add_argument("session")

    abort = subparsers.add_parser("abort", help="abort an awaiting session")
    abort.add_argument("--state-dir", required=True, type=Path)
    abort.add_argument("--expected-sequence", required=True, type=int)
    abort.add_argument("session")

    server = subparsers.add_parser("serve", help="serve the versioned NDJSON protocol")
    server.add_argument("--state-dir", type=Path)
    server.add_argument("--max-line-bytes", type=int, default=DEFAULT_MAX_LINE_BYTES)
    return parser


def _candidate(path: Path | None) -> Charter | None:
    return None if path is None else Charter.from_dict(_load_json(path))


def _decision_exit(result: StepResult) -> int:
    if result.decision is None or result.decision.effect is DecisionEffect.ALLOW:
        return 0
    if result.decision.effect is DecisionEffect.DENY:
        return 3
    return 4


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "capabilities":
        _write(WireEngine.capabilities())
        return 0
    if args.command == "validate-charter":
        charter = Charter.from_dict(_load_json(args.charter))
        _write({"valid": True, "api_version": charter.api_version, "digest": charter.digest})
        return 0
    if args.command == "validate-proposal":
        charter = Charter.from_dict(_load_json(args.charter))
        proposal = Proposal.from_dict(_load_json(args.proposal))
        candidate = _candidate(args.candidate)
        if proposal.base_charter_digest != charter.digest:
            raise ValueError("proposal base_charter_digest does not match the charter")
        if proposal.is_amendment != (candidate is not None):
            raise ValueError("candidate presence does not match amendment proposal")
        if candidate is not None and proposal.candidate_charter_digest != candidate.digest:
            raise ValueError("candidate charter digest does not match the proposal")
        _write({"valid": True, "api_version": proposal.api_version, "digest": proposal.digest})
        return 0
    if args.command == "open":
        charter = Charter.from_dict(_load_json(args.charter))
        proposal = Proposal.from_dict(_load_json(args.proposal))
        result = _engine(args.state_dir).open(
            charter, proposal, candidate=_candidate(args.candidate)
        )
        _write(step_to_dict(result))
        return _decision_exit(result)
    if args.command == "advance":
        charter = Charter.from_dict(_load_json(args.charter))
        raw = _load_json(args.receipts)
        values = raw.get("receipts") if isinstance(raw, dict) else raw
        if not isinstance(values, list):
            raise ValueError("receipts file must be an array or an object containing receipts")
        receipts = tuple(
            effect_receipt_from_dict(value, f"$.receipts[{index}]")
            for index, value in enumerate(values)
        )
        result = _engine(args.state_dir).advance(
            charter,
            args.session,
            args.expected_sequence,
            receipts,
        )
        _write(step_to_dict(result))
        return _decision_exit(result)
    if args.command == "inspect":
        state = _engine(args.state_dir).inspect(args.session)
        if state is None:
            raise ValueError("session does not exist")
        _write({"state": state, "state_digest": state.digest})
        return 0
    if args.command == "abort":
        result = _engine(args.state_dir).abort(args.session, args.expected_sequence)
        _write(step_to_dict(result))
        return 0
    if args.command == "serve":
        instream, outstream = _wire_stdio()
        return serve(
            WireEngine(_engine(args.state_dir)),
            instream,
            outstream,
            max_line_bytes=args.max_line_bytes,
        )
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except (OSError, json.JSONDecodeError, PolyhorizonError, TypeError, ValueError) as exc:
        print(f"polyhorizon: ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
