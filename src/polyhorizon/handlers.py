from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from polyhorizon.errors import ProtocolError
from polyhorizon.kernel import SessionStatus, StepResult
from polyhorizon.models import Charter, EffectReceipt, EffectRequest, Proposal
from polyhorizon.runtime import Engine


@runtime_checkable
class EffectHandler(Protocol):
    def handle(self, request: EffectRequest) -> EffectReceipt: ...


class HandlerRegistry:
    def __init__(self, handlers: Mapping[str, EffectHandler] | None = None) -> None:
        self._handlers: dict[str, EffectHandler] = {}
        if handlers is not None:
            for provider, handler in handlers.items():
                self.register(provider, handler)

    def register(self, provider: str, handler: EffectHandler) -> None:
        if provider in self._handlers:
            raise ValueError(f"provider is already registered: {provider}")
        if not isinstance(handler, EffectHandler):
            raise TypeError("handler does not implement EffectHandler")
        self._handlers[provider] = handler

    def handle(self, request: EffectRequest) -> EffectReceipt:
        handler = self._handlers.get(request.provider)
        if handler is None:
            raise ProtocolError(f"no in-process handler for provider: {request.provider}")
        return handler.handle(request)


class InProcessRunner:
    def __init__(self, engine: Engine, handlers: HandlerRegistry) -> None:
        self.engine = engine
        self.handlers = handlers

    def run(
        self,
        charter: Charter,
        proposal: Proposal,
        *,
        candidate: Charter | None = None,
        max_rounds: int = 32,
    ) -> StepResult:
        if isinstance(max_rounds, bool) or not isinstance(max_rounds, int) or max_rounds < 1:
            raise ValueError("max_rounds must be a positive integer")
        result = self.engine.open(charter, proposal, candidate=candidate)
        for _ in range(max_rounds):
            if result.state.status is not SessionStatus.AWAITING_EFFECTS:
                return result
            receipts = tuple(self.handlers.handle(request) for request in result.effects)
            result = self.engine.advance(
                charter,
                result.state.id,
                result.state.sequence,
                receipts,
            )
        raise ProtocolError("in-process runner exhausted max_rounds")
