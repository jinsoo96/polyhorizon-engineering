# Threat model

This threat model covers the reference Polyhorizon kernel, its in-process interpreter, and its
versioned NDJSON interface. A concrete deployment MUST add the trust assumptions and threats of its
identity, storage, policy, evaluator, transport, and effect-execution systems.

## 1. Security objectives

The kernel aims to preserve:

- **binding integrity** — evidence and receipts apply only to the exact session, sequence, request,
  proposal, charter, producer, and payload they name, plus any implementation material the
  deployment binds in the external result contract;
- **decision integrity** — hard findings cannot be scalarized away or rewritten by an extension;
- **charter continuity** — open obligations and horizon contractions cannot disappear across
  revisions without predecessor-authorized records;
- **amendment integrity** — a successor charter cannot ratify itself;
- **epistemic integrity** — `unknown` and `uncovered` cannot become satisfied by omission;
- **recourse truthfulness** — nominal recovery is not reported as executable recourse without the
  declared proof or completion receipt;
- **replay safety** — repeated commands and receipts are idempotent or rejected according to their
  sequence; and
- **audit continuity** — a decision can be reconstructed from canonical public records without
  exposing secrets in those records.

Availability is bounded by the host's liveness policy. Safety-critical uncertainty may legitimately
produce `ESCALATE`, which an adversary can try to amplify into denial of service.

## 2. Assets

Protected assets include:

- telic charter versions and semantic diffs;
- open obligation and authorized-discharge state;
- standing and authority snapshots;
- proposal and artifact identities;
- horizon evaluator and evidence-contract identities;
- effect requests and receipts;
- recourse reservations and terminal receipts;
- session state, sequence, and idempotency records;
- audit ledger roots and canonical digest test vectors; and
- decision reason codes and findings.

Secrets, raw credentials, private model context, and sensitive evidence SHOULD remain in host-owned
systems. Kernel records SHOULD carry opaque references, minimized claims, or verifiable proofs
instead of secret values.

## 3. Trust boundaries

### Pure kernel

The pure transition function is trusted to validate events, enforce state invariants, emit effect
requests, and produce deterministic outcomes. It has no direct filesystem, network, clock,
identity, policy, randomness, or model authority.

### Host interpreter

The host schedules steps, persists state, executes effects, selects implementations, applies
resource limits, and returns receipts. A malicious host can suppress effects, lie about persistence,
or refuse to enforce an outcome. The kernel can detect malformed or misbound receipts; it cannot
force a hostile host to act.

High-assurance deployments need independent receipt signatures, append-only storage, external
anchors, or multiple trust domains appropriate to their threat model.

### Effect adapters

Impact mappers, horizon evaluators, standing resolvers, authority verifiers, evidence verifiers,
policy engines, clocks, state stores, and recourse executors are external. Their implementation
identity and output binding are checked, but their correctness and honesty remain trust assumptions
unless corroborated independently.

### Candidate and Forge

The candidate and its Forge are untrusted. They may know the public charter and may intentionally
search for horizon gaps, evaluator weaknesses, parser differences, or recourse failures.

### Wire peer and transport

NDJSON peers are untrusted until transport authentication and application authority are verified.
JSON framing is not authentication. A valid envelope can still be unauthorized.

## 4. Adversaries

The model includes:

- a candidate that tries to tamper with evaluation, evidence, or its own charter;
- an authorized but conflicted proposer that narrows scope to improve reported outcomes;
- a malicious or compromised effect adapter;
- a principal that replays stale authority after revocation;
- a wire client that reorders, duplicates, truncates, or cross-binds messages;
- a plugin package that changes behavior without changing its declared name;
- a ledger operator that rolls back, forks, truncates, or substitutes history;
- an affected party or attacker that creates identity or standing ambiguity to force escalation;
- a host that fails between an external effect and durable state commit; and
- an observer that provides strategically incomplete causal or population coverage.

## 5. Threats and required mitigations

### Receipt replay and substitution

**Threat:** reuse a valid receipt for a different request, candidate, charter, session, sequence,
adapter revision, or payload.

**Mitigations:** domain-separated canonical digests; exact request and producer binding; externally
bound implementation identity where required; monotonic sequence; idempotency key; expiry where
relevant; rejection of unrequested receipts.

### Diagnostic-detail confusion

**Threat:** place a decision-bearing score, proof, or policy result only in
`EffectReceipt.details`, or assume two serialized states differ normatively because their details
differ.

**Mitigations:** treat `details` as non-normative diagnostics; retain the exact external result and
bind it with `result_digest`; bind supporting evidence with `evidence_digest`; compare the returned
semantic digests rather than hashing display JSON.

### Authority TOCTOU

**Threat:** authority changes between proposal, evaluation, effect execution, and promotion.

**Mitigations:** bind the authority snapshot and verifier implementation; require a new effect when
freshness expires; recheck around consequential terminal effects; quarantine or escalate uncertain
completion.

### Successor self-ratification

**Threat:** a proposal weakens quorum, adds itself as an approver, deletes standing, or changes the
amendment rule and then uses those new rights immediately.

**Mitigations:** resolve amendment authority only from the predecessor charter; bind exact charter
diff and predecessor ledger root; reject successor-only discharge and approvals.

### Horizon downgrade and semantic aliasing

**Threat:** rename a horizon, metric, unit, party, evaluator, or schema so that a contraction looks
like an unrelated addition/deletion.

**Mitigations:** stable identifiers; explicit semantic migrations; typed units and schema versions;
predecessor-authorized equivalence; fail-closed handling of unknown migrations.

### Passive footprint expansion

**Threat:** add a tool, connector, data flow, customer population, or downstream automated consumer
without adding observation and standing coverage.

**Mitigations:** host-supplied effect graph; capability and dependency diff; coverage request before
admission; `uncovered -> ESCALATE`.

The kernel cannot detect a footprint edge omitted by every discovery source.

### Obligation orphaning

**Threat:** delete the bearer, metric, evaluator, or configuration record of an open obligation.

**Mitigations:** obligation identity independent of implementation; carry-forward check at every
charter terminal; authorized discharge event; ledger-root binding.

### Scalar and confidence laundering

**Threat:** average away a hard violation, convert missing data to zero, or use an unjustified
confidence summary.

**Mitigations:** four-state findings; hard conjunctive semantics; typed units and uncertainty;
aggregation allowed only by a versioned charter rule; raw finding preservation.

### Recourse theater

**Threat:** declare rollback, appeal, compensation, or human review that cannot actually execute.

**Mitigations:** recourse effect request; implementation and authority binding; resource
reservation or readiness receipt; fault injection; terminal receipt tied to claimant and deadline.

### Adapter or plugin compromise

**Threat:** allowlisted code is malicious, compromised, or changes behavior between resolution and
use.

**Mitigations:** explicit registration; distribution/version/digest locks; before/after identity
checks; process isolation where risk warrants; independent evidence domains; least-privilege host
capabilities.

An in-process plugin remains trusted code regardless of its digest.

### Canonicalization divergence

**Threat:** different runtimes hash semantically equivalent or ambiguous JSON differently.

**Mitigations:** one normative canonicalization profile; reject duplicate keys, non-finite numbers,
ambiguous Unicode or unsupported numeric forms; publish cross-language digest vectors; distinguish
wire serialization from digest serialization.

### NDJSON framing and resource exhaustion

**Threat:** oversized lines, deep objects, invalid UTF-8, duplicate keys, output flooding, slow
readers, or sequence gaps cause parser confusion or denial of service.

**Mitigations:** host-configured line/depth/count limits; strict UTF-8 JSON object per line; strict
v0.1 field sets; duplicate-key rejection in the CLI and NDJSON decoder; bounded queues; timeouts
outside the pure kernel; stable error responses; never include secrets in parser errors. A host
that constructs mappings programmatically remains responsible for rejecting duplicates before
they are collapsed by its own parser.

### Crash between effect and commit

**Threat:** an external effect succeeds but the host crashes before persisting the receipt or next
state, causing duplicate execution or uncertain outcome.

**Mitigations:** stable idempotency key; adapter-level deduplication; write-ahead request record;
receipt recovery by request identifier; explicit `unknown` or quarantine state when completion
cannot be proved. The kernel does not provide a distributed transaction.

### Audit rollback and truncation

**Threat:** replace a ledger with an older valid prefix or fork history.

**Mitigations:** hash chaining plus an externally retained anchor, monotonic store version, signed
checkpoints, or a transparency service. A local hash chain alone cannot detect replacement with an
older complete copy.

### Escalation denial of service

**Threat:** create ambiguous identities, effects, or evidence to keep the system in escalation.

**Mitigations:** bounded evidence and escalation budgets; priority and triage policy; cached valid
receipts; explicit liveness objectives; operator-visible cause. The engine MUST NOT convert
uncertainty into allow merely to improve availability.

## 6. Public repository and artifact boundary

The public repository MUST exclude credentials, internal worklogs, local state, raw evidence,
private charter deployments, and operational receipts. Local ignore rules are insufficient:
pre-commit, pre-push, and CI checks should inspect every outgoing commit tree, and release checks
should inspect wheel and source archives.

Path scanning does not replace secret scanning or prose review. A public research document can
still contain a copied secret even when its path is permitted.

## 7. Non-goals and residual risk

The reference kernel does not:

- discover every causal effect or affected party;
- prove that a charter or authority structure is just;
- authenticate principals without an external verifier;
- make in-process adapters safe;
- guarantee that a hostile host enforces deny or recourse;
- provide Byzantine consensus or distributed transactions;
- make forecasts correct;
- make irreversible harm reversible; or
- ensure that procedural compliance produces a beneficial social outcome.

A production security case must state which of these risks is accepted, transferred, or addressed
by external controls.
