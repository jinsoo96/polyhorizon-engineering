from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from polyhorizon.errors import ConcurrentUpdateError, ProtocolError
from polyhorizon.kernel import PureKernel, SessionState, SessionStatus, StepResult
from polyhorizon.models import Charter, EffectReceipt, Proposal
from polyhorizon.store import MemorySessionStore, SessionStore


def utc_now() -> datetime:
    return datetime.now(UTC)


class Engine:
    def __init__(
        self,
        *,
        kernel: PureKernel | None = None,
        store: SessionStore | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.kernel = PureKernel() if kernel is None else kernel
        self.store = MemorySessionStore() if store is None else store
        self.clock = clock

    def open(
        self, charter: Charter, proposal: Proposal, *, candidate: Charter | None = None
    ) -> StepResult:
        existing = self.store.get_by_idempotency(proposal.idempotency_key)
        if existing is not None:
            self._validate_replay(existing, charter, proposal, candidate)
            return StepResult(
                state=existing,
                effects=(
                    existing.pending_requests
                    if existing.status is SessionStatus.AWAITING_EFFECTS
                    else ()
                ),
                decision=existing.decision,
            )
        result = self.kernel.open(charter, proposal, candidate=candidate, now=self.clock())
        stored = self.store.put_new(result.state)
        if stored.digest == result.state.digest:
            return result
        return StepResult(
            state=stored,
            effects=(
                stored.pending_requests if stored.status is SessionStatus.AWAITING_EFFECTS else ()
            ),
            decision=stored.decision,
        )

    @staticmethod
    def _validate_replay(
        existing: SessionState,
        charter: Charter,
        proposal: Proposal,
        candidate: Charter | None,
    ) -> None:
        if existing.charter_digest != charter.digest or existing.proposal_digest != proposal.digest:
            raise ProtocolError("idempotency key is already bound to another proposal")
        if proposal.base_charter_digest != charter.digest:
            raise ProtocolError("proposal base charter digest does not match")
        if proposal.is_amendment:
            if candidate is None:
                raise ProtocolError("amendment proposal requires a candidate charter")
            if candidate.digest != proposal.candidate_charter_digest:
                raise ProtocolError("candidate charter digest does not match proposal")
        elif candidate is not None:
            raise ProtocolError("non-amendment proposal must not include a candidate charter")

    def advance(
        self,
        charter: Charter,
        session_id: str,
        expected_sequence: int,
        receipts: Iterable[EffectReceipt],
    ) -> StepResult:
        state = self.require(session_id)
        if state.sequence != expected_sequence:
            raise ConcurrentUpdateError(
                f"expected session sequence {expected_sequence}, found {state.sequence}"
            )
        result = self.kernel.advance(charter, state, receipts, now=self.clock())
        self.store.compare_and_swap(session_id, expected_sequence, result.state)
        return result

    def abort(self, session_id: str, expected_sequence: int) -> StepResult:
        state = self.require(session_id)
        if state.sequence != expected_sequence:
            raise ConcurrentUpdateError(
                f"expected session sequence {expected_sequence}, found {state.sequence}"
            )
        result = self.kernel.abort(state, now=self.clock())
        self.store.compare_and_swap(session_id, expected_sequence, result.state)
        return result

    def inspect(self, session_id: str) -> SessionState | None:
        return self.store.get(session_id)

    def require(self, session_id: str) -> SessionState:
        state = self.inspect(session_id)
        if state is None:
            raise ProtocolError("session does not exist")
        return state
