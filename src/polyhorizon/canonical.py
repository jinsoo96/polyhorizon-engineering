from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SELECTOR = re.compile(r"^(?:\*|[A-Za-z0-9][A-Za-z0-9._:/-]{0,126}\*?)$")
_RFC3339 = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T"
    r"(?P<time>\d{2}:\d{2}:\d{2})(?P<fraction>\.\d{1,6})?"
    r"(?P<offset>Z|[+-]\d{2}:\d{2})$"
)
_SAFE_INTEGER = 2**53 - 1


def require_identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} must be a portable identifier")
    return value


def require_digest(value: str, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{field} must be sha256:<64 lowercase hex>")
    return value


def require_selector(value: str, field: str) -> str:
    if not isinstance(value, str) or not _SELECTOR.fullmatch(value):
        raise ValueError(f"{field} must be an exact value, a terminal-prefix wildcard, or '*'")
    return value


def selector_matches(pattern: str, value: str) -> bool:
    require_selector(pattern, "selector")
    require_identifier(value, "selected value")
    if pattern == "*":
        return True
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])
    return value == pattern


def any_selector_matches(patterns: tuple[str, ...], value: str) -> bool:
    return any(selector_matches(pattern, value) for pattern in patterns)


def unique_identifiers(values: Sequence[str], field: str) -> tuple[str, ...]:
    checked = tuple(require_identifier(value, field) for value in values)
    if len(checked) != len(set(checked)):
        raise ValueError(f"{field} must not contain duplicates")
    return tuple(sorted(checked))


def unique_selectors(values: Sequence[str], field: str) -> tuple[str, ...]:
    checked = tuple(require_selector(value, field) for value in values)
    if len(checked) != len(set(checked)):
        raise ValueError(f"{field} must not contain duplicates")
    return tuple(sorted(checked))


def aware_datetime(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def parse_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an RFC 3339 string")
    if _RFC3339.fullmatch(value) is None:
        raise ValueError(f"{field} must be a valid RFC 3339 timestamp")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return aware_datetime(datetime.fromisoformat(candidate), field)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid RFC 3339 timestamp") from exc


def format_datetime(value: datetime) -> str:
    return aware_datetime(value, "datetime").isoformat().replace("+00:00", "Z")


def to_jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: to_jsonable(getattr(value, item.name))
            for item in dataclasses.fields(value)
            if not item.name.startswith("_")
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return format_datetime(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("JSON object keys must be strings")
        return {_scalar_text(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, set | frozenset):
        raise TypeError("sets are not deterministic JSON values")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > _SAFE_INTEGER:
        raise ValueError("integers in canonical material must fit the interoperable JSON range")
    if isinstance(value, str):
        return _scalar_text(value)
    if value is None or isinstance(value, int | bool):
        return value
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def freeze_json(value: Any) -> Any:
    normalized = to_jsonable(value)
    if isinstance(normalized, dict):
        return MappingProxyType({key: freeze_json(item) for key, item in normalized.items()})
    if isinstance(normalized, list):
        return tuple(freeze_json(item) for item in normalized)
    return normalized


def freeze_mapping(value: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    frozen = freeze_json({} if value is None else value)
    assert isinstance(frozen, Mapping)
    return frozen


def _scalar_text(value: str) -> str:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("canonical strings must contain only Unicode scalar values")
    return value


def _canonical_normalized(normalized: Any) -> Any:
    if isinstance(normalized, float):
        raise ValueError("floating-point numbers are not supported in canonical material")
    if isinstance(normalized, str):
        return _scalar_text(normalized)
    if isinstance(normalized, list):
        return [_canonical_normalized(item) for item in normalized]
    if isinstance(normalized, dict):
        keys = sorted(
            (_scalar_text(key) for key in normalized), key=lambda key: key.encode("utf-8")
        )
        return {key: _canonical_normalized(normalized[key]) for key in keys}
    return normalized


def _canonical_value(value: Any) -> Any:
    return _canonical_normalized(to_jsonable(value))


def canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=False,
        separators=(",", ":"),
    )


def domain_digest(domain: str, material: Any) -> str:
    require_identifier(domain, "digest domain")
    prefix = b"polyhorizon.engine.v1\x00" + domain.encode("ascii") + b"\x00"
    payload = prefix + canonical_json(material).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def content_digest(value: bytes | str) -> str:
    payload = value if isinstance(value, bytes) else value.encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
