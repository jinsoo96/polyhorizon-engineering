# Integration guide

Polyhorizon is an admission engine, not an agent platform. Embed it at the boundary where a host
can stop or defer a proposal before the subject system performs the proposed action. The same
domain objects and state machine are available through Python, a local command-line interface, and
the versioned NDJSON wire protocol.

The host keeps all ambient authority. The kernel requests observations, standing resolution,
authority checks, and recourse reservations as `EffectRequest` values; host-owned adapters return
`EffectReceipt` values. An `ALLOW` decision records admission under one charter and evidence set.
It does not execute the proposal or force a hostile host to obey the decision.

## 1. Install and inspect capabilities

```bash
python -m pip install polyhorizon-engineering
polyhorizon capabilities
```

The package requires Python 3.11 or newer and has no runtime dependencies. The capabilities result
is the reliable way to discover wire, domain API, command, transport, effect-ownership, and digest
profile versions. Do not infer compatibility from the package version alone.

## 2. Choose an attachment surface

| Surface | Use when | State ownership |
|---|---|---|
| `PureKernel` | a host already owns event ordering and persistence | entirely host-owned |
| `Engine` | Python code wants open/advance/inspect/abort orchestration | injected `SessionStore` |
| `InProcessRunner` | all effect handlers are trusted in one Python process | injected `Engine` and handlers |
| CLI | a human or CI job manages JSON files and a local state directory | `FileSessionStore` |
| NDJSON `WireEngine` | another language, subprocess, sidecar, or service hosts the engine | server process store |

`Charter`, `Proposal`, `PureKernel`, `Engine`, `SessionStore`, `EffectRequest`, and
`EffectReceipt` are the stable concepts across all surfaces. Transport adapters must preserve
their binding and decision semantics.

## 3. Python orchestration

Load manifests through the typed constructors and inject a store appropriate to the deployment:

```python
import json
from pathlib import Path

from polyhorizon import Charter, Engine, FileSessionStore, Proposal

charter = Charter.from_dict(json.loads(Path("charter.json").read_text(encoding="utf-8")))
proposal = Proposal.from_dict(json.loads(Path("proposal.json").read_text(encoding="utf-8")))

engine = Engine(store=FileSessionStore(".polyhorizon/state"))
step = engine.open(charter, proposal)

while step.effects:
    receipts = tuple(execute_with_host_adapter(request) for request in step.effects)
    step = engine.advance(
        charter,
        step.state.id,
        step.state.sequence,
        receipts,
    )

decision = step.decision
```

The repository includes a complete [Forge mutation example](../examples/README.md) and a Node
client that drives the Python NDJSON sidecar.

For an amendment proposal, pass the proposed successor as `candidate=...` to `Engine.open`.
`Proposal.base_charter_digest` must equal the predecessor `Charter.digest`, and
`Proposal.candidate_charter_digest` must equal the candidate digest. All amendment effect requests
and accepted producers are resolved from the predecessor charter. An amendment proposal must also
carry `ledger_root_digest`, the root of the predecessor obligation history maintained by the host.
Ratification/root requests expose the exact typed material diff and a digest over that diff plus
the ledger root; release/discharge requests expose the affected before/after material. The alpha
kernel binds this root but does not fetch or prove its contents. The predecessor authority adapter
must resolve and verify it against the host's durable ledger.

The alpha engine does not emit an impact-discovery request. Before calling `open`, the host must
combine the actor's declared claims with outputs from the independent discovery sources required
by its deployment, bind that fixed set into the proposal artifact, and reject unexplained
omissions. `EffectReceipt.details` is not a channel for adding claims after the session opens.

The example intentionally leaves `execute_with_host_adapter` to the host. An adapter may call a
policy engine, evaluator, identity service, assurance system, human workflow, or recourse
executor. The kernel does not hardcode those systems.

### In-process handler registry

An `EffectHandler` implements:

```python
def handle(request: EffectRequest) -> EffectReceipt: ...
```

Register handlers by the exact `request.provider` value and use `InProcessRunner` for the bounded
open/advance loop. This is convenient, but it is not process isolation. A digest or allowlist does
not make candidate-controlled code independent when it executes in the same process.

### Direct pure-kernel use

`PureKernel.open`, `PureKernel.advance`, and `PureKernel.abort` take an explicit `now` value and do
not access a clock or store. Use this surface for deterministic replay, alternative runtimes, and
conformance interpreters. Persist the returned `SessionState` before dispatching newly emitted
effects, and advance it with compare-and-swap semantics.

## 4. Effect execution contract

For each emitted `EffectRequest`, the host should:

1. persist the state and request before starting an external effect;
2. route by the request's exact provider and kind, subject to host resource limits;
3. execute idempotently using the request digest as the stable operation binding;
4. store sensitive or large evidence and result material outside the engine state;
5. compute `evidence_digest` and `result_digest` over the exact external materials;
6. return one `EffectReceipt` from an allowed predecessor principal before request expiry; and
7. call `advance` with the current session sequence.

`EffectReceipt.status` is one of `satisfied`, `violated`, `unknown`, or `uncovered`. Missing
coverage must remain `uncovered`; an evaluator failure or unresolved mapped question must remain
`unknown`. Neither is an empty success.

### Normative result versus diagnostic details

`EffectReceipt.details` is optional, non-normative diagnostic metadata. It is serialized for
inspection, but it is excluded from the receipt's semantic material and therefore from the
`SessionState.digest`. Decision-bearing adapters must not place a score, proof, policy result, or
other material fact only in `details`.

The external result is bound by `result_digest`; its supporting evidence is bound by
`evidence_digest`. A host that needs to reconstruct or independently verify a decision must retain
the exact external bytes, canonicalization profile, schema, and provenance needed to reproduce
those digests. A digest prevents substitution; it does not prove the producer was truthful.

## 5. Session storage and concurrency

`SessionStore` has four operations:

```python
get(session_id) -> SessionState | None
get_by_idempotency(idempotency_key) -> SessionState | None
put_new(state) -> SessionState
compare_and_swap(session_id, expected_sequence, state) -> None
```

`MemorySessionStore` is process-local. `FileSessionStore` is a restart-safe local implementation
with hashed OS advisory locks, an atomic idempotency index, atomic file replacement, and strict
per-session compare-and-swap. Persistent lock files do not represent ownership; the operating
system releases ownership when a process exits. This assumes cooperating processes on one local
filesystem and is not a distributed database, NFS lock guarantee, or Byzantine ledger. Services
should implement `SessionStore` over their durable store and preserve the same idempotency,
immutable-binding, append-only protocol-entry, and monotonic-sequence contract.

There is no distributed transaction between state persistence and an external effect. Providers
therefore need idempotent execution or result recovery by request identity. If completion cannot be
proved after a crash, report `unknown` or quarantine the operation rather than manufacturing a
receipt.

## 6. CLI workflows

The CLI exposes local validation and persisted-session commands in addition to the wire server:

```bash
polyhorizon validate-charter charter.json
polyhorizon validate-proposal --charter charter.json proposal.json
polyhorizon open --state-dir .polyhorizon/state --charter charter.json proposal.json
polyhorizon inspect --state-dir .polyhorizon/state SESSION_ID
polyhorizon advance --state-dir .polyhorizon/state --charter charter.json --session SESSION_ID --expected-sequence 0 receipts.json
polyhorizon abort --state-dir .polyhorizon/state --expected-sequence 0 SESSION_ID
polyhorizon serve --state-dir .polyhorizon/state
```

`validate-charter` and `validate-proposal` are CLI conveniences, not wire commands. The wire
command set is `capabilities`, `open`, `advance`, `inspect`, and `abort`.

CLI decision exit codes are `0` for an awaiting step or `ALLOW`, `3` for `DENY`, and `4` for
`ESCALATE`; input and protocol failures return `2`. A CI integration should parse the JSON result
as the primary contract and use exit codes only for process control.

## 7. Subprocess, sidecar, and service hosting

Start `polyhorizon serve` and exchange one UTF-8 JSON object per line. Keep the process alive when
using an in-memory store; restarting it loses those sessions. Use `--state-dir` or inject another
`SessionStore` when sessions must survive restarts.

HTTP, a queue, MCP, A2A, or another RPC system can carry the same envelopes. Such a carrier is only
transport. It must not be treated as proof that the caller has proposal, observation, amendment,
or recourse authority. See the [wire protocol](wire-protocol.md) for the exact envelope.

## 8. Typical placements

### Forge or loop admission gate

The Forge proposes a harness or loop revision. The host computes the artifact digest, loads the
active predecessor charter, opens a Polyhorizon session, executes independent effects, and promotes
the revision only on `ALLOW`. `DENY` blocks it; `ESCALATE` routes the same bound proposal for more
evidence or authorized human resolution.

### CI gate

Store charter and proposal artifacts separately from repository secrets. Run the engine before the
deployment job, archive the terminal state and externally bound evidence, and configure branch or
deployment protection so the subject cannot bypass the result.

### Long-running service

Place `WireEngine` behind authenticated transport, inject a durable compare-and-swap store, limit
line size and work queues, isolate untrusted effect adapters, and anchor decision history outside
the service. Authentication identifies a peer; charter mandates and predecessor rules determine
authority.

## 9. Integration checklist

- Put admission on a path the subject system cannot bypass.
- Keep the active predecessor charter and candidate artifact immutable during a session.
- Resolve effect producers from the predecessor charter, not a successor proposal.
- Preserve `EffectReceipt.details` as diagnostic only; bind external results with `result_digest`.
- Persist requests before effects and use compare-and-swap for session updates.
- Do not scalarize the per-horizon decision vector or coerce `unknown`/`uncovered` to success.
- Keep evidence, identity, recourse execution, and policy systems behind replaceable adapters.
- Publish the deployment's trusted components, discovery limits, and enforcement boundary.
