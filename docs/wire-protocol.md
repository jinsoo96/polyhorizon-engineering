# Wire protocol v0.1

The reference wire protocol exposes the same `Engine` state machine to non-Python hosts. It is a
strict, request/response NDJSON protocol; it is not an authorization or agent-transport protocol.

The wire API identifier is:

```text
polyhorizon.wire/v0.1
```

The domain API identifiers advertised by the current implementation are:

```text
polyhorizon.charter/v0.1
polyhorizon.proposal/v0.1
polyhorizon.effect/v0.1
```

## 1. Framing

- Input and output are UTF-8 newline-delimited JSON.
- Every nonblank input line must contain one JSON object.
- The server writes exactly one response line for each nonblank input line and flushes it.
- The default maximum encoded input-line size is 4 MiB; hosts may configure a smaller or larger
  positive limit.
- JSON object key order and insignificant whitespace are not semantic.
- Wire JSON is not the canonical JSON profile used for semantic digests.

`polyhorizon serve` implements this protocol over standard input and standard output. Transport
authentication, request authorization, queueing, rate limits, timeouts, and process isolation are
host responsibilities.

## 2. Request envelope

Every request has exactly four fields:

```json
{
  "api_version": "polyhorizon.wire/v0.1",
  "request_id": "client-42",
  "command": "capabilities",
  "payload": {}
}
```

| Field | Meaning |
|---|---|
| `api_version` | exact wire API identifier |
| `request_id` | caller-chosen portable identifier used to correlate the response |
| `command` | one of `capabilities`, `open`, `advance`, `inspect`, or `abort` |
| `payload` | command-specific JSON object |

The v0.1 reference codec rejects unknown envelope and command-payload fields. Future compatibility
is negotiated through `capabilities` and a new protocol version, not by assuming an ignored field
was understood.

## 3. Response envelopes

A successful response contains `payload`:

```json
{
  "api_version": "polyhorizon.wire/v0.1",
  "request_id": "client-42",
  "ok": true,
  "payload": {}
}
```

An error response contains `error` instead:

```json
{
  "api_version": "polyhorizon.wire/v0.1",
  "request_id": "client-42",
  "ok": false,
  "error": {
    "code": "unsupported_command",
    "message": "unsupported command: example"
  }
}
```

When parsing fails before a valid identifier is available, `request_id` is `unknown`. Error
messages are diagnostic and must not contain secrets. Clients should branch on `error.code`, not
parse human-readable messages.

## 4. Commands

### `capabilities`

Request payload: an empty object.

The current result is equivalent to:

```json
{
  "wire_api": "polyhorizon.wire/v0.1",
  "domain_apis": [
    "polyhorizon.charter/v0.1",
    "polyhorizon.proposal/v0.1",
    "polyhorizon.effect/v0.1"
  ],
  "commands": ["abort", "advance", "capabilities", "inspect", "open"],
  "transport": "ndjson",
  "effect_execution": "host-owned",
  "digest_profile": "polyhorizon.engine.v1"
}
```

Clients should inspect rather than hardcode this result when selecting a peer.

### `open`

Request payload:

| Field | Required | Meaning |
|---|---:|---|
| `charter` | yes | predecessor `Charter` object |
| `proposal` | yes | bound `Proposal` object |
| `candidate` | amendment only | proposed successor `Charter`; omit or use `null` otherwise |

The result is a [step result](#5-step-result). Opening is idempotent through
`Proposal.idempotency_key`: replay with the same key and charter/proposal binding returns the
stored session; conflicting reuse fails.

### `advance`

Request payload:

| Field | Required | Meaning |
|---|---:|---|
| `charter` | yes | the same active predecessor `Charter` |
| `session_id` | yes | session returned by `open` |
| `expected_sequence` | yes | current non-negative session sequence |
| `receipts` | yes | array of bound `EffectReceipt` objects; empty only for an expiry tick |

The result is a step result. `expected_sequence` is a compare-and-swap token. A stale value returns
`concurrent_update`. Each effect request may receive at most one accepted receipt, and receipt IDs
must be unique.

### `inspect`

Request payload:

```json
{"session_id": "session-example"}
```

The result contains the serialized `state` and `state_digest`. A missing session returns
`not_found`. Inspection does not advance a session.

### `abort`

Request payload:

```json
{
  "session_id": "session-example",
  "expected_sequence": 0
}
```

The result is a step result. Only a session in `awaiting_effects` may be aborted. Abort advances
the sequence and produces no `Decision`; it does not execute rollback or claimant recourse.

## 5. Step result

`open`, `advance`, and `abort` return:

```json
{
  "state": {},
  "state_digest": "sha256:...",
  "effects": [],
  "decision": null
}
```

| Field | Meaning |
|---|---|
| `state` | complete serialized `SessionState` |
| `state_digest` | semantic digest of the state material |
| `effects` | `EffectRequest` values the host still owns and must execute |
| `decision` | terminal `Decision`, or `null` while awaiting effects or after abort |

`Decision.effect` is `allow`, `deny`, or `escalate`. `Decision.horizon_vector` preserves
per-horizon results and must not be replaced by an ungoverned scalar score.

## 6. Effect receipts and result binding

An `EffectReceipt` includes:

```text
api_version, id, request_digest, producer, status,
evidence_digest, result_digest, issued_at, details
```

`status` is `satisfied`, `violated`, `unknown`, or `uncovered`. The engine validates that the
receipt names a pending request, an allowed predecessor producer, and an issue time inside the
session and request interval.

`details` is non-normative diagnostic metadata. It is present in serialized state but excluded
from `EffectReceipt.material()`, the receipt digest, and consequently `SessionState.digest`.
Clients must not place decision-bearing result content only in `details` or treat a changed detail
as a changed normative state.

`result_digest` binds the exact external result held by the host; `evidence_digest` binds its
supporting evidence. The wire protocol does not transfer those external materials or prescribe a
universal result schema. The adapter contract must identify the schema and canonicalization used
to reproduce the digest.

## 7. Error codes

| Code | Meaning |
|---|---|
| `invalid_json` | the input line is not JSON |
| `message_too_large` | encoded line exceeds the configured bound |
| `invalid_envelope` | envelope or command payload has a wrong shape, type, or extra field |
| `unsupported_version` | `api_version` is not `polyhorizon.wire/v0.1` |
| `unsupported_command` | command is not implemented |
| `manifest_error` | charter, proposal, receipt, or nested manifest is structurally invalid |
| `invalid_value` | a typed value violates a domain invariant |
| `protocol_error` | session or receipt state-machine invariant is violated |
| `concurrent_update` | `expected_sequence` is stale or the session is being updated |
| `not_found` | inspected session does not exist |
| `internal_error` | an unexpected server failure was redacted |

Receiving an error does not prove that an external effect did not occur. Hosts must recover
effect completion by stable request identity after transport or process failures.

## 8. Security and authority boundary

- NDJSON framing does not authenticate or authorize a peer.
- A transport identity does not replace a charter mandate or predecessor ratification.
- The subject system must not be able to rewrite persisted state, charter artifacts, or external
  results whose digests support receipts.
- Input size limits do not replace depth, queue, CPU, memory, and adapter resource controls.
- A local `FileSessionStore` does not provide distributed consensus, a transparency log, or an
  atomic transaction with external effects.
- A valid receipt proves binding and declared producer identity, not truth or institutional
  legitimacy.

See the [integration guide](integration.md) for host responsibilities and the
[threat model](threat-model.md) for residual risks.
