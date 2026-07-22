from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from polyhorizon.canonical import domain_digest
from polyhorizon.errors import ProtocolError
from polyhorizon.kernel import DecisionEffect, PureKernel, SessionState, SessionStatus
from polyhorizon.models import ObligationMode, ReceiptStatus, Reversibility, Standing

from .helpers import NOW, make_charter, make_proposal, receipt_for, revised


def test_open_compiles_independent_observer_requests() -> None:
    charter = make_charter()
    result = PureKernel().open(charter, make_proposal(charter), now=NOW)

    assert result.state.status is SessionStatus.AWAITING_EFFECTS
    assert {item.provider for item in result.effects} == {"host.observe-a", "host.observe-b"}
    assert {item.group for item in result.effects} == {"obligation:no-regression"}
    assert result.state.digest.startswith("sha256:")


def test_matching_horizon_without_obligation_escalates_instead_of_vacuous_allow() -> None:
    charter = make_charter()
    uncovered = replace(charter.horizons[0], id="uncovered-horizon")
    guarded = replace(charter, horizons=(*charter.horizons, uncovered))
    proposal = make_proposal(guarded)
    claim = replace(
        proposal.claims[0],
        horizons=(*proposal.claims[0].horizons, uncovered.id),
    )
    result = PureKernel().open(guarded, replace(proposal, claims=(claim,)), now=NOW)

    assert result.decision is not None
    assert result.decision.effect is DecisionEffect.ESCALATE
    assert result.decision.reasons == ("uncovered_obligation:impact-1:uncovered-horizon",)


def test_declared_standing_without_an_applicable_obligation_escalates() -> None:
    charter = make_charter()
    workers = Standing(
        id="workers",
        representatives=("representative",),
        rights=("contest",),
    )
    guarded = replace(charter, standings=(*charter.standings, workers))
    proposal = make_proposal(guarded)
    claim = replace(proposal.claims[0], standings=(*proposal.claims[0].standings, workers.id))
    result = PureKernel().open(guarded, replace(proposal, claims=(claim,)), now=NOW)

    assert result.decision is not None
    assert result.decision.effect is DecisionEffect.ESCALATE
    assert result.decision.reasons == ("uncovered_standing:impact-1:workers",)


def test_declared_horizon_whose_selectors_do_not_match_escalates() -> None:
    charter = make_charter()
    unmatched = replace(
        charter.horizons[0],
        id="unmatched-horizon",
        selectors=replace(charter.horizons[0].selectors, effects=("other.*",)),
    )
    guarded = replace(charter, horizons=(*charter.horizons, unmatched))
    proposal = make_proposal(guarded)
    claim = replace(proposal.claims[0], horizons=(*proposal.claims[0].horizons, unmatched.id))
    result = PureKernel().open(guarded, replace(proposal, claims=(claim,)), now=NOW)

    assert result.decision is not None
    assert result.decision.effect is DecisionEffect.ESCALATE
    assert result.decision.reasons == ("unmatched_horizon:impact-1:unmatched-horizon",)


def test_all_hard_horizons_satisfied_allows_without_scalarization() -> None:
    charter = make_charter()
    kernel = PureKernel()
    opened = kernel.open(charter, make_proposal(charter), now=NOW)
    result = kernel.advance(
        charter,
        opened.state,
        [receipt_for(item) for item in opened.effects],
        now=NOW + timedelta(minutes=2),
    )

    assert result.decision is not None
    assert result.decision.effect is DecisionEffect.ALLOW
    assert result.decision.horizon_vector[0].horizon_id == "long-term"
    assert result.decision.horizon_vector[0].effect is DecisionEffect.ALLOW


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ReceiptStatus.VIOLATED, DecisionEffect.DENY),
        (ReceiptStatus.UNKNOWN, DecisionEffect.ESCALATE),
        (ReceiptStatus.UNCOVERED, DecisionEffect.ESCALATE),
    ],
)
def test_hard_obligation_status_is_fail_closed(
    status: ReceiptStatus, expected: DecisionEffect
) -> None:
    charter = make_charter()
    kernel = PureKernel()
    opened = kernel.open(charter, make_proposal(charter), now=NOW)
    receipts = [
        receipt_for(item, status if index == 0 else ReceiptStatus.SATISFIED)
        for index, item in enumerate(opened.effects)
    ]
    result = kernel.advance(charter, opened.state, receipts, now=NOW + timedelta(minutes=2))
    assert result.decision is not None
    assert result.decision.effect is expected


def test_review_violation_escalates_and_advisory_violation_remains_vector() -> None:
    for mode, expected in (
        (ObligationMode.REVIEW, DecisionEffect.ESCALATE),
        (ObligationMode.ADVISORY, DecisionEffect.ALLOW),
    ):
        charter = make_charter(obligation_mode=mode)
        kernel = PureKernel()
        opened = kernel.open(charter, make_proposal(charter), now=NOW)
        result = kernel.advance(
            charter,
            opened.state,
            [receipt_for(item, ReceiptStatus.VIOLATED) for item in opened.effects],
            now=NOW + timedelta(minutes=2),
        )
        assert result.decision is not None
        assert result.decision.effect is expected


@pytest.mark.parametrize(
    ("horizons", "standings", "effect", "reason"),
    [
        ((), ("users",), "code.performance", "undeclared_horizon"),
        (("long-term",), (), "code.performance", "unrepresented_standing"),
        (("long-term",), ("users",), "external.transfer", "uncovered_claim"),
    ],
)
def test_coverage_debt_escalates_before_observers(
    horizons: tuple[str, ...], standings: tuple[str, ...], effect: str, reason: str
) -> None:
    charter = make_charter()
    result = PureKernel().open(
        charter,
        make_proposal(charter, horizons=horizons, standings=standings, effect=effect),
        now=NOW,
    )
    assert result.decision is not None
    assert result.decision.effect is DecisionEffect.ESCALATE
    assert result.effects == ()
    assert any(item.startswith(reason) for item in result.decision.reasons)


def test_missing_active_mandate_denies() -> None:
    charter = make_charter()
    charter = replace(charter, mandates=())
    result = PureKernel().open(charter, make_proposal(charter), now=NOW)
    assert result.decision is not None
    assert result.decision.effect is DecisionEffect.DENY
    assert result.decision.reasons == ("actor_lacks_active_mandate",)


def test_compensatable_motion_requires_reserved_recourse() -> None:
    charter = make_charter()
    proposal = make_proposal(charter, reversibility=Reversibility.COMPENSATABLE)
    opened = PureKernel().open(charter, proposal, now=NOW)
    assert any(item.kind == "polyhorizon.recourse.reserve" for item in opened.effects)

    no_recourse = replace(charter, obligations=(replace(charter.obligations[0], recourse_ids=()),))
    denied = PureKernel().open(
        no_recourse,
        make_proposal(no_recourse, reversibility=Reversibility.COMPENSATABLE),
        now=NOW,
    )
    assert denied.decision is not None
    assert denied.decision.effect is DecisionEffect.DENY
    assert denied.decision.reasons == ("hard_recourse_missing:no-regression",)


def test_partial_advance_preserves_pending_effects() -> None:
    charter = make_charter()
    kernel = PureKernel()
    opened = kernel.open(charter, make_proposal(charter), now=NOW)
    partial = kernel.advance(
        charter,
        opened.state,
        (receipt_for(opened.effects[0]),),
        now=NOW + timedelta(minutes=2),
    )
    assert partial.state.sequence == 1
    assert partial.decision is None
    assert len(partial.effects) == 1
    completed = kernel.advance(
        charter,
        partial.state,
        (receipt_for(partial.effects[0]),),
        now=NOW + timedelta(minutes=3),
    )
    assert completed.decision is not None
    assert completed.decision.effect is DecisionEffect.ALLOW


def test_receipt_replay_wrong_producer_and_expiry_are_rejected() -> None:
    charter = make_charter()
    kernel = PureKernel()
    opened = kernel.open(charter, make_proposal(charter), now=NOW)
    request = opened.effects[0]
    with pytest.raises(ProtocolError, match="not authorized"):
        kernel.advance(
            charter,
            opened.state,
            (receipt_for(request, producer="actor"),),
            now=NOW + timedelta(minutes=2),
        )
    future = receipt_for(request, issued_at=NOW + timedelta(minutes=5))
    with pytest.raises(ProtocolError, match="outside"):
        kernel.advance(
            charter,
            opened.state,
            (future,),
            now=NOW + timedelta(minutes=2),
        )
    replay = receipt_for(request)
    partial = kernel.advance(charter, opened.state, (replay,), now=NOW + timedelta(minutes=2))
    with pytest.raises(ProtocolError, match=r"duplicate|only once"):
        kernel.advance(charter, partial.state, (replay,), now=NOW + timedelta(minutes=3))


def test_session_rejects_foreign_request_bindings() -> None:
    charter = make_charter()
    opened = PureKernel().open(charter, make_proposal(charter), now=NOW)
    request = replace(opened.effects[0], session_id="other-session")
    with pytest.raises(ValueError, match="request binding"):
        SessionState(
            id=opened.state.id,
            sequence=0,
            status=SessionStatus.AWAITING_EFFECTS,
            charter_digest=opened.state.charter_digest,
            proposal_digest=opened.state.proposal_digest,
            idempotency_key=opened.state.idempotency_key,
            opened_at=opened.state.opened_at,
            expires_at=opened.state.expires_at,
            requests=(request,),
        )


def test_restored_session_revalidates_receipt_authority_and_time() -> None:
    charter = make_charter()
    opened = PureKernel().open(charter, make_proposal(charter), now=NOW)
    request = opened.effects[0]
    unauthorized = replace(receipt_for(request), producer="actor")
    with pytest.raises(ValueError, match="producer"):
        replace(opened.state, sequence=1, receipts=(unauthorized,))

    late = receipt_for(request, issued_at=request.expires_at)
    with pytest.raises(ValueError, match="timestamp"):
        replace(opened.state, sequence=1, receipts=(late,))


def test_advance_requires_evidence_until_expiry_tick() -> None:
    charter = make_charter()
    kernel = PureKernel()
    opened = kernel.open(charter, make_proposal(charter), now=NOW)
    with pytest.raises(ProtocolError, match="at least one receipt"):
        kernel.advance(charter, opened.state, (), now=NOW + timedelta(minutes=1))

    expired = kernel.advance(charter, opened.state, (), now=opened.state.expires_at)
    assert expired.decision is not None
    assert expired.decision.effect is DecisionEffect.ESCALATE


def test_amendment_is_ratifed_by_predecessor_not_candidate() -> None:
    charter = make_charter()
    candidate_standing = Standing(
        id="users",
        representatives=("actor",),
        rights=charter.standings[0].rights,
    )
    candidate = revised(charter, standings=(candidate_standing,))
    proposal = make_proposal(charter, candidate=candidate)
    opened = PureKernel().open(charter, proposal, candidate=candidate, now=NOW)

    ratify = next(item for item in opened.effects if item.kind == "polyhorizon.amendment.ratify")
    consent = next(item for item in opened.effects if item.kind == "polyhorizon.standing.consent")
    assert ratify.allowed_producers == ("representative",)
    assert consent.allowed_producers == ("representative",)
    assert "actor" not in ratify.allowed_producers
    assert ratify.payload["predecessor_ledger_root"] == proposal.ledger_root_digest
    change_set = ratify.payload["change_set"]
    assert "standings" in change_set["collections"]
    assert ratify.payload["change_set_digest"] == domain_digest(
        "charter-change-set",
        {
            "change_set": change_set,
            "predecessor_ledger_root": proposal.ledger_root_digest,
        },
    )


def test_amendment_requires_a_bound_predecessor_ledger_root() -> None:
    charter = make_charter()
    candidate = revised(charter)
    with pytest.raises(ValueError, match="ledger root"):
        replace(make_proposal(charter, candidate=candidate), ledger_root_digest=None)


def test_principal_identity_change_requires_predecessor_release() -> None:
    charter = make_charter()
    candidate = revised(
        charter,
        principals=tuple(
            replace(principal, trust_domain="replacement-domain", adapter="host.replacement")
            if principal.id == "observer-a"
            else principal
            for principal in charter.principals
        ),
    )
    opened = PureKernel().open(
        charter, make_proposal(charter, candidate=candidate), candidate=candidate, now=NOW
    )
    release = next(item for item in opened.effects if item.kind == "polyhorizon.principal.release")
    assert release.provider == "host.observe-a"
    assert release.allowed_producers == ("observer-a",)
    assert release.payload["trust_domain_changed"] is True
    assert release.payload["adapter_changed"] is True
    assert release.payload["before"]["adapter"] == "host.observe-a"
    assert release.payload["after"]["adapter"] == "host.replacement"


def test_changed_obligation_requires_beneficiary_discharge() -> None:
    charter = make_charter()
    changed = replace(charter.obligations[0], predicate="quality.weaker-rule")
    candidate = revised(charter, obligations=(changed,))
    opened = PureKernel().open(
        charter, make_proposal(charter, candidate=candidate), candidate=candidate, now=NOW
    )
    discharge = [item for item in opened.effects if item.kind == "polyhorizon.obligation.discharge"]
    assert len(discharge) == 1
    assert discharge[0].allowed_producers == ("representative",)


def test_amendment_root_rejection_denies() -> None:
    charter = make_charter()
    candidate = revised(charter)
    kernel = PureKernel()
    opened = kernel.open(
        charter, make_proposal(charter, candidate=candidate), candidate=candidate, now=NOW
    )
    receipts = [
        receipt_for(
            request,
            ReceiptStatus.VIOLATED
            if request.kind == "polyhorizon.amendment.root"
            else ReceiptStatus.SATISFIED,
        )
        for request in opened.effects
    ]
    result = kernel.advance(charter, opened.state, receipts, now=NOW + timedelta(minutes=2))
    assert result.decision is not None
    assert result.decision.effect is DecisionEffect.DENY


def test_candidate_mismatch_and_expired_proposal_fail_before_session() -> None:
    charter = make_charter()
    candidate = revised(charter)
    proposal = make_proposal(charter, candidate=candidate)
    with pytest.raises(ProtocolError, match="digest"):
        PureKernel().open(
            charter,
            proposal,
            candidate=replace(candidate, revision="v3"),
            now=NOW,
        )

    expired = replace(make_proposal(charter), expires_at=NOW - timedelta(seconds=1))
    with pytest.raises(ProtocolError, match="not active"):
        PureKernel().open(charter, expired, now=NOW)
