from __future__ import annotations

import copy
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

from polyhorizon.canonical import canonical_json, domain_digest
from polyhorizon.kernel import PureKernel, SessionStatus
from polyhorizon.models import Charter, Proposal
from polyhorizon.runtime import Engine
from polyhorizon.serde import effect_receipt_from_dict
from polyhorizon.wire import WIRE_API, WireEngine

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "schemas"
EXAMPLE_ROOT = ROOT / "examples"
FORGE_ROOT = EXAMPLE_ROOT / "forge-mutation"
NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


SCHEMA_DOCUMENTS = {
    path.name: load_json(path) for path in sorted(SCHEMA_ROOT.glob("*.schema.json"))
}
REGISTRY = Registry().with_resources(
    (schema["$id"], Resource.from_contents(schema)) for schema in SCHEMA_DOCUMENTS.values()
)


def validate(schema_name: str, instance: object) -> None:
    Draft202012Validator(
        SCHEMA_DOCUMENTS[schema_name],
        registry=REGISTRY,
        format_checker=FormatChecker(),
    ).validate(instance)


def forge_manifests() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_json(FORGE_ROOT / "charter.v1.json"),
        load_json(FORGE_ROOT / "charter.v1.1-candidate.json"),
        load_json(FORGE_ROOT / "proposal.json"),
    )


def test_all_public_schemas_are_draft_2020_12() -> None:
    assert set(SCHEMA_DOCUMENTS) == {
        "charter.schema.json",
        "effect-receipt.schema.json",
        "proposal.schema.json",
        "wire.schema.json",
    }
    for schema in SCHEMA_DOCUMENTS.values():
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_forge_mutation_manifests_match_schema_and_runtime() -> None:
    base_value, candidate_value, proposal_value = forge_manifests()
    validate("charter.schema.json", base_value)
    validate("charter.schema.json", candidate_value)
    validate("proposal.schema.json", proposal_value)

    base = Charter.from_dict(base_value)
    candidate = Charter.from_dict(candidate_value)
    proposal = Proposal.from_dict(proposal_value)
    assert proposal.base_charter_digest == base.digest
    assert proposal.candidate_charter_digest == candidate.digest
    assert base.id == candidate.id
    assert base.revision != candidate.revision


def test_schema_rejects_extensions_that_runtime_rejects() -> None:
    charter_value, _, proposal_value = forge_manifests()
    extended_charter = copy.deepcopy(charter_value)
    extended_charter["ambient_authority"] = True
    with pytest.raises(ValidationError):
        validate("charter.schema.json", extended_charter)

    extended_proposal = copy.deepcopy(proposal_value)
    extended_proposal["forge_score"] = 1.0
    with pytest.raises(ValidationError):
        validate("proposal.schema.json", extended_proposal)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-07-16 12:00:00+00:00",
        "2026-07-16t12:00:00z",
        "2026-07-16T12:00:00.1234567Z",
    ],
)
def test_schema_timestamp_profile_matches_runtime(timestamp: str) -> None:
    charter_value, _, proposal_value = forge_manifests()
    invalid_proposal = copy.deepcopy(proposal_value)
    invalid_proposal["issued_at"] = timestamp
    with pytest.raises(ValidationError):
        validate("proposal.schema.json", invalid_proposal)

    invalid_charter = copy.deepcopy(charter_value)
    invalid_charter["mandates"][0]["issued_at"] = timestamp
    with pytest.raises(ValidationError):
        validate("charter.schema.json", invalid_charter)

    receipt = copy.deepcopy(
        load_json(EXAMPLE_ROOT / "conformance" / "digests.json")["effect_receipt_vectors"][0][
            "value"
        ]
    )
    receipt["issued_at"] = timestamp
    with pytest.raises(ValidationError):
        validate("effect-receipt.schema.json", receipt)


def test_forge_mutation_requests_predecessor_authority() -> None:
    base_value, candidate_value, proposal_value = forge_manifests()
    result = PureKernel().open(
        Charter.from_dict(base_value),
        Proposal.from_dict(proposal_value),
        candidate=Charter.from_dict(candidate_value),
        now=NOW,
    )
    kinds = Counter(request.kind for request in result.effects)
    assert result.state.status is SessionStatus.AWAITING_EFFECTS
    assert kinds["polyhorizon.obligation.assess"] == 8
    assert kinds["polyhorizon.recourse.reserve"] == 5
    assert kinds["polyhorizon.amendment.ratify"] == 3
    assert kinds["polyhorizon.amendment.root"] == 1
    assert kinds["polyhorizon.obligation.discharge"] == 1
    assert kinds["polyhorizon.horizon.release"] == 1
    assert kinds["polyhorizon.purpose.release"] == 1


def test_digest_conformance_corpus() -> None:
    corpus_path = EXAMPLE_ROOT / "conformance" / "digests.json"
    corpus = load_json(corpus_path)
    assert corpus["profile"] == "polyhorizon.engine.v1"

    for vector in corpus["canonical_vectors"]:
        assert canonical_json(vector["material"]) == vector["canonical_json"]
        assert domain_digest(vector["domain"], vector["material"]) == vector["digest"]

    factories = {"charter": Charter.from_dict, "proposal": Proposal.from_dict}
    for vector in corpus["manifest_vectors"]:
        value = load_json((corpus_path.parent / vector["path"]).resolve())
        assert factories[vector["kind"]](value).digest == vector["digest"]

    for vector in corpus["effect_receipt_vectors"]:
        validate("effect-receipt.schema.json", vector["value"])
        receipt = effect_receipt_from_dict(vector["value"])
        assert receipt.digest == vector["digest"]
        changed_details = copy.deepcopy(vector["value"])
        changed_details["details"] = {"transport_note": "not digest material"}
        assert effect_receipt_from_dict(changed_details).digest == vector["digest"]


def test_wire_schema_covers_requests_and_engine_responses() -> None:
    base_value, candidate_value, proposal_value = forge_manifests()
    client = WireEngine(Engine(clock=lambda: NOW))
    capabilities_request = {
        "api_version": WIRE_API,
        "request_id": "schema-capabilities",
        "command": "capabilities",
        "payload": {},
    }
    validate("wire.schema.json", capabilities_request)
    capabilities = client.handle(capabilities_request)
    validate("wire.schema.json", capabilities)

    open_request = {
        "api_version": WIRE_API,
        "request_id": "schema-open",
        "command": "open",
        "payload": {
            "charter": base_value,
            "candidate": candidate_value,
            "proposal": proposal_value,
        },
    }
    validate("wire.schema.json", open_request)
    opened = client.handle(open_request)
    validate("wire.schema.json", opened)
    assert opened["ok"] is True
    session = opened["payload"]["state"]

    inspect_request = {
        "api_version": WIRE_API,
        "request_id": "schema-inspect",
        "command": "inspect",
        "payload": {"session_id": session["id"]},
    }
    validate("wire.schema.json", inspect_request)
    validate("wire.schema.json", client.handle(inspect_request))

    abort_request = {
        "api_version": WIRE_API,
        "request_id": "schema-abort",
        "command": "abort",
        "payload": {
            "session_id": session["id"],
            "expected_sequence": session["sequence"],
        },
    }
    validate("wire.schema.json", abort_request)
    validate("wire.schema.json", client.handle(abort_request))

    advance_request = {
        "api_version": WIRE_API,
        "request_id": "schema-advance",
        "command": "advance",
        "payload": {
            "charter": base_value,
            "session_id": session["id"],
            "expected_sequence": session["sequence"],
            "receipts": [],
        },
    }
    validate("wire.schema.json", advance_request)

    unsupported = client.handle(
        {
            "api_version": WIRE_API,
            "request_id": "schema-unsupported",
            "command": "unknown",
            "payload": {},
        }
    )
    validate("wire.schema.json", unsupported)
    assert unsupported["ok"] is False


def test_wire_schema_rejects_ambiguous_or_extended_envelopes() -> None:
    with pytest.raises(ValidationError):
        validate(
            "wire.schema.json",
            {
                "api_version": WIRE_API,
                "request_id": "bad-capabilities",
                "command": "capabilities",
                "payload": {"ambient_authority": True},
            },
        )
