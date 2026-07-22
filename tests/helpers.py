from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from polyhorizon.canonical import content_digest
from polyhorizon.models import (
    AmendmentRule,
    Charter,
    EffectReceipt,
    EffectRequest,
    Horizon,
    ImpactClaim,
    Mandate,
    Obligation,
    ObligationMode,
    Principal,
    Proposal,
    Purpose,
    ReceiptStatus,
    Recourse,
    Reversibility,
    SelectorSet,
    Standing,
)

NOW = datetime(2026, 7, 22, 0, 0, tzinfo=UTC)


def digest(value: str) -> str:
    return content_digest(value)


def make_charter(
    *,
    revision: str = "v1",
    obligation_mode: ObligationMode = ObligationMode.HARD,
    reversibilities: tuple[Reversibility, ...] = (
        Reversibility.COMPENSATABLE,
        Reversibility.IRREVERSIBLE,
    ),
) -> Charter:
    selectors = SelectorSet(effects=("code.*",), resources=("repo:*",))
    return Charter(
        id="demo-charter",
        revision=revision,
        principals=(
            Principal("actor", "forge", "host.actor"),
            Principal("observer-a", "evaluation-a", "host.observe-a"),
            Principal("observer-b", "evaluation-b", "host.observe-b"),
            Principal("owner", "governance", "host.owner"),
            Principal("recourse-executor", "operations", "host.recourse"),
            Principal("representative", "claimants", "host.claimants"),
            Principal("root", "root-of-trust", "host.root"),
        ),
        purposes=(Purpose("purpose", "owner", digest("purpose-v1")),),
        horizons=(
            Horizon(
                id="long-term",
                kind="standard.temporal.long-term",
                owner="owner",
                selectors=selectors,
                observers=("observer-a", "observer-b"),
                minimum_trust_domains=2,
            ),
        ),
        standings=(
            Standing(
                id="users",
                representatives=("representative",),
                rights=("appeal", "consent", "contest", "discharge", "observe"),
            ),
        ),
        obligations=(
            Obligation(
                id="no-regression",
                horizon_id="long-term",
                bearer="actor",
                beneficiary="users",
                predicate="quality.no-regression",
                mode=obligation_mode,
                selectors=selectors,
                recourse_ids=("restore",),
            ),
        ),
        recourses=(
            Recourse(
                id="restore",
                standing_id="users",
                owner="owner",
                executor="recourse-executor",
                mechanism="rollback-or-remedy",
                applies_to=reversibilities,
                deadline_seconds=3600,
            ),
        ),
        mandates=(
            Mandate(
                id="forge-mandate",
                issuer="root",
                principal="actor",
                actions=("forge.*",),
                resources=("repo:*",),
                issued_at=NOW - timedelta(days=365),
                expires_at=NOW + timedelta(days=365),
                allow_amendment=True,
            ),
        ),
        amendment=AmendmentRule(
            approver_standings=("users",), minimum_standings=1, root_principal="root"
        ),
    )


def make_proposal(
    charter: Charter,
    *,
    action: str = "forge.mutate",
    effect: str = "code.performance",
    horizons: tuple[str, ...] = ("long-term",),
    standings: tuple[str, ...] = ("users",),
    reversibility: Reversibility = Reversibility.REVERSIBLE,
    candidate: Charter | None = None,
    actor: str = "actor",
    key: str = "proposal-key",
) -> Proposal:
    return Proposal(
        id="proposal-1",
        actor=actor,
        action=action,
        claims=(
            ImpactClaim(
                id="impact-1",
                effect=effect,
                resource="repo:demo",
                horizons=horizons,
                standings=standings,
            ),
        ),
        reversibility=reversibility,
        artifact_digest=digest("candidate-artifact"),
        base_charter_digest=charter.digest,
        candidate_charter_digest=None if candidate is None else candidate.digest,
        ledger_root_digest=None if candidate is None else digest("predecessor-ledger-root"),
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
        idempotency_key=key,
    )


def receipt_for(
    request: EffectRequest,
    status: ReceiptStatus = ReceiptStatus.SATISFIED,
    *,
    producer: str | None = None,
    issued_at: datetime | None = None,
) -> EffectReceipt:
    selected = request.allowed_producers[0] if producer is None else producer
    return EffectReceipt(
        id=f"receipt-{request.id.removeprefix('effect-')}",
        request_digest=request.digest,
        producer=selected,
        status=status,
        evidence_digest=digest(f"evidence:{request.id}:{status.value}"),
        result_digest=digest(f"result:{request.id}:{status.value}"),
        issued_at=NOW + timedelta(minutes=1) if issued_at is None else issued_at,
        details={"non_normative": True},
    )


def revised(charter: Charter, **changes: object) -> Charter:
    return replace(charter, revision="v2", **changes)
