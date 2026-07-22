# Architecture

Polyhorizon is designed as a transport-neutral decision engine. The semantic center is a pure
transition function; storage, clocks, identity, policy, observation, models, and recourse execution
remain host-owned effects. This boundary lets one decision model run in a Python process, a
subprocess, a sidecar, a CI gate, or a service without giving the kernel ambient authority.

This document distinguishes three things deliberately:

- **method requirements** are normative in [POLYHORIZON.md](../POLYHORIZON.md);
- **protocol requirements** define interoperable messages and bindings; and
- **reference implementation details** may evolve while the alpha API is versioned.

## 1. Control plane, effect plane, and subject plane

The architecture separates three planes.

### Control plane

The control plane holds the charter and evaluates proposals. Its state includes the charter
digest, proposal digest, session sequence, outstanding requests, accepted receipts, findings, and
terminal outcome. It decides; it does not execute the proposed action.

### Effect plane

The effect plane is owned by the embedding host. Providers resolve standing, verify authority,
observe horizons, validate evidence, reserve recourse, and perform any other typed request. A
provider returns a receipt bound to the exact request. Provider code is outside the pure kernel and
inside the deployment's trusted computing base to the degree declared by the charter.

### Subject plane

The subject plane contains the agent, harness, loop, Forge, CI workflow, robot, application, or
other system whose proposal is being considered. It cannot write control-plane state directly. A
terminal `ALLOW` is a decision record, not execution; the host remains responsible for enforcing
it before admitting the subject-plane action.

```text
 subject / Forge                Polyhorizon control plane            host effect plane
       |                                   |                                  |
       | proposal                          |                                  |
       +---------------------------------->|                                  |
       |                                   | EffectRequest                    |
       |                                   +--------------------------------->|
       |                                   |                    EffectReceipt |
       |                                   |<---------------------------------+
       |                                   |                                  |
       |                 Outcome           |                                  |
       |<----------------------------------+                                  |
       | host enforces ALLOW/DENY/ESCALATE |                                  |
```

## 2. The pure transition boundary

The conceptual kernel signature is:

```text
step(session_state, input_event) -> transition

transition = {
  next_state,
  effect_requests[],
  outcome?
}
```

The function has no implicit clock, randomness, environment variables, filesystem, network,
credentials, global plugin registry, or mutable singleton. All nondeterministic facts arrive as
input events or bound effect receipts. Given the same initial state and the same ordered events, a
conforming interpreter must produce the same state, requests, and hard decision.

An interpreter may run providers immediately, but that convenience loop sits outside `step`:

```text
state = open(charter, proposal, explicit_time)
while not terminal(state):
    transition = step(state, next_event)
    persist_with_compare_and_swap(transition.next_state)
    for request in transition.effect_requests:
        receipt = host.execute(request)
        queue(receipt)
```

Persist-before-effect or write-ahead request recording is a host responsibility. An external effect
and a state-store commit are not one distributed transaction. Stable request identity and provider
idempotency are therefore required for crash recovery.

In the Python reference, `PureKernel` is the effect-free state machine, `Engine` supplies clock and
`SessionStore` orchestration, and `InProcessRunner` is an optional host loop over registered effect
handlers. `WireEngine` exposes the same `Engine` operations without executing effects.

## 3. Public domain model

The alpha reference model uses immutable values and content digests.

| Object | Role |
|---|---|
| `Charter` | versioned purposes, principals, horizons, standing, obligations, recourse, mandates, and predecessor amendment rule |
| `Horizon` | namespaced consequence kind, effect/resource selectors, observers, and minimum independent trust domains |
| `Standing` | represented claimant group and typed rights |
| `Obligation` | horizon-scoped predicate joining bearer, beneficiary, observers, decision mode, and recourse |
| `Recourse` | claimant-specific mechanism, executor, reversibility scope, and completion deadline |
| `Mandate` | expiring actor authority over action and resource selectors |
| `Proposal` | exact actor, action, claimed effects, artifact, base charter, optional successor charter, and idempotency key |
| `EffectRequest` | kernel request bound to a session, sequence, charter, proposal, provider, and producer allowlist |
| `EffectReceipt` | provider result bound to the request digest and evidence/result digests |

The current API identifiers are:

```text
polyhorizon.charter/v0.1
polyhorizon.proposal/v0.1
polyhorizon.effect/v0.1
polyhorizon.wire/v0.1
```

Descriptions are human-facing metadata and are intentionally excluded from semantic content
digests. Deployments must not place decision-bearing rules only in descriptions.

## 4. Open horizon type system

The five axes in the standard profile—temporal, causal, standing, authority, and epistemic—are a
useful decomposition, not kernel branches. A horizon carries a portable `kind` identifier. A host
maps that identifier to a versioned provider contract.

A provider registration should bind at least:

```text
kind identifier
input and result schema identifiers
provider and implementation digest
supported protocol versions
required capabilities
trust domain
resource limits
```

Kind identifiers should be namespaced and versioned, for example
`example.org/horizon/delayed-impact/v1`. The portable identifier grammar permits letters, digits,
periods, underscores, colons, slashes, and hyphens; `@` is not part of the alpha grammar.

The kernel owns the invariant that every applicable hard obligation receives a covered finding and
that trust-domain requirements hold. The provider owns the domain-specific meaning of its typed
predicate. Adding a medical, financial, environmental, or infrastructure horizon must therefore
require a registered contract and provider, not a new `if horizon == ...` branch in admission
logic.

The formal projection, time window, uncertainty model, and evidence rules described in
[the theory](theory.md) belong to the registered horizon contract. The compact alpha `Horizon`
object identifies and binds that contract; it does not hardcode every domain field into the
kernel.

## 5. Effect graph and coverage

A proposal declares one or more `ImpactClaim` values. Each claim names an effect, a resource, and
the horizons and standings believed to apply. Claims are assertions, not proof of completeness.
The v0.1 kernel receives a fixed, digest-bound claim set; it does not run discovery or accept
decision-bearing discoveries through diagnostic receipt details. A production host must run its
independent discovery sources before `open` and either bind their claims into the proposal artifact
or reject a proposal that omits them.

Coverage evaluation compares that bound claim set with charter selectors:

```text
known effect/resource
  -> matching horizons
  -> matching obligations
  -> required observers and trust domains
  -> beneficiary standing
  -> applicable recourse
```

The engine must preserve four findings: `satisfied`, `violated`, `unknown`, and `uncovered`.
`unknown` means a mapped question could not be resolved from acceptable evidence. `uncovered`
means a known effect has no adequate declared mapping. Neither is false, zero, or success.

Discovery is necessarily relative to host adapters and declared topology. If every source omits an
effect, the pure kernel cannot infer it from nothing. Independent discovery sources and hidden
challenge tests reduce this risk but do not eliminate it.

## 6. Admission compilation

Domain providers return typed evidence. The method layer compiles those results into a small,
stable admission intermediate representation rather than allowing plugins to invent terminal
semantics.

```text
provider-specific result
  -> schema validation
  -> request/result binding validation
  -> finding: satisfied | violated | unknown | uncovered
  -> obligation mode: hard | review | advisory
  -> reason record
  -> ALLOW | DENY | ESCALATE
```

The proposal separately declares reversibility as `reversible`, `compensatable`, or `irreversible`.
This is not an obligation score. It determines which declared recourse mechanisms may legitimately
apply. An advisory benefit cannot compensate for a violated hard obligation; an allegedly
compensatable action cannot proceed on the strength of recourse that is not executable.

Extensions may add evidence fields and reason detail. They may not add a fourth terminal decision,
rewrite hard-decision precedence, or silently coerce `unknown`/`uncovered` to `satisfied`.

## 7. Amendment and continuity

A proposal with `candidate_charter_digest` is an amendment proposal. The predecessor charter
remains the authority source for that transition. At minimum, evaluation must establish:

- the proposal's `base_charter_digest` is the active charter;
- the candidate content matches `candidate_charter_digest`;
- the proposal binds the predecessor's externally maintained obligation ledger root;
- the actor has an unexpired amendment-capable mandate under the predecessor;
- the predecessor amendment rule's standing threshold is met;
- a removed principal or a changed principal trust domain or adapter is released by that
  predecessor principal through its predecessor adapter;
- removed or weakened coverage is exposed rather than hidden by rename; and
- open obligations are carried forward, substituted, or validly discharged.

The alpha engine emits a deterministic typed material diff in predecessor ratification and root
requests, and its digest also binds the supplied predecessor ledger root. Per-object release and
discharge requests carry their exact before/after material. A durable obligation lifecycle ledger,
semantic-equivalence migration proof, and stateful discharge protocol remain separate features and
must not be simulated by deleting manifest entries. Until those features are implemented and
tested, the reference package should be treated as an experimental gate rather than a complete
governance system.

## 8. Receipt binding and evidence handling

Every effect request binds:

- request, session, and monotonic sequence identity;
- active charter and proposal digests;
- provider kind and allowed producer identities;
- logical group and canonical payload; and
- expiry.

Every receipt binds the request digest, producer, four-state status, evidence digest, result
digest, and issue time. Large or sensitive result material should remain in a host evidence store;
the receipt carries its digest. `EffectReceipt.details` is optional, non-normative diagnostic
metadata. The reference serializer exposes it in state JSON, but receipt and session semantic
digests exclude it. A decision-bearing value must live in the external result bound by
`result_digest`; supporting evidence is bound separately by `evidence_digest`.

Bindings prevent substitution; they do not prove that a producer is honest. Trust-domain
independence, signatures, attestations, replicated observers, or institutional review are
deployment choices.

## 9. State, concurrency, and replay

Session state should be persisted with compare-and-swap on `(session_id, sequence)` or an equivalent
version token. Locking every subject behind one global process lock is not a portable concurrency
model. Independent sessions may advance concurrently; events within a session are ordered.

Hosts should retain:

- the latest session state and its version;
- a write-ahead record of emitted requests;
- receipts indexed by request digest;
- proposal idempotency records;
- terminal outcomes; and
- charter and obligation history required for continuity checks.

The serialized `state` is an inspection and persistence form; not every displayed field is
normative digest material. In particular, receipt `details` is excluded. Integrations must use the
returned `state_digest` and the domain-separated object digests rather than hashing display JSON.

Duplicate delivery of the same event may return the recorded transition. Conflicting content under
the same identity must fail. A receipt for a different session, sequence, request, charter,
proposal, producer, payload, or expired request must not advance state.

## 10. Canonicalization

Semantic digests use domain separation so that equal JSON material in different object roles does
not share an identity accidentally. The v0.1 profile permits null, booleans, Unicode-scalar
strings, arrays, string-keyed objects, and exact interoperable integers. It rejects every floating
point value, surrogate code point, and integer outside the portable exact range. Object keys use
UTF-8 byte order without Unicode normalization; timestamps use the strict RFC 3339 subset defined
in the method specification and canonicalize to UTC.

[`examples/conformance/digests.json`](../examples/conformance/digests.json) is the normative
cross-language corpus for `polyhorizon.engine.v1`. This is a project-specific, deliberately narrow
profile, not a claim of RFC 8785/JCS compatibility. Wire JSON and digest canonical JSON are related
but not interchangeable concepts.

## 11. Enforcement boundary

The engine can produce an outcome and a reconstructable reason chain. It cannot force a hostile
host to obey `DENY`, execute recourse, persist history, or reveal omitted effects. Production
deployments should put the admission check on an enforcement path the subject cannot bypass and
should state the trusted components publicly.

This architecture is intentionally smaller than a platform: identity systems, databases, policy
engines, model providers, MCP servers, A2A peers, CI systems, and observability stacks connect
through explicit host adapters. Their existence is not hardcoded into the kernel.
