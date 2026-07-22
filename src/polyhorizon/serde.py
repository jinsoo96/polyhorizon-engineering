from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar

from polyhorizon.canonical import parse_datetime, to_jsonable
from polyhorizon.errors import ManifestError
from polyhorizon.kernel import (
    Decision,
    DecisionEffect,
    HorizonResult,
    SessionState,
    SessionStatus,
    StepResult,
)
from polyhorizon.models import EffectReceipt, EffectRequest, ReceiptStatus

T = TypeVar("T")


def _manifest(path: str, builder: Callable[[], T]) -> T:
    try:
        return builder()
    except ManifestError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestError(f"{path}: {exc}") from exc


def _object(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ManifestError(f"{path} must be an object")
    return value


def _array(value: object, path: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ManifestError(f"{path} must be an array")
    return value


def _str(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise ManifestError(f"{path} must be a string")
    return value


def _int(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(f"{path} must be an integer")
    return value


def _keys(value: Mapping[str, object], allowed: set[str], path: str) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ManifestError(f"{path} contains unsupported fields: {', '.join(unexpected)}")


def effect_request_from_dict(value: object, path: str = "$") -> EffectRequest:
    item = _object(value, path)
    _keys(
        item,
        {
            "api_version",
            "id",
            "kind",
            "session_id",
            "sequence",
            "charter_digest",
            "proposal_digest",
            "provider",
            "allowed_producers",
            "group",
            "payload",
            "expires_at",
        },
        path,
    )
    try:
        return EffectRequest(
            api_version=_str(item.get("api_version"), f"{path}.api_version"),
            id=_str(item.get("id"), f"{path}.id"),
            kind=_str(item.get("kind"), f"{path}.kind"),
            session_id=_str(item.get("session_id"), f"{path}.session_id"),
            sequence=_int(item.get("sequence"), f"{path}.sequence"),
            charter_digest=_str(item.get("charter_digest"), f"{path}.charter_digest"),
            proposal_digest=_str(item.get("proposal_digest"), f"{path}.proposal_digest"),
            provider=_str(item.get("provider"), f"{path}.provider"),
            allowed_producers=tuple(
                _str(member, f"{path}.allowed_producers[]")
                for member in _array(item.get("allowed_producers"), f"{path}.allowed_producers")
            ),
            group=_str(item.get("group"), f"{path}.group"),
            payload=_object(item.get("payload"), f"{path}.payload"),
            expires_at=parse_datetime(item.get("expires_at"), f"{path}.expires_at"),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ManifestError):
            raise
        raise ManifestError(str(exc)) from exc


def effect_receipt_from_dict(value: object, path: str = "$") -> EffectReceipt:
    item = _object(value, path)
    _keys(
        item,
        {
            "api_version",
            "id",
            "request_digest",
            "producer",
            "status",
            "evidence_digest",
            "result_digest",
            "issued_at",
            "details",
        },
        path,
    )
    try:
        return EffectReceipt(
            api_version=_str(item.get("api_version"), f"{path}.api_version"),
            id=_str(item.get("id"), f"{path}.id"),
            request_digest=_str(item.get("request_digest"), f"{path}.request_digest"),
            producer=_str(item.get("producer"), f"{path}.producer"),
            status=ReceiptStatus(_str(item.get("status"), f"{path}.status")),
            evidence_digest=_str(item.get("evidence_digest"), f"{path}.evidence_digest"),
            result_digest=_str(item.get("result_digest"), f"{path}.result_digest"),
            issued_at=parse_datetime(item.get("issued_at"), f"{path}.issued_at"),
            details=_object(item.get("details", {}), f"{path}.details"),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ManifestError):
            raise
        raise ManifestError(str(exc)) from exc


def horizon_result_from_dict(value: object, path: str) -> HorizonResult:
    item = _object(value, path)
    _keys(item, {"horizon_id", "effect", "obligations", "reasons"}, path)
    return _manifest(
        path,
        lambda: HorizonResult(
            horizon_id=_str(item.get("horizon_id"), f"{path}.horizon_id"),
            effect=DecisionEffect(_str(item.get("effect"), f"{path}.effect")),
            obligations=tuple(
                _str(member, f"{path}.obligations[]")
                for member in _array(item.get("obligations"), f"{path}.obligations")
            ),
            reasons=tuple(
                _str(member, f"{path}.reasons[]")
                for member in _array(item.get("reasons", []), f"{path}.reasons")
            ),
        ),
    )


def decision_from_dict(value: object, path: str = "$") -> Decision:
    item = _object(value, path)
    _keys(
        item,
        {"effect", "charter_digest", "proposal_digest", "reasons", "horizon_vector"},
        path,
    )
    return _manifest(
        path,
        lambda: Decision(
            effect=DecisionEffect(_str(item.get("effect"), f"{path}.effect")),
            charter_digest=_str(item.get("charter_digest"), f"{path}.charter_digest"),
            proposal_digest=_str(item.get("proposal_digest"), f"{path}.proposal_digest"),
            reasons=tuple(
                _str(member, f"{path}.reasons[]")
                for member in _array(item.get("reasons"), f"{path}.reasons")
            ),
            horizon_vector=tuple(
                horizon_result_from_dict(member, f"{path}.horizon_vector[{index}]")
                for index, member in enumerate(
                    _array(item.get("horizon_vector", []), f"{path}.horizon_vector")
                )
            ),
        ),
    )


def session_from_dict(value: object, path: str = "$") -> SessionState:
    item = _object(value, path)
    _keys(
        item,
        {
            "id",
            "sequence",
            "status",
            "charter_digest",
            "proposal_digest",
            "idempotency_key",
            "opened_at",
            "expires_at",
            "requests",
            "receipts",
            "decision",
        },
        path,
    )
    decision_value = item.get("decision")
    return _manifest(
        path,
        lambda: SessionState(
            id=_str(item.get("id"), f"{path}.id"),
            sequence=_int(item.get("sequence"), f"{path}.sequence"),
            status=SessionStatus(_str(item.get("status"), f"{path}.status")),
            charter_digest=_str(item.get("charter_digest"), f"{path}.charter_digest"),
            proposal_digest=_str(item.get("proposal_digest"), f"{path}.proposal_digest"),
            idempotency_key=_str(item.get("idempotency_key"), f"{path}.idempotency_key"),
            opened_at=parse_datetime(item.get("opened_at"), f"{path}.opened_at"),
            expires_at=parse_datetime(item.get("expires_at"), f"{path}.expires_at"),
            requests=tuple(
                effect_request_from_dict(member, f"{path}.requests[{index}]")
                for index, member in enumerate(_array(item.get("requests"), f"{path}.requests"))
            ),
            receipts=tuple(
                effect_receipt_from_dict(member, f"{path}.receipts[{index}]")
                for index, member in enumerate(_array(item.get("receipts", []), f"{path}.receipts"))
            ),
            decision=(
                None
                if decision_value is None
                else decision_from_dict(decision_value, f"{path}.decision")
            ),
        ),
    )


def step_to_dict(result: StepResult) -> dict[str, Any]:
    return {
        "state": to_jsonable(result.state),
        "state_digest": result.state.digest,
        "effects": to_jsonable(result.effects),
        "decision": None if result.decision is None else to_jsonable(result.decision),
    }


def to_dict(value: object) -> Any:
    return to_jsonable(value)
