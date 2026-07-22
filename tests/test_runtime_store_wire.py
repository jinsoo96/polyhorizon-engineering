from __future__ import annotations

import io
import json
from datetime import timedelta
from pathlib import Path

import pytest

from polyhorizon.canonical import to_jsonable
from polyhorizon.errors import ConcurrentUpdateError, ManifestError, ProtocolError
from polyhorizon.kernel import DecisionEffect, SessionStatus
from polyhorizon.models import ReceiptStatus
from polyhorizon.runtime import Engine
from polyhorizon.serde import session_from_dict
from polyhorizon.store import FileSessionStore, MemorySessionStore
from polyhorizon.wire import WIRE_API, WireEngine, serve

from .helpers import NOW, make_charter, make_proposal, receipt_for


def test_engine_idempotency_and_sequence_cas() -> None:
    charter = make_charter()
    proposal = make_proposal(charter)
    engine = Engine(store=MemorySessionStore(), clock=lambda: NOW)
    first = engine.open(charter, proposal)
    second = engine.open(charter, proposal)
    assert second.state.digest == first.state.digest

    advanced = engine.advance(
        charter,
        first.state.id,
        0,
        (receipt_for(first.effects[0], issued_at=NOW),),
    )
    assert advanced.state.sequence == 1
    with pytest.raises(ConcurrentUpdateError):
        engine.advance(charter, first.state.id, 0, ())


def test_idempotent_open_of_terminal_session_never_redispatches_effects() -> None:
    charter = make_charter()
    proposal = make_proposal(charter)
    engine = Engine(clock=lambda: NOW)
    opened = engine.open(charter, proposal)
    completed = engine.advance(
        charter,
        opened.state.id,
        opened.state.sequence,
        tuple(receipt_for(item, issued_at=NOW) for item in opened.effects),
    )

    replayed = engine.open(charter, proposal)
    assert replayed.state == completed.state
    assert replayed.decision == completed.decision
    assert replayed.effects == ()


def test_idempotency_key_cannot_bind_different_proposal() -> None:
    charter = make_charter()
    store = MemorySessionStore()
    first = Engine(store=store, clock=lambda: NOW).open(charter, make_proposal(charter))
    changed = make_proposal(charter, effect="code.correctness")
    with pytest.raises(ProtocolError, match="idempotency"):
        Engine(store=store, clock=lambda: NOW).open(charter, changed)
    assert store.get(first.state.id) is not None


def test_file_store_survives_restart_and_detects_state_tampering(tmp_path: Path) -> None:
    charter = make_charter()
    directory = tmp_path / "sessions"
    engine = Engine(store=FileSessionStore(directory), clock=lambda: NOW)
    opened = engine.open(charter, make_proposal(charter))

    restarted = Engine(store=FileSessionStore(directory), clock=lambda: NOW)
    assert restarted.require(opened.state.id).digest == opened.state.digest
    path = directory / f"{opened.state.id}.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["state"]["idempotency_key"] = "tampered-key"
    path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(ProtocolError, match="digest does not match"):
        restarted.require(opened.state.id)


def test_session_decoder_normalizes_model_failures_to_manifest_error() -> None:
    charter = make_charter()
    opened = Engine(clock=lambda: NOW).open(charter, make_proposal(charter))
    encoded = to_jsonable(opened.state)
    encoded["status"] = "invented-status"
    with pytest.raises(ManifestError, match="invented-status"):
        session_from_dict(encoded)


def test_wire_open_advance_and_inspect() -> None:
    charter = make_charter()
    proposal = make_proposal(charter)
    adapter = WireEngine(Engine(clock=lambda: NOW))
    opened = adapter.handle(
        {
            "api_version": WIRE_API,
            "request_id": "request-open",
            "command": "open",
            "payload": {
                "charter": to_jsonable(charter),
                "proposal": to_jsonable(proposal),
            },
        }
    )
    assert opened["ok"] is True
    payload = opened["payload"]
    assert isinstance(payload, dict)
    state = payload["state"]
    effects = payload["effects"]
    assert isinstance(state, dict) and isinstance(effects, list)

    receipts = [
        to_jsonable(receipt_for(request, issued_at=NOW))
        for request in Engine(clock=lambda: NOW).kernel.open(charter, proposal, now=NOW).effects
    ]
    advanced = adapter.handle(
        {
            "api_version": WIRE_API,
            "request_id": "request-advance",
            "command": "advance",
            "payload": {
                "charter": to_jsonable(charter),
                "session_id": state["id"],
                "expected_sequence": 0,
                "receipts": receipts,
            },
        }
    )
    assert advanced["ok"] is True
    result_payload = advanced["payload"]
    assert isinstance(result_payload, dict)
    decision = result_payload["decision"]
    assert isinstance(decision, dict)
    assert decision["effect"] == DecisionEffect.ALLOW.value

    inspected = adapter.handle(
        {
            "api_version": WIRE_API,
            "request_id": "request-inspect",
            "command": "inspect",
            "payload": {"session_id": state["id"]},
        }
    )
    assert inspected["ok"] is True


def test_wire_abort_and_safe_errors() -> None:
    charter = make_charter()
    adapter = WireEngine(Engine(clock=lambda: NOW))
    opened = adapter.handle(
        {
            "api_version": WIRE_API,
            "request_id": "request-open",
            "command": "open",
            "payload": {
                "charter": to_jsonable(charter),
                "proposal": to_jsonable(make_proposal(charter)),
            },
        }
    )
    payload = opened["payload"]
    assert isinstance(payload, dict)
    state = payload["state"]
    assert isinstance(state, dict)
    aborted = adapter.handle(
        {
            "api_version": WIRE_API,
            "request_id": "request-abort",
            "command": "abort",
            "payload": {"session_id": state["id"], "expected_sequence": 0},
        }
    )
    assert aborted["ok"] is True
    abort_payload = aborted["payload"]
    assert isinstance(abort_payload, dict)
    abort_state = abort_payload["state"]
    assert isinstance(abort_state, dict)
    assert abort_state["status"] == SessionStatus.ABORTED.value

    bad = adapter.handle(
        {
            "api_version": "polyhorizon.wire/v9",
            "request_id": "bad-version",
            "command": "capabilities",
            "payload": {},
        }
    )
    assert bad["ok"] is False
    assert "Traceback" not in json.dumps(bad)


def test_ndjson_server_isolates_bad_lines_and_enforces_size() -> None:
    valid = json.dumps(
        {
            "api_version": WIRE_API,
            "request_id": "capabilities",
            "command": "capabilities",
            "payload": {},
        }
    )
    duplicate = valid.replace('"payload": {}', '"payload": {}, "payload": {}')
    limit = max(len(valid.encode("utf-8")), len(duplicate.encode("utf-8"))) + 1
    source = io.StringIO(
        "not-json\n" + duplicate + "\n" + valid + "\n" + ("x" * (limit + 1)) + "\n"
    )
    target = io.StringIO()
    assert serve(WireEngine(), source, target, max_line_bytes=limit) == 0
    responses = [json.loads(line) for line in target.getvalue().splitlines()]
    assert responses[0]["error"]["code"] == "invalid_json"
    assert responses[1]["error"]["code"] == "invalid_json"
    assert responses[2]["ok"] is True
    assert responses[3]["error"]["code"] == "message_too_large"


def test_ndjson_server_bounds_reads_and_contains_parser_failures() -> None:
    class TrackingStream(io.StringIO):
        def __init__(self, value: str) -> None:
            super().__init__(value)
            self.read_sizes: list[int] = []

        def readline(self, size: int = -1) -> str:
            self.read_sizes.append(size)
            return super().readline(size)

    limit = 128
    source = TrackingStream(("x" * 10_000) + "\n")
    target = io.StringIO()
    assert serve(WireEngine(), source, target, max_line_bytes=limit) == 0
    assert source.read_sizes and set(source.read_sizes) == {limit + 1}
    assert json.loads(target.getvalue())["error"]["code"] == "message_too_large"

    deep = (
        '{"api_version":"polyhorizon.wire/v0.1","request_id":"deep","command":"capabilities","payload":'
        + ("[" * 2_000)
        + "0"
        + ("]" * 2_000)
        + "}\n"
    )
    non_finite = (
        '{"api_version":"polyhorizon.wire/v0.1","request_id":"nan",'
        '"command":"capabilities","payload":{"value":NaN}}\n'
    )
    target = io.StringIO()
    assert serve(WireEngine(), io.StringIO(deep + non_finite), target) == 0
    responses = [json.loads(line) for line in target.getvalue().splitlines()]
    assert [item["error"]["code"] for item in responses] == ["invalid_json", "invalid_json"]


def test_ndjson_server_contains_invalid_utf8_and_surrogate_request_ids() -> None:
    for payload, limit in ((b"\xff\n", 1024), ((b"a" * 9_000) + b"\xff\n", 10)):
        binary = io.BytesIO(payload)
        source = io.TextIOWrapper(binary, encoding="utf-8", errors="strict")
        target = io.StringIO()
        assert serve(WireEngine(), source, target, max_line_bytes=limit) == 0
        assert json.loads(target.getvalue())["error"]["code"] == "invalid_json"

    response = WireEngine().handle(
        {
            "api_version": WIRE_API,
            "request_id": "\ud800",
            "command": "capabilities",
            "payload": {},
        }
    )
    assert response["request_id"] == "unknown"
    json.dumps(response, ensure_ascii=False).encode("utf-8")


def test_expired_session_escalates_without_accepting_receipts() -> None:
    charter = make_charter()
    proposal = make_proposal(charter)
    clock_values = iter((NOW, proposal.expires_at + timedelta(seconds=1)))
    engine = Engine(clock=lambda: next(clock_values))
    opened = engine.open(charter, proposal)
    result = engine.advance(
        charter,
        opened.state.id,
        opened.state.sequence,
        [receipt_for(item, ReceiptStatus.SATISFIED) for item in opened.effects],
    )
    assert result.decision is not None
    assert result.decision.effect is DecisionEffect.ESCALATE
    assert result.state.receipts == ()

    replayed = engine.open(charter, proposal)
    assert replayed.state == result.state
    assert replayed.effects == ()
