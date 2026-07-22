from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from polyhorizon.canonical import content_digest
from polyhorizon.models import Charter, EffectReceipt, Proposal, ReceiptStatus
from polyhorizon.runtime import Engine

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
EXAMPLE_ROOT = Path(__file__).resolve().parents[1] / "forge-mutation"


def load(path: str) -> object:
    return json.loads((EXAMPLE_ROOT / path).read_text(encoding="utf-8"))


def main() -> None:
    charter = Charter.from_dict(load("charter.v1.json"))
    candidate = Charter.from_dict(load("charter.v1.1-candidate.json"))
    proposal = Proposal.from_dict(load("proposal.json"))
    engine = Engine(clock=lambda: NOW)

    opened = engine.open(charter, proposal, candidate=candidate)
    receipts = tuple(
        EffectReceipt(
            id=f"receipt.{index:02d}",
            request_digest=request.digest,
            producer=request.allowed_producers[0],
            status=ReceiptStatus.SATISFIED,
            evidence_digest=content_digest(f"evidence:{request.id}"),
            result_digest=content_digest(f"result:{request.id}:satisfied"),
            issued_at=NOW,
            details={"example": "forge-mutation"},
        )
        for index, request in enumerate(opened.effects, start=1)
    )
    completed = engine.advance(charter, opened.state.id, opened.state.sequence, receipts)

    print(
        json.dumps(
            {
                "session_id": completed.state.id,
                "requests": len(opened.effects),
                "decision": completed.decision.effect.value if completed.decision else None,
                "horizons": [
                    {
                        "id": horizon.horizon_id,
                        "effect": horizon.effect.value,
                    }
                    for horizon in (completed.decision.horizon_vector if completed.decision else ())
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
