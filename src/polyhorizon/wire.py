from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import TextIO

from polyhorizon.canonical import require_identifier, to_jsonable
from polyhorizon.errors import (
    ConcurrentUpdateError,
    ManifestError,
    PolyhorizonError,
    ProtocolError,
)
from polyhorizon.models import CHARTER_API, EFFECT_API, PROPOSAL_API, Charter, Proposal
from polyhorizon.runtime import Engine
from polyhorizon.serde import effect_receipt_from_dict, step_to_dict

WIRE_API = "polyhorizon.wire/v0.1"
DEFAULT_MAX_LINE_BYTES = 4 * 1024 * 1024


class WireError(PolyhorizonError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = require_identifier(code, "wire error code")


class DuplicateKeyError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def decode_json(value: str) -> object:
    return to_jsonable(json.loads(value, object_pairs_hook=_unique_object))


def _write_response(outstream: TextIO, response: Mapping[str, object]) -> None:
    outstream.write(json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    outstream.write("\n")
    outstream.flush()


def _object(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise WireError("invalid_envelope", f"{path} must be an object")
    return value


def _array(value: object, path: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise WireError("invalid_envelope", f"{path} must be an array")
    return value


def _string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise WireError("invalid_envelope", f"{path} must be a string")
    return value


def _integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise WireError("invalid_envelope", f"{path} must be an integer")
    return value


def _only_keys(value: Mapping[str, object], allowed: set[str], path: str) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise WireError(
            "invalid_envelope", f"{path} contains unsupported fields: {', '.join(unexpected)}"
        )


class WireEngine:
    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = Engine() if engine is None else engine

    @staticmethod
    def capabilities() -> dict[str, object]:
        return {
            "wire_api": WIRE_API,
            "domain_apis": [CHARTER_API, PROPOSAL_API, EFFECT_API],
            "commands": ["abort", "advance", "capabilities", "inspect", "open"],
            "transport": "ndjson",
            "effect_execution": "host-owned",
            "digest_profile": "polyhorizon.engine.v1",
        }

    def handle(self, envelope: object) -> dict[str, object]:
        request_id = "unknown"
        try:
            item = _object(to_jsonable(envelope), "$")
            _only_keys(item, {"api_version", "request_id", "command", "payload"}, "$")
            api_version = _string(item.get("api_version"), "$.api_version")
            if api_version != WIRE_API:
                raise WireError("unsupported_version", f"api_version must be {WIRE_API}")
            candidate_request_id = _string(item.get("request_id"), "$.request_id")
            require_identifier(candidate_request_id, "request_id")
            request_id = candidate_request_id
            command = _string(item.get("command"), "$.command")
            require_identifier(command, "command")
            payload = _object(item.get("payload", {}), "$.payload")
            result = self._dispatch(command, payload)
            return {
                "api_version": WIRE_API,
                "request_id": request_id,
                "ok": True,
                "payload": result,
            }
        except WireError as exc:
            return self._error(request_id, exc.code, str(exc))
        except ManifestError as exc:
            return self._error(request_id, "manifest_error", str(exc))
        except ConcurrentUpdateError as exc:
            return self._error(request_id, "concurrent_update", str(exc))
        except ProtocolError as exc:
            return self._error(request_id, "protocol_error", str(exc))
        except (TypeError, ValueError) as exc:
            return self._error(request_id, "invalid_value", str(exc))
        except Exception:
            return self._error(request_id, "internal_error", "internal engine failure")

    @staticmethod
    def _error(request_id: str, code: str, message: str) -> dict[str, object]:
        return {
            "api_version": WIRE_API,
            "request_id": request_id,
            "ok": False,
            "error": {"code": code, "message": message},
        }

    def _dispatch(self, command: str, payload: Mapping[str, object]) -> dict[str, object]:
        if command == "capabilities":
            _only_keys(payload, set(), "$.payload")
            return self.capabilities()
        if command == "open":
            _only_keys(payload, {"charter", "proposal", "candidate"}, "$.payload")
            charter = Charter.from_dict(payload.get("charter"), "$.payload.charter")
            proposal = Proposal.from_dict(payload.get("proposal"), "$.payload.proposal")
            candidate_value = payload.get("candidate")
            candidate = (
                None
                if candidate_value is None
                else Charter.from_dict(candidate_value, "$.payload.candidate")
            )
            return step_to_dict(self.engine.open(charter, proposal, candidate=candidate))
        if command == "advance":
            _only_keys(
                payload,
                {"charter", "session_id", "expected_sequence", "receipts"},
                "$.payload",
            )
            charter = Charter.from_dict(payload.get("charter"), "$.payload.charter")
            session_id = _string(payload.get("session_id"), "$.payload.session_id")
            expected = _integer(payload.get("expected_sequence"), "$.payload.expected_sequence")
            receipts = tuple(
                effect_receipt_from_dict(value, f"$.payload.receipts[{index}]")
                for index, value in enumerate(_array(payload.get("receipts"), "$.payload.receipts"))
            )
            return step_to_dict(self.engine.advance(charter, session_id, expected, receipts))
        if command == "inspect":
            _only_keys(payload, {"session_id"}, "$.payload")
            session_id = _string(payload.get("session_id"), "$.payload.session_id")
            state = self.engine.inspect(session_id)
            if state is None:
                raise WireError("not_found", "session does not exist")
            return {"state": to_jsonable(state), "state_digest": state.digest}
        if command == "abort":
            _only_keys(payload, {"session_id", "expected_sequence"}, "$.payload")
            session_id = _string(payload.get("session_id"), "$.payload.session_id")
            expected = _integer(payload.get("expected_sequence"), "$.payload.expected_sequence")
            return step_to_dict(self.engine.abort(session_id, expected))
        raise WireError("unsupported_command", f"unsupported command: {command}")


def serve(
    engine: WireEngine,
    instream: TextIO,
    outstream: TextIO,
    *,
    max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
) -> int:
    if (
        isinstance(max_line_bytes, bool)
        or not isinstance(max_line_bytes, int)
        or max_line_bytes < 1
    ):
        raise ValueError("max_line_bytes must be a positive integer")
    read_limit = max_line_bytes + 1
    while True:
        try:
            line = instream.readline(read_limit)
        except UnicodeDecodeError:
            _write_response(
                outstream,
                WireEngine._error("unknown", "invalid_json", "line is not valid UTF-8 JSON"),
            )
            break
        if line == "":
            break
        truncated = len(line) == read_limit and not line.endswith("\n")
        if truncated:
            while line and not line.endswith("\n"):
                try:
                    line = instream.readline(read_limit)
                except UnicodeDecodeError:
                    _write_response(
                        outstream,
                        WireEngine._error(
                            "unknown", "invalid_json", "line is not valid UTF-8 JSON"
                        ),
                    )
                    return 0
            response = WireEngine._error(
                "unknown", "message_too_large", "wire message is too large"
            )
            _write_response(outstream, response)
            continue
        if not line.strip():
            continue
        try:
            encoded_size = len(line.encode("utf-8"))
        except UnicodeEncodeError:
            response = WireEngine._error("unknown", "invalid_json", "line is not valid JSON")
        else:
            if encoded_size > max_line_bytes:
                response = WireEngine._error(
                    "unknown", "message_too_large", "wire message is too large"
                )
            else:
                try:
                    message = decode_json(line)
                except (json.JSONDecodeError, DuplicateKeyError, RecursionError, ValueError):
                    response = WireEngine._error(
                        "unknown", "invalid_json", "line is not valid JSON"
                    )
                else:
                    response = engine.handle(message)
        _write_response(outstream, response)
    return 0
