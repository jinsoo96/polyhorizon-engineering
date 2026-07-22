from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pytest

from polyhorizon.canonical import canonical_json, domain_digest, parse_datetime, selector_matches
from polyhorizon.errors import ProtocolError
from polyhorizon.handlers import HandlerRegistry, InProcessRunner
from polyhorizon.kernel import DecisionEffect
from polyhorizon.models import EffectReceipt, EffectRequest
from polyhorizon.runtime import Engine

from .helpers import NOW, make_charter, make_proposal, receipt_for


@dataclass
class SatisfyingHandler:
    def handle(self, request: EffectRequest) -> EffectReceipt:
        return receipt_for(request, issued_at=NOW)


def test_in_process_handlers_are_explicit_and_transport_equivalent() -> None:
    charter = make_charter()
    registry = HandlerRegistry(
        {"host.observe-a": SatisfyingHandler(), "host.observe-b": SatisfyingHandler()}
    )
    result = InProcessRunner(Engine(clock=lambda: NOW), registry).run(
        charter, make_proposal(charter)
    )
    assert result.decision is not None
    assert result.decision.effect is DecisionEffect.ALLOW


def test_missing_or_duplicate_handler_fails_closed() -> None:
    registry = HandlerRegistry()
    registry.register("host.observe-a", SatisfyingHandler())
    with pytest.raises(ValueError, match="already registered"):
        registry.register("host.observe-a", SatisfyingHandler())
    charter = make_charter()
    with pytest.raises(ProtocolError, match="no in-process handler"):
        InProcessRunner(Engine(clock=lambda: NOW), registry).run(charter, make_proposal(charter))


def test_canonical_material_is_order_independent_and_domain_separated() -> None:
    left = {"b": [2, 1], "a": "value"}
    right = {"a": "value", "b": [2, 1]}
    assert canonical_json(left) == canonical_json(right)
    assert domain_digest("alpha", left) == domain_digest("alpha", right)
    assert domain_digest("alpha", left) != domain_digest("beta", left)


@pytest.mark.parametrize(
    ("pattern", "value", "expected"),
    [
        ("*", "any.value", True),
        ("repo:*", "repo:demo", True),
        ("repo:*", "database:demo", False),
        ("exact", "exact", True),
    ],
)
def test_selector_profile_is_portable(pattern: str, value: str, expected: bool) -> None:
    assert selector_matches(pattern, value) is expected


def test_canonical_profile_rejects_unsafe_numbers() -> None:
    with pytest.raises(ValueError, match=r"finite|floating-point"):
        canonical_json({"value": float("nan")})
    with pytest.raises(ValueError, match="floating-point"):
        canonical_json({"value": 1.5})
    with pytest.raises(ValueError, match="interoperable"):
        canonical_json({"value": 2**60})
    with pytest.raises(ValueError, match="Unicode scalar"):
        canonical_json({"value": "\ud800"})


@pytest.mark.parametrize(
    "value",
    [
        "2026-07-22 12:00:00+00:00",
        "2026-W30-3T12:00:00Z",
        "2026-07-22T12:00:00",
        "2026-07-22t12:00:00z",
        "2026-07-22T12:00:00.1234567Z",
    ],
)
def test_datetime_parser_accepts_only_the_declared_rfc3339_profile(value: str) -> None:
    with pytest.raises(ValueError, match="RFC 3339"):
        parse_datetime(value, "timestamp")


def test_receipt_details_are_non_normative_and_result_digest_is_bound() -> None:
    charter = make_charter()
    request = Engine(clock=lambda: NOW).open(charter, make_proposal(charter)).effects[0]
    first = receipt_for(request)
    second = EffectReceipt(
        id=first.id,
        request_digest=first.request_digest,
        producer=first.producer,
        status=first.status,
        evidence_digest=first.evidence_digest,
        result_digest=first.result_digest,
        issued_at=first.issued_at,
        details={"different": "diagnostic only"},
    )
    assert first.digest == second.digest
    changed_result = EffectReceipt(
        id=first.id,
        request_digest=first.request_digest,
        producer=first.producer,
        status=first.status,
        evidence_digest=first.evidence_digest,
        result_digest=domain_digest("test-result", {"changed": True}),
        issued_at=first.issued_at + timedelta(seconds=1),
    )
    assert first.digest != changed_result.digest


def test_wire_visible_diagnostics_reject_unpaired_surrogates() -> None:
    charter = make_charter()
    request = Engine(clock=lambda: NOW).open(charter, make_proposal(charter)).effects[0]
    with pytest.raises(ValueError, match="Unicode scalar"):
        EffectReceipt(
            id="receipt-invalid-details",
            request_digest=request.digest,
            producer=request.allowed_producers[0],
            status=receipt_for(request).status,
            evidence_digest=domain_digest("test-evidence", {}),
            result_digest=domain_digest("test-result", {}),
            issued_at=NOW,
            details={"invalid": "\ud800"},
        )
