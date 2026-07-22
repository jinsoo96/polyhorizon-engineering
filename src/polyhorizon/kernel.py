from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from polyhorizon.canonical import (
    any_selector_matches,
    aware_datetime,
    domain_digest,
    require_digest,
    require_identifier,
)
from polyhorizon.errors import ProtocolError
from polyhorizon.models import (
    Charter,
    EffectReceipt,
    EffectRequest,
    Horizon,
    Obligation,
    ObligationMode,
    Proposal,
    ReceiptStatus,
)


class DecisionEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


class SessionStatus(StrEnum):
    AWAITING_EFFECTS = "awaiting_effects"
    DECIDED = "decided"
    ABORTED = "aborted"


@dataclass(frozen=True, slots=True)
class HorizonResult:
    horizon_id: str
    effect: DecisionEffect
    obligations: tuple[str, ...]
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_identifier(self.horizon_id, "horizon_result.horizon_id")
        if not isinstance(self.effect, DecisionEffect):
            raise TypeError("horizon_result.effect is invalid")
        object.__setattr__(self, "obligations", tuple(sorted(set(self.obligations))))
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))

    def material(self) -> dict[str, object]:
        return {
            "horizon_id": self.horizon_id,
            "effect": self.effect.value,
            "obligations": list(self.obligations),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class Decision:
    effect: DecisionEffect
    charter_digest: str
    proposal_digest: str
    reasons: tuple[str, ...]
    horizon_vector: tuple[HorizonResult, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.effect, DecisionEffect):
            raise TypeError("decision.effect is invalid")
        require_digest(self.charter_digest, "decision.charter_digest")
        require_digest(self.proposal_digest, "decision.proposal_digest")
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))
        vector = tuple(sorted(self.horizon_vector, key=lambda item: item.horizon_id))
        if len(vector) != len({item.horizon_id for item in vector}):
            raise ValueError("decision.horizon_vector must contain unique horizons")
        object.__setattr__(self, "horizon_vector", vector)

    def material(self) -> dict[str, object]:
        return {
            "effect": self.effect.value,
            "charter_digest": self.charter_digest,
            "proposal_digest": self.proposal_digest,
            "reasons": list(self.reasons),
            "horizon_vector": [item.material() for item in self.horizon_vector],
        }

    @property
    def digest(self) -> str:
        return domain_digest("decision", self.material())


@dataclass(frozen=True, slots=True)
class SessionState:
    id: str
    sequence: int
    status: SessionStatus
    charter_digest: str
    proposal_digest: str
    idempotency_key: str
    opened_at: datetime
    expires_at: datetime
    requests: tuple[EffectRequest, ...]
    receipts: tuple[EffectReceipt, ...] = ()
    decision: Decision | None = None

    def __post_init__(self) -> None:
        require_identifier(self.id, "session.id")
        require_identifier(self.idempotency_key, "session.idempotency_key")
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValueError("session.sequence must be a non-negative integer")
        if not isinstance(self.status, SessionStatus):
            raise TypeError("session.status is invalid")
        require_digest(self.charter_digest, "session.charter_digest")
        require_digest(self.proposal_digest, "session.proposal_digest")
        object.__setattr__(self, "opened_at", aware_datetime(self.opened_at, "session.opened_at"))
        object.__setattr__(
            self, "expires_at", aware_datetime(self.expires_at, "session.expires_at")
        )
        if self.expires_at <= self.opened_at:
            raise ValueError("session.expires_at must be after session.opened_at")
        requests = tuple(sorted(self.requests, key=lambda item: item.id))
        receipts = tuple(sorted(self.receipts, key=lambda item: item.id))
        if len(requests) != len({item.id for item in requests}):
            raise ValueError("session requests must have unique ids")
        if len(receipts) != len({item.id for item in receipts}):
            raise ValueError("session receipts must have unique ids")
        object.__setattr__(self, "requests", requests)
        object.__setattr__(self, "receipts", receipts)
        request_by_digest = {item.digest: item for item in requests}
        request_digests = set(request_by_digest)
        receipt_requests = [item.request_digest for item in receipts]
        if len(receipt_requests) != len(set(receipt_requests)):
            raise ValueError("session may contain at most one receipt per request")
        if any(item not in request_digests for item in receipt_requests):
            raise ValueError("session receipt references an unknown request")
        for receipt in receipts:
            request = request_by_digest[receipt.request_digest]
            if receipt.producer not in request.allowed_producers:
                raise ValueError("session receipt producer is not authorized by its request")
            if not self.opened_at <= receipt.issued_at < request.expires_at:
                raise ValueError("session receipt timestamp is outside its request interval")
        for request in requests:
            if (
                request.session_id != self.id
                or request.charter_digest != self.charter_digest
                or request.proposal_digest != self.proposal_digest
                or request.sequence > self.sequence
                or request.expires_at != self.expires_at
            ):
                raise ValueError("session request binding is inconsistent")
        if self.decision is not None and (
            self.decision.charter_digest != self.charter_digest
            or self.decision.proposal_digest != self.proposal_digest
        ):
            raise ValueError("session decision binding is inconsistent")
        if self.status is SessionStatus.DECIDED and self.decision is None:
            raise ValueError("decided session requires a decision")
        if self.status is SessionStatus.AWAITING_EFFECTS and self.decision is not None:
            raise ValueError("awaiting session cannot already have a decision")
        if self.status is SessionStatus.AWAITING_EFFECTS and not self.pending_requests:
            raise ValueError("awaiting session requires at least one pending request")
        if self.status is SessionStatus.ABORTED and self.decision is not None:
            raise ValueError("aborted session cannot have a decision")

    @property
    def pending_requests(self) -> tuple[EffectRequest, ...]:
        received = {item.request_digest for item in self.receipts}
        return tuple(item for item in self.requests if item.digest not in received)

    def material(self) -> dict[str, object]:
        return {
            "id": self.id,
            "sequence": self.sequence,
            "status": self.status.value,
            "charter_digest": self.charter_digest,
            "proposal_digest": self.proposal_digest,
            "idempotency_key": self.idempotency_key,
            "opened_at": self.opened_at,
            "expires_at": self.expires_at,
            "requests": [item.material() for item in self.requests],
            "receipts": [item.material() for item in self.receipts],
            "decision": None if self.decision is None else self.decision.material(),
        }

    @property
    def digest(self) -> str:
        return domain_digest("session-state", self.material())


@dataclass(frozen=True, slots=True)
class StepResult:
    state: SessionState
    effects: tuple[EffectRequest, ...]
    decision: Decision | None


def _short_id(prefix: str, domain: str, material: object) -> str:
    suffix = domain_digest(domain, material).removeprefix("sha256:")[:24]
    return f"{prefix}-{suffix}"


class PureKernel:
    """Effect-free admission state machine; hosts execute every requested side effect."""

    def open(
        self,
        charter: Charter,
        proposal: Proposal,
        *,
        now: datetime,
        candidate: Charter | None = None,
    ) -> StepResult:
        current_time = aware_datetime(now, "now")
        self._validate_open_inputs(charter, proposal, candidate, current_time)
        session_id = _short_id(
            "session",
            "session-id",
            {
                "charter": charter.digest,
                "proposal": proposal.digest,
                "idempotency_key": proposal.idempotency_key,
            },
        )
        immediate = self._static_decision(charter, proposal, current_time)
        if immediate is not None:
            state = SessionState(
                id=session_id,
                sequence=0,
                status=SessionStatus.DECIDED,
                charter_digest=charter.digest,
                proposal_digest=proposal.digest,
                idempotency_key=proposal.idempotency_key,
                opened_at=current_time,
                expires_at=proposal.expires_at,
                requests=(),
                decision=immediate,
            )
            return StepResult(state=state, effects=(), decision=immediate)

        requests, planning_decision = self._compile_requests(
            charter, proposal, session_id, candidate
        )
        if planning_decision is not None:
            state = SessionState(
                id=session_id,
                sequence=0,
                status=SessionStatus.DECIDED,
                charter_digest=charter.digest,
                proposal_digest=proposal.digest,
                idempotency_key=proposal.idempotency_key,
                opened_at=current_time,
                expires_at=proposal.expires_at,
                requests=(),
                decision=planning_decision,
            )
            return StepResult(state=state, effects=(), decision=planning_decision)

        if not requests:
            decision = Decision(
                effect=DecisionEffect.ALLOW,
                charter_digest=charter.digest,
                proposal_digest=proposal.digest,
                reasons=("no_applicable_obligations",),
            )
            state = SessionState(
                id=session_id,
                sequence=0,
                status=SessionStatus.DECIDED,
                charter_digest=charter.digest,
                proposal_digest=proposal.digest,
                idempotency_key=proposal.idempotency_key,
                opened_at=current_time,
                expires_at=proposal.expires_at,
                requests=(),
                decision=decision,
            )
            return StepResult(state=state, effects=(), decision=decision)

        state = SessionState(
            id=session_id,
            sequence=0,
            status=SessionStatus.AWAITING_EFFECTS,
            charter_digest=charter.digest,
            proposal_digest=proposal.digest,
            idempotency_key=proposal.idempotency_key,
            opened_at=current_time,
            expires_at=proposal.expires_at,
            requests=requests,
        )
        return StepResult(state=state, effects=requests, decision=None)

    def advance(
        self,
        charter: Charter,
        state: SessionState,
        receipts: Iterable[EffectReceipt],
        *,
        now: datetime,
    ) -> StepResult:
        current_time = aware_datetime(now, "now")
        submitted = tuple(receipts)
        if state.charter_digest != charter.digest:
            raise ProtocolError("session is bound to a different charter")
        if state.status is not SessionStatus.AWAITING_EFFECTS:
            raise ProtocolError("only an awaiting session can advance")
        if current_time >= state.expires_at:
            decision = Decision(
                effect=DecisionEffect.ESCALATE,
                charter_digest=state.charter_digest,
                proposal_digest=state.proposal_digest,
                reasons=("session_expired",),
            )
            expired = SessionState(
                id=state.id,
                sequence=state.sequence + 1,
                status=SessionStatus.DECIDED,
                charter_digest=state.charter_digest,
                proposal_digest=state.proposal_digest,
                idempotency_key=state.idempotency_key,
                opened_at=state.opened_at,
                expires_at=state.expires_at,
                requests=state.requests,
                receipts=state.receipts,
                decision=decision,
            )
            return StepResult(state=expired, effects=(), decision=decision)

        if not submitted:
            raise ProtocolError("advance requires at least one receipt before session expiry")
        accepted = self._accept_receipts(charter, state, submitted, current_time)
        combined = tuple((*state.receipts, *accepted))
        received = {item.request_digest for item in combined}
        pending = tuple(item for item in state.requests if item.digest not in received)
        if pending:
            advanced = SessionState(
                id=state.id,
                sequence=state.sequence + 1,
                status=SessionStatus.AWAITING_EFFECTS,
                charter_digest=state.charter_digest,
                proposal_digest=state.proposal_digest,
                idempotency_key=state.idempotency_key,
                opened_at=state.opened_at,
                expires_at=state.expires_at,
                requests=state.requests,
                receipts=combined,
            )
            return StepResult(state=advanced, effects=pending, decision=None)

        decision = self._decide(charter, state.requests, combined, state.proposal_digest)
        completed = SessionState(
            id=state.id,
            sequence=state.sequence + 1,
            status=SessionStatus.DECIDED,
            charter_digest=state.charter_digest,
            proposal_digest=state.proposal_digest,
            idempotency_key=state.idempotency_key,
            opened_at=state.opened_at,
            expires_at=state.expires_at,
            requests=state.requests,
            receipts=combined,
            decision=decision,
        )
        return StepResult(state=completed, effects=(), decision=decision)

    def abort(self, state: SessionState, *, now: datetime) -> StepResult:
        aware_datetime(now, "now")
        if state.status is not SessionStatus.AWAITING_EFFECTS:
            raise ProtocolError("only an awaiting session can be aborted")
        aborted = SessionState(
            id=state.id,
            sequence=state.sequence + 1,
            status=SessionStatus.ABORTED,
            charter_digest=state.charter_digest,
            proposal_digest=state.proposal_digest,
            idempotency_key=state.idempotency_key,
            opened_at=state.opened_at,
            expires_at=state.expires_at,
            requests=state.requests,
            receipts=state.receipts,
        )
        return StepResult(state=aborted, effects=(), decision=None)

    @staticmethod
    def _validate_open_inputs(
        charter: Charter,
        proposal: Proposal,
        candidate: Charter | None,
        now: datetime,
    ) -> None:
        if proposal.base_charter_digest != charter.digest:
            raise ProtocolError("proposal base charter digest does not match")
        if proposal.actor not in charter.principal_map:
            raise ProtocolError("proposal actor is not a charter principal")
        if not proposal.issued_at <= now < proposal.expires_at:
            raise ProtocolError("proposal is not active at open time")
        if proposal.is_amendment:
            if candidate is None:
                raise ProtocolError("amendment proposal requires a candidate charter")
            if candidate.digest != proposal.candidate_charter_digest:
                raise ProtocolError("candidate charter digest does not match proposal")
            if candidate.id != charter.id or candidate.revision == charter.revision:
                raise ProtocolError("candidate must advance the same charter identity")
        elif candidate is not None:
            raise ProtocolError("non-amendment proposal cannot carry a candidate charter")

    @staticmethod
    def _static_decision(charter: Charter, proposal: Proposal, now: datetime) -> Decision | None:
        eligible = []
        for mandate in charter.mandates:
            if (
                mandate.principal != proposal.actor
                or not mandate.issued_at <= now < mandate.expires_at
            ):
                continue
            if not any_selector_matches(mandate.actions, proposal.action):
                continue
            if proposal.is_amendment and not mandate.allow_amendment:
                continue
            if all(
                any_selector_matches(mandate.resources, claim.resource) for claim in proposal.claims
            ):
                eligible.append(mandate.id)
        if eligible:
            return None
        return Decision(
            effect=DecisionEffect.DENY,
            charter_digest=charter.digest,
            proposal_digest=proposal.digest,
            reasons=("actor_lacks_active_mandate",),
        )

    def _compile_requests(
        self,
        charter: Charter,
        proposal: Proposal,
        session_id: str,
        candidate: Charter | None,
    ) -> tuple[tuple[EffectRequest, ...], Decision | None]:
        horizons = charter.horizon_map
        standings = charter.standing_map
        coverage_reasons: list[str] = []
        applicable: dict[str, set[str]] = defaultdict(set)

        for claim in proposal.claims:
            matching = {
                horizon.id
                for horizon in charter.horizons
                if horizon.selectors.matches(claim.effect, claim.resource)
            }
            if not matching:
                coverage_reasons.append(f"uncovered_claim:{claim.id}")
                continue
            unknown_horizons = set(claim.horizons) - set(horizons)
            missing_horizons = matching - set(claim.horizons)
            unmatched_horizons = (set(claim.horizons) & set(horizons)) - matching
            for horizon_id in sorted(unknown_horizons):
                coverage_reasons.append(f"unknown_horizon:{claim.id}:{horizon_id}")
            for horizon_id in sorted(missing_horizons):
                coverage_reasons.append(f"undeclared_horizon:{claim.id}:{horizon_id}")
            for horizon_id in sorted(unmatched_horizons):
                coverage_reasons.append(f"unmatched_horizon:{claim.id}:{horizon_id}")
            for standing_id in sorted(set(claim.standings) - set(standings)):
                coverage_reasons.append(f"unknown_standing:{claim.id}:{standing_id}")

            obligated_horizons: set[str] = set()
            represented_standings: set[str] = set()
            for obligation in charter.obligations:
                if obligation.horizon_id in matching and obligation.selectors.matches(
                    claim.effect, claim.resource
                ):
                    obligated_horizons.add(obligation.horizon_id)
                    represented_standings.add(obligation.beneficiary)
                    applicable[obligation.id].add(claim.id)
                    if obligation.beneficiary not in claim.standings:
                        coverage_reasons.append(
                            f"unrepresented_standing:{claim.id}:{obligation.beneficiary}"
                        )
            for horizon_id in sorted(matching - obligated_horizons):
                coverage_reasons.append(f"uncovered_obligation:{claim.id}:{horizon_id}")
            known_claimed_standings = set(claim.standings) & set(standings)
            for standing_id in sorted(known_claimed_standings - represented_standings):
                coverage_reasons.append(f"uncovered_standing:{claim.id}:{standing_id}")

        if coverage_reasons:
            return (), Decision(
                effect=DecisionEffect.ESCALATE,
                charter_digest=charter.digest,
                proposal_digest=proposal.digest,
                reasons=tuple(coverage_reasons),
            )

        planning_reasons: list[str] = []
        requests: list[EffectRequest] = []
        obligation_map = charter.obligation_map
        for obligation_id, claim_ids in sorted(applicable.items()):
            obligation = obligation_map[obligation_id]
            horizon = horizons[obligation.horizon_id]
            requests.extend(
                self._obligation_requests(
                    charter, proposal, session_id, obligation, horizon, tuple(sorted(claim_ids))
                )
            )
            requests.extend(
                self._recourse_requests(
                    charter,
                    proposal,
                    session_id,
                    obligation,
                    planning_reasons,
                )
            )

        if planning_reasons:
            effect = (
                DecisionEffect.DENY
                if any(reason.startswith("hard_") for reason in planning_reasons)
                else DecisionEffect.ESCALATE
            )
            return (), Decision(
                effect=effect,
                charter_digest=charter.digest,
                proposal_digest=proposal.digest,
                reasons=tuple(planning_reasons),
            )

        if candidate is not None:
            requests.extend(self._amendment_requests(charter, proposal, session_id, candidate))

        ordered = tuple(sorted(requests, key=lambda item: item.id))
        if len(ordered) != len({item.id for item in ordered}):
            raise ProtocolError("compiled effect request ids collided")
        return ordered, None

    def _obligation_requests(
        self,
        charter: Charter,
        proposal: Proposal,
        session_id: str,
        obligation: Obligation,
        horizon: Horizon,
        claim_ids: tuple[str, ...],
    ) -> list[EffectRequest]:
        observers = obligation.observer_ids or horizon.observers
        result = []
        for observer_id in observers:
            principal = charter.principal_map[observer_id]
            payload = {
                "semantics": "obligation_assessment",
                "obligation_id": obligation.id,
                "horizon_id": horizon.id,
                "horizon_kind": horizon.kind,
                "predicate": obligation.predicate,
                "mode": obligation.mode.value,
                "claim_ids": list(claim_ids),
                "minimum_trust_domains": horizon.minimum_trust_domains,
            }
            result.append(
                self._request(
                    charter,
                    proposal,
                    session_id,
                    kind="polyhorizon.obligation.assess",
                    provider=principal.adapter,
                    allowed=(observer_id,),
                    group=f"obligation:{obligation.id}",
                    payload=payload,
                )
            )
        return result

    def _recourse_requests(
        self,
        charter: Charter,
        proposal: Proposal,
        session_id: str,
        obligation: Obligation,
        planning_reasons: list[str],
    ) -> list[EffectRequest]:
        if (
            proposal.reversibility.value == "reversible"
            or obligation.mode is ObligationMode.ADVISORY
        ):
            return []
        recourses = [
            charter.recourse_map[item]
            for item in obligation.recourse_ids
            if proposal.reversibility in charter.recourse_map[item].applies_to
        ]
        if not recourses:
            prefix = "hard" if obligation.mode is ObligationMode.HARD else "review"
            planning_reasons.append(f"{prefix}_recourse_missing:{obligation.id}")
            return []
        result = []
        for recourse in recourses:
            executor = charter.principal_map[recourse.executor]
            result.append(
                self._request(
                    charter,
                    proposal,
                    session_id,
                    kind="polyhorizon.recourse.reserve",
                    provider=executor.adapter,
                    allowed=(recourse.executor,),
                    group=f"recourse:{obligation.id}:{recourse.id}",
                    payload={
                        "semantics": "reserved_recourse",
                        "obligation_id": obligation.id,
                        "standing_id": recourse.standing_id,
                        "recourse_id": recourse.id,
                        "mechanism": recourse.mechanism,
                        "deadline_seconds": recourse.deadline_seconds,
                    },
                )
            )
        return result

    @staticmethod
    def _charter_change_set(charter: Charter, candidate: Charter) -> dict[str, object]:
        collections: dict[
            str,
            tuple[
                Mapping[str, Mapping[str, object]],
                Mapping[str, Mapping[str, object]],
            ],
        ] = {
            "principals": (
                {item.id: item.material() for item in charter.principals},
                {item.id: item.material() for item in candidate.principals},
            ),
            "purposes": (
                {item.id: item.material() for item in charter.purposes},
                {item.id: item.material() for item in candidate.purposes},
            ),
            "horizons": (
                {item.id: item.material() for item in charter.horizons},
                {item.id: item.material() for item in candidate.horizons},
            ),
            "standings": (
                {item.id: item.material() for item in charter.standings},
                {item.id: item.material() for item in candidate.standings},
            ),
            "obligations": (
                {item.id: item.material() for item in charter.obligations},
                {item.id: item.material() for item in candidate.obligations},
            ),
            "recourses": (
                {item.id: item.material() for item in charter.recourses},
                {item.id: item.material() for item in candidate.recourses},
            ),
            "mandates": (
                {item.id: item.material() for item in charter.mandates},
                {item.id: item.material() for item in candidate.mandates},
            ),
        }
        changed_collections: dict[str, object] = {}
        for collection, (before, after) in collections.items():
            changes: list[dict[str, object]] = []
            for identifier in sorted(set(before) | set(after)):
                predecessor = before.get(identifier)
                successor = after.get(identifier)
                if predecessor == successor:
                    continue
                change = "changed"
                if predecessor is None:
                    change = "added"
                elif successor is None:
                    change = "removed"
                changes.append(
                    {
                        "id": identifier,
                        "change": change,
                        "before": predecessor,
                        "after": successor,
                    }
                )
            if changes:
                changed_collections[collection] = changes

        amendment_change: dict[str, object] | None = None
        if charter.amendment.material() != candidate.amendment.material():
            amendment_change = {
                "before": charter.amendment.material(),
                "after": candidate.amendment.material(),
            }
        return {
            "base_charter_digest": charter.digest,
            "candidate_charter_digest": candidate.digest,
            "from_revision": charter.revision,
            "to_revision": candidate.revision,
            "collections": changed_collections,
            "amendment": amendment_change,
        }

    def _amendment_requests(
        self,
        charter: Charter,
        proposal: Proposal,
        session_id: str,
        candidate: Charter,
    ) -> list[EffectRequest]:
        result: list[EffectRequest] = []
        rule = charter.amendment
        ledger_root = proposal.ledger_root_digest
        if ledger_root is None:
            raise ProtocolError("amendment proposal is missing its predecessor ledger root")
        change_set = self._charter_change_set(charter, candidate)
        change_set_digest = domain_digest(
            "charter-change-set",
            {"change_set": change_set, "predecessor_ledger_root": ledger_root},
        )
        for standing_id in rule.approver_standings:
            standing = charter.standing_map[standing_id]
            result.append(
                self._request(
                    charter,
                    proposal,
                    session_id,
                    kind="polyhorizon.amendment.ratify",
                    provider=f"standing:{standing.id}",
                    allowed=standing.representatives,
                    group="amendment:ratify",
                    payload={
                        "semantics": "predecessor_ratification",
                        "standing_id": standing.id,
                        "minimum_standings": rule.minimum_standings,
                        "candidate_charter_digest": candidate.digest,
                        "predecessor_ledger_root": ledger_root,
                        "change_set_digest": change_set_digest,
                        "change_set": change_set,
                    },
                )
            )

        root = charter.principal_map[rule.root_principal]
        result.append(
            self._request(
                charter,
                proposal,
                session_id,
                kind="polyhorizon.amendment.root",
                provider=root.adapter,
                allowed=(root.id,),
                group="amendment:root",
                payload={
                    "semantics": "external_root_approval",
                    "candidate_charter_digest": candidate.digest,
                    "predecessor_ledger_root": ledger_root,
                    "change_set_digest": change_set_digest,
                    "change_set": change_set,
                },
            )
        )

        base_obligations = charter.obligation_map
        candidate_obligations = candidate.obligation_map
        for obligation_id, obligation in base_obligations.items():
            successor = candidate_obligations.get(obligation_id)
            if successor is not None and successor.material() == obligation.material():
                continue
            standing = charter.standing_map[obligation.beneficiary]
            result.append(
                self._request(
                    charter,
                    proposal,
                    session_id,
                    kind="polyhorizon.obligation.discharge",
                    provider=f"standing:{standing.id}",
                    allowed=standing.representatives,
                    group=f"discharge:{obligation.id}",
                    payload={
                        "semantics": "obligation_discharge",
                        "obligation_id": obligation.id,
                        "beneficiary": standing.id,
                        "successor_present": successor is not None,
                        "candidate_charter_digest": candidate.digest,
                        "predecessor_ledger_root": ledger_root,
                        "change_set_digest": change_set_digest,
                        "before": obligation.material(),
                        "after": None if successor is None else successor.material(),
                    },
                )
            )

        self._append_standing_change_requests(
            charter, candidate, proposal, session_id, change_set_digest, result
        )
        self._append_principal_change_requests(
            charter, candidate, proposal, session_id, change_set_digest, result
        )
        self._append_horizon_change_requests(
            charter, candidate, proposal, session_id, change_set_digest, result
        )
        self._append_recourse_change_requests(
            charter, candidate, proposal, session_id, change_set_digest, result
        )
        self._append_purpose_change_requests(
            charter, candidate, proposal, session_id, change_set_digest, result
        )
        return result

    def _append_principal_change_requests(
        self,
        charter: Charter,
        candidate: Charter,
        proposal: Proposal,
        session_id: str,
        change_set_digest: str,
        result: list[EffectRequest],
    ) -> None:
        candidate_map = candidate.principal_map
        for principal_id, principal in charter.principal_map.items():
            successor = candidate_map.get(principal_id)
            if successor is not None and successor.material() == principal.material():
                continue
            result.append(
                self._request(
                    charter,
                    proposal,
                    session_id,
                    kind="polyhorizon.principal.release",
                    provider=principal.adapter,
                    allowed=(principal.id,),
                    group=f"principal-change:{principal.id}",
                    payload={
                        "semantics": "predecessor_principal_release",
                        "principal_id": principal.id,
                        "removed": successor is None,
                        "candidate_charter_digest": candidate.digest,
                        "predecessor_ledger_root": proposal.ledger_root_digest,
                        "change_set_digest": change_set_digest,
                        "before": principal.material(),
                        "after": None if successor is None else successor.material(),
                        "trust_domain_changed": (
                            successor is not None
                            and successor.trust_domain != principal.trust_domain
                        ),
                        "adapter_changed": (
                            successor is not None and successor.adapter != principal.adapter
                        ),
                    },
                )
            )

    def _append_standing_change_requests(
        self,
        charter: Charter,
        candidate: Charter,
        proposal: Proposal,
        session_id: str,
        change_set_digest: str,
        result: list[EffectRequest],
    ) -> None:
        candidate_map = candidate.standing_map
        for standing_id, standing in charter.standing_map.items():
            successor = candidate_map.get(standing_id)
            lost_rights = (
                set(standing.rights)
                if successor is None
                else (set(standing.rights) - set(successor.rights))
            )
            removed_representatives = (
                set(standing.representatives)
                if successor is None
                else (set(standing.representatives) - set(successor.representatives))
            )
            if successor is not None and successor.material() == standing.material():
                continue
            result.append(
                self._request(
                    charter,
                    proposal,
                    session_id,
                    kind="polyhorizon.standing.consent",
                    provider=f"standing:{standing.id}",
                    allowed=standing.representatives,
                    group=f"standing-change:{standing.id}",
                    payload={
                        "semantics": "standing_change_consent",
                        "standing_id": standing.id,
                        "removed": successor is None,
                        "candidate_charter_digest": candidate.digest,
                        "predecessor_ledger_root": proposal.ledger_root_digest,
                        "change_set_digest": change_set_digest,
                        "before": standing.material(),
                        "after": None if successor is None else successor.material(),
                        "lost_rights": sorted(lost_rights),
                        "removed_representatives": sorted(removed_representatives),
                    },
                )
            )

    def _append_horizon_change_requests(
        self,
        charter: Charter,
        candidate: Charter,
        proposal: Proposal,
        session_id: str,
        change_set_digest: str,
        result: list[EffectRequest],
    ) -> None:
        candidate_map = candidate.horizon_map
        for horizon_id, horizon in charter.horizon_map.items():
            successor = candidate_map.get(horizon_id)
            if successor is not None and successor.material() == horizon.material():
                continue
            owner = charter.principal_map[horizon.owner]
            result.append(
                self._request(
                    charter,
                    proposal,
                    session_id,
                    kind="polyhorizon.horizon.release",
                    provider=owner.adapter,
                    allowed=(owner.id,),
                    group=f"horizon-change:{horizon.id}",
                    payload={
                        "semantics": "horizon_change_release",
                        "horizon_id": horizon.id,
                        "removed": successor is None,
                        "candidate_charter_digest": candidate.digest,
                        "predecessor_ledger_root": proposal.ledger_root_digest,
                        "change_set_digest": change_set_digest,
                        "before": horizon.material(),
                        "after": None if successor is None else successor.material(),
                    },
                )
            )

    def _append_recourse_change_requests(
        self,
        charter: Charter,
        candidate: Charter,
        proposal: Proposal,
        session_id: str,
        change_set_digest: str,
        result: list[EffectRequest],
    ) -> None:
        candidate_map = candidate.recourse_map
        for recourse_id, recourse in charter.recourse_map.items():
            successor = candidate_map.get(recourse_id)
            if successor is not None and successor.material() == recourse.material():
                continue
            standing = charter.standing_map[recourse.standing_id]
            result.append(
                self._request(
                    charter,
                    proposal,
                    session_id,
                    kind="polyhorizon.recourse.release",
                    provider=f"standing:{standing.id}",
                    allowed=standing.representatives,
                    group=f"recourse-change:{recourse.id}",
                    payload={
                        "semantics": "recourse_change_consent",
                        "recourse_id": recourse.id,
                        "standing_id": standing.id,
                        "removed": successor is None,
                        "candidate_charter_digest": candidate.digest,
                        "predecessor_ledger_root": proposal.ledger_root_digest,
                        "change_set_digest": change_set_digest,
                        "before": recourse.material(),
                        "after": None if successor is None else successor.material(),
                    },
                )
            )

    def _append_purpose_change_requests(
        self,
        charter: Charter,
        candidate: Charter,
        proposal: Proposal,
        session_id: str,
        change_set_digest: str,
        result: list[EffectRequest],
    ) -> None:
        candidate_map = {item.id: item for item in candidate.purposes}
        for purpose in charter.purposes:
            successor = candidate_map.get(purpose.id)
            if successor is not None and successor.material() == purpose.material():
                continue
            owner = charter.principal_map[purpose.owner]
            result.append(
                self._request(
                    charter,
                    proposal,
                    session_id,
                    kind="polyhorizon.purpose.release",
                    provider=owner.adapter,
                    allowed=(owner.id,),
                    group=f"purpose-change:{purpose.id}",
                    payload={
                        "semantics": "purpose_change_release",
                        "purpose_id": purpose.id,
                        "removed": successor is None,
                        "candidate_charter_digest": candidate.digest,
                        "predecessor_ledger_root": proposal.ledger_root_digest,
                        "change_set_digest": change_set_digest,
                        "before": purpose.material(),
                        "after": None if successor is None else successor.material(),
                    },
                )
            )

    @staticmethod
    def _request(
        charter: Charter,
        proposal: Proposal,
        session_id: str,
        *,
        kind: str,
        provider: str,
        allowed: tuple[str, ...],
        group: str,
        payload: Mapping[str, object],
    ) -> EffectRequest:
        seed = {
            "session": session_id,
            "kind": kind,
            "provider": provider,
            "allowed": sorted(allowed),
            "group": group,
            "payload": payload,
        }
        request_id = _short_id("effect", "effect-id", seed)
        return EffectRequest(
            id=request_id,
            kind=kind,
            session_id=session_id,
            sequence=0,
            charter_digest=charter.digest,
            proposal_digest=proposal.digest,
            provider=provider,
            allowed_producers=allowed,
            group=group,
            payload=payload,
            expires_at=proposal.expires_at,
        )

    @staticmethod
    def _accept_receipts(
        charter: Charter,
        state: SessionState,
        receipts: tuple[EffectReceipt, ...],
        now: datetime,
    ) -> tuple[EffectReceipt, ...]:
        requests = {item.digest: item for item in state.requests}
        existing_ids = {item.id for item in state.receipts}
        existing_requests = {item.request_digest for item in state.receipts}
        batch_ids: set[str] = set()
        batch_requests: set[str] = set()
        for receipt in receipts:
            if receipt.id in existing_ids or receipt.id in batch_ids:
                raise ProtocolError(f"duplicate receipt id: {receipt.id}")
            if (
                receipt.request_digest in existing_requests
                or receipt.request_digest in batch_requests
            ):
                raise ProtocolError("an effect request may be receipted only once")
            request = requests.get(receipt.request_digest)
            if request is None:
                raise ProtocolError("receipt is not bound to a session effect request")
            if receipt.producer not in request.allowed_producers:
                raise ProtocolError("receipt producer is not authorized for the effect request")
            if receipt.producer not in charter.principal_map:
                raise ProtocolError("receipt producer is not in the predecessor charter")
            if not state.opened_at <= receipt.issued_at <= now:
                raise ProtocolError("receipt timestamp is outside the active session interval")
            if receipt.issued_at >= request.expires_at:
                raise ProtocolError("receipt was issued after its effect request expired")
            batch_ids.add(receipt.id)
            batch_requests.add(receipt.request_digest)
        return tuple(sorted(receipts, key=lambda item: item.id))

    def _decide(
        self,
        charter: Charter,
        requests: tuple[EffectRequest, ...],
        receipts: tuple[EffectReceipt, ...],
        proposal_digest: str,
    ) -> Decision:
        by_request = {item.request_digest: item for item in receipts}
        grouped: dict[str, list[tuple[EffectRequest, EffectReceipt]]] = defaultdict(list)
        for request in requests:
            grouped[request.group].append((request, by_request[request.digest]))

        deny: list[str] = []
        escalate: list[str] = []
        horizon_reasons: dict[str, list[str]] = defaultdict(list)
        horizon_obligations: dict[str, set[str]] = defaultdict(set)

        for group, items in sorted(grouped.items()):
            kind = items[0][0].kind
            if kind == "polyhorizon.obligation.assess":
                self._decide_obligation_group(
                    charter,
                    group,
                    items,
                    deny,
                    escalate,
                    horizon_reasons,
                    horizon_obligations,
                )
            elif kind == "polyhorizon.amendment.ratify":
                threshold = int(items[0][0].payload["minimum_standings"])
                approvals = sum(receipt.status is ReceiptStatus.SATISFIED for _, receipt in items)
                if approvals < threshold:
                    escalate.append("predecessor_ratification_quorum_not_met")
            else:
                for request, receipt in items:
                    if receipt.status is ReceiptStatus.VIOLATED:
                        deny.append(f"effect_violated:{request.group}")
                    elif receipt.status in {ReceiptStatus.UNKNOWN, ReceiptStatus.UNCOVERED}:
                        escalate.append(f"effect_unresolved:{request.group}")

        effect = DecisionEffect.ALLOW
        reasons: tuple[str, ...] = ("all_declared_horizons_satisfied",)
        if deny:
            effect = DecisionEffect.DENY
            reasons = tuple(deny)
        elif escalate:
            effect = DecisionEffect.ESCALATE
            reasons = tuple(escalate)

        vector = []
        for horizon_id in sorted(horizon_obligations):
            local_reasons = tuple(horizon_reasons[horizon_id])
            local_effect = DecisionEffect.ALLOW
            if any(reason.startswith("deny:") for reason in local_reasons):
                local_effect = DecisionEffect.DENY
            elif any(reason.startswith("escalate:") for reason in local_reasons):
                local_effect = DecisionEffect.ESCALATE
            vector.append(
                HorizonResult(
                    horizon_id=horizon_id,
                    effect=local_effect,
                    obligations=tuple(horizon_obligations[horizon_id]),
                    reasons=local_reasons,
                )
            )
        return Decision(
            effect=effect,
            charter_digest=charter.digest,
            proposal_digest=proposal_digest,
            reasons=reasons,
            horizon_vector=tuple(vector),
        )

    @staticmethod
    def _decide_obligation_group(
        charter: Charter,
        group: str,
        items: list[tuple[EffectRequest, EffectReceipt]],
        deny: list[str],
        escalate: list[str],
        horizon_reasons: dict[str, list[str]],
        horizon_obligations: dict[str, set[str]],
    ) -> None:
        first = items[0][0]
        obligation_id = str(first.payload["obligation_id"])
        horizon_id = str(first.payload["horizon_id"])
        mode = ObligationMode(str(first.payload["mode"]))
        minimum = int(first.payload["minimum_trust_domains"])
        horizon_obligations[horizon_id].add(obligation_id)
        statuses = [receipt.status for _, receipt in items]
        satisfied_domains = {
            charter.principal_map[receipt.producer].trust_domain
            for _, receipt in items
            if receipt.status is ReceiptStatus.SATISFIED
        }
        if ReceiptStatus.VIOLATED in statuses:
            if mode is ObligationMode.HARD:
                deny.append(f"hard_obligation_violated:{obligation_id}")
                horizon_reasons[horizon_id].append(f"deny:{obligation_id}:violated")
            elif mode is ObligationMode.REVIEW:
                escalate.append(f"review_obligation_violated:{obligation_id}")
                horizon_reasons[horizon_id].append(f"escalate:{obligation_id}:violated")
            else:
                horizon_reasons[horizon_id].append(f"advisory:{obligation_id}:violated")
            return
        unresolved = any(
            status in {ReceiptStatus.UNKNOWN, ReceiptStatus.UNCOVERED} for status in statuses
        )
        if unresolved or len(satisfied_domains) < minimum:
            if mode is not ObligationMode.ADVISORY:
                escalate.append(f"obligation_unresolved:{obligation_id}")
                horizon_reasons[horizon_id].append(f"escalate:{obligation_id}:unresolved")
            else:
                horizon_reasons[horizon_id].append(f"advisory:{obligation_id}:unresolved")
            return
        horizon_reasons[horizon_id].append(f"allow:{obligation_id}:satisfied")
