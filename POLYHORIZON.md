# Polyhorizon Engineering Method, v0.1 Draft

This document is normative for the method. The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are to be interpreted as requirement levels. Conformance is always relative to a
declared charter, host boundary, effect graph, evidence contract, and protocol version.

## 1. Definition and scope

**Polyhorizon Engineering is the engineering of plural, non-collapsible consequence horizons and
the legitimate rules by which evolving agent systems may amend them.**

It applies when a system can repeatedly act, change its own harness or loop policy, change its
evaluation machinery, expand its causal footprint, or operate for parties other than the immediate
operator.

It does not decide a uniquely correct social objective. It provides executable semantics for:

- declaring whose purposes and claims are represented;
- preserving open obligations across system and charter revisions;
- exposing known gaps rather than treating them as zero risk;
- separating proposal capability from amendment authority; and
- preserving contest, appeal, rollback, repair, exit, or handoff where the charter requires them.

## 2. Controlled object

Let an evolving agent system be:

\[
k_t = (H_t, L_t, F_t)
\]

where `H` is its harness, `L` its repeated trajectory policy, and `F` the operator that proposes
changes to the first two. A Forge proposal is a motion:

\[
m_t : k_t \rightarrow k_{t+1}
\]

Polyhorizon does not replace `F`. It controls a protected telic charter:

\[
\Theta_t = (P_t, \mathcal H_t, \mathcal O_t, \mathcal S_t,
\mathcal A_t, \mathcal R_t, \mu_t)
\]

where:

- `P` is a versioned set of declared purposes and anti-purposes;
- `H` is a registry of typed consequence horizons;
- `O` is the open and discharged obligation ledger;
- `S` is affected-party standing;
- `A` is delegated authority and separation-of-duty policy;
- `R` is executable recourse; and
- `mu` is the amendment rule.

The controlled object is not just the next world state. It is the continuity and legitimate
amendment of `Theta` while `k` changes.

## 3. Normative primitives

The reference package represents these primitives with `Charter`, `Proposal`, and their immutable
nested values. A compact alpha field may bind a richer domain contract by digest rather than carry
every domain-specific field inline. Such indirection does not make the external contract optional:
the host must retain and verify the exact material named by the digest.

### 3.1 Purpose

A purpose MUST have a stable identifier, owner, beneficiaries or represented constituency,
effective interval, and revision. A purpose MAY be aspirational, but it MUST NOT silently override
hard obligations. Changing a purpose is a charter amendment, not an ordinary configuration edit.

### 3.2 Horizon

A horizon is a typed observation and consequence boundary:

\[
h=(kind, scope, \pi_h, \tau_h, W_h, evidence_h)
\]

- `kind` is a namespaced, versioned type such as `org.example/temporal/v1`;
- `scope` names the systems, parties, resources, or effects covered;
- `pi` projects relevant world or system state into typed observations;
- `tau` declares the time window or review cadence;
- `W` declares uncertainty or disturbance assumptions; and
- `evidence` declares provenance, freshness, and verifier requirements.

The kernel MUST NOT limit deployments to a fixed enum of horizon kinds. The standard profile MAY
ship temporal, causal, standing, authority, and epistemic kinds, but additional kinds MUST be
registerable without modifying admission semantics.

### 3.3 Obligation

An obligation MUST bind at least:

\[
o=(h, bearer, beneficiary, predicate, mode, deadline, remedy)
\]

The reference `ObligationMode` values are `hard`, `review`, and `advisory`. A hard violation denies;
a review violation escalates; an advisory finding remains visible without overriding a hard
decision. Proposal `Reversibility` and linked `Recourse` describe whether remediation can be
relied upon; they are not weights. Deleting a metric, evaluator, owner, or manifest entry MUST NOT
discharge an obligation. Discharge is a separately authorized event bound to the predecessor
charter and ledger state.

### 3.4 Standing

Standing is a typed relation between a party and a claim or obligation. Standard rights include
`observe`, `contest`, `consent`, `discharge`, and `appeal`. A deployment MAY add rights through a
namespaced extension.

Being affected does not imply a universal veto. The charter defines which right follows from which
effect. If the system can identify an effect but cannot resolve required standing, the result MUST
be `ESCALATE`, not implicit consent.

### 3.5 Authority

Authority MUST be externally verifiable and scoped by operation, target, purpose, horizon, and
time. Capability, authenticated identity, and authority are distinct. A process that can execute a
change does not thereby have authority to approve it.

### 3.6 Recourse

Recourse is a graph of executable actions owed to a claimant, not merely a safe state for the
system. It MAY include contest, human review, rollback, repair, compensation, exit, handoff,
deletion, or stop.

When a proposal relies on remediability, the required executor, authority, resources, and deadline
MUST be verified or reserved before admission. Irreversible disclosure or non-compensable harm
MUST NOT be laundered through a nominal compensation path.

### 3.7 Amendment

Every amendment is evaluated under the predecessor charter:

\[
\Theta_{t+1} \ne \Theta_t
\Rightarrow
Authorized_{\Theta_t}(\Theta_t\rightarrow\Theta_{t+1})
\]

The proposed charter MUST NOT authorize its own adoption. An amendment to the amendment rule MUST
follow the old rule plus any declared external root, delay, or higher-order approval. There is no
infinite self-justifying chain: the genesis charter is an external trust decision.

## 4. Endogenous horizon collapse

Endogenous horizon collapse (EHC) is a system change that earns apparent improvement by shrinking or
failing to expand the boundary within which consequences count.

### 4.1 Active collapse

\[
Obs_{\Theta_{t+1}}(m) \subset Obs_{\Theta_t}(m)
\]

Active collapse includes a shorter evaluation interval, a removed party or causal edge, a weaker
uncertainty set, a less independent evaluator, an erased appeal, or a deleted obligation. A
contraction is not automatically forbidden, but it MUST carry predecessor-authorized rationale,
discharge or substitution evidence, and a diff of the lost coverage.

### 4.2 Passive collapse

\[
Footprint(k_{t+1}) \nsubseteq Coverage(\mathcal H_{t+1})
\]

Passive collapse occurs when a new connector, capability, user population, data flow, or downstream
consumer expands the causal footprint without a corresponding horizon. A known uncovered edge MUST
produce `ESCALATE`.

Coverage is relative to registered discovery adapters and the declared effect graph. Conformance
does not imply discovery of unknown unknowns.

## 5. Required laws

### 5.1 No silent horizon loss

Every removed or weakened horizon, standing right, obligation, authority boundary, evidence
contract, or recourse edge MUST have a predecessor-bound amendment record. The kernel MUST expose
the contraction as a typed diff.

### 5.2 Obligation carry-forward

\[
Open(\mathcal O_t)
\subseteq
\mathcal O_{t+1} \cup AuthorizedDischarge_t
\]

Every open obligation MUST be preserved or discharged by an authorized beneficiary, arbiter, or
rule named by the predecessor charter. Assigning no bearer is an orphaning violation.

### 5.3 Predecessor ratification

Authority evidence for an amendment MUST bind the predecessor charter digest, proposed successor
digest, exact diff, and ledger root. Evidence issued only under the successor is invalid.
Removing a predecessor principal or changing its trust domain or adapter MUST also require a
release produced by that predecessor identity through the predecessor adapter. Reusing the same
identifier does not preserve authority when its trust boundary changed.

### 5.4 Coverage before optimization

Every known boundary-crossing effect MUST map to a horizon, observer, evidence contract, and
standing-resolution rule. `Unknown` and `uncovered` are first-class results and MUST NOT be
converted to zero, false, or an average score.

### 5.5 Reserved recourse

A remediable obligation MUST name and verify a feasible remedy path. A declaration without an
available executor, authority, resource reservation, or bounded completion condition is not
recourse.

### 5.6 Non-compensation

Hard obligations are conjunctive. A benefit in one horizon MUST NOT compensate for a hard breach in
another. Soft observations remain a vector unless the charter contains an authorized aggregation
rule, units, and provenance.

### 5.7 Separation of actor, observer, and amender

The host MUST enforce declared independence constraints between candidate, effect executor,
horizon evaluator, evidence verifier, recourse authority, and charter amender. A digest identifies
code; it does not make same-process code independent.

## 6. Admission semantics

For a proposal `m`, each horizon evaluator returns typed findings from a bound evidence set. A
finding has one of four states:

```text
satisfied | violated | unknown | uncovered
```

The normative decision is:

```text
DENY
  if a known hard obligation is violated,
  or authority is invalid,
  or an open obligation is orphaned,
  or an amendment is self-ratifying,
  or required recourse is known to be infeasible.

ESCALATE
  if a required finding is unknown or uncovered,
  or affected-party standing is unresolved,
  or evidence is stale or unverifiable,
  or plural obligations conflict without an authorized ordering rule.

ALLOW
  only if all required horizons are covered,
  all hard obligations are satisfied,
  all amendments are predecessor-authorized,
  and relied-upon recourse is executable.
```

`ESCALATE` is epistemic, not a softer denial. The host MAY resume the same bound proposal with new
evidence or authority. It MUST NOT silently create a new proposal merely to reset evidence budgets.

## 7. Pure transition protocol

The reference kernel is effect-free. It implements:

```text
step(state, event) -> transition

transition:
  next_state
  effect_requests[]
  outcome?
```

An effect request MUST contain a stable kind, request identifier, session identifier, monotonic
sequence, active charter and proposal digests, provider identity, allowed producer set, logical
group, expiry, and canonical payload. The request digest binds that complete material. It MUST NOT
contain ambient authority.

The host executes the effect and returns an effect receipt. A receipt MUST bind the exact request,
producer, four-state status, external result digest, evidence digest, and issue time. A deployment
MAY require an implementation digest or signature inside the externally bound result or evidence
contract. A receipt for a different session, sequence, request, charter, proposal, producer, or
payload MUST be rejected.

Optional `EffectReceipt.details` is diagnostic and non-normative. The reference implementation
serializes it for inspection but excludes it from receipt semantic material and the session-state
digest. A decision-bearing result MUST be retained externally and bound by `result_digest`; its
supporting evidence MUST be bound by `evidence_digest`.

The kernel MUST reach the same hard decision for the same initial state, ordered input events, and
explicit host-supplied time values. Randomness, network responses, identity assertions, and policy
decisions are external observations and therefore enter through bound receipts rather than ambient
kernel access.

## 8. Interfaces and portability

A conforming implementation MUST expose at least one deterministic in-process interface. The
reference symbols are `PureKernel`, `Engine`, and `SessionStore`; the portable domain values are
`Charter`, `Proposal`, `EffectRequest`, and `EffectReceipt`. A wire implementation MUST use a
versioned envelope and MUST preserve the same event semantics.

The reference wire surface is `polyhorizon.wire/v0.1`, newline-delimited JSON with
`capabilities`, `open`, `advance`, `inspect`, and `abort` commands. Transport framing is not
authorization. HTTP, MCP, A2A, queues, or CI systems MAY carry the envelopes through adapters, but
MUST NOT alter the normative binding or decision semantics.

The reference v0.1 codec rejects unknown envelope and command-payload fields. Future compatible
features require explicit capability negotiation or a new protocol version. Unknown required
features and unsupported protocol versions MUST fail closed.

Semantic digests use the `polyhorizon.engine.v1` canonical profile. Canonical material is limited
to JSON null, booleans, Unicode-scalar strings, arrays, objects with string keys, and integers in
the inclusive range `[-9007199254740991, 9007199254740991]`. Floating-point values, surrogate
code points, sets, binary values, and non-string object keys MUST be rejected. Strings are not
Unicode-normalized. Object keys are ordered by their UTF-8 byte sequence; arrays preserve order.
Serialization uses UTF-8, no insignificant whitespace, and the shortest mandatory JSON escapes:
quotes, reverse solidus, and control characters are escaped, while other scalar values remain
unescaped. Parsed timestamps MUST match `YYYY-MM-DDTHH:MM:SS[.ffffff](Z|+HH:MM|-HH:MM)` and are
canonicalized to UTC with uppercase `Z`.

Domain digests are SHA-256 over
`b"polyhorizon.engine.v1\\x00" + ascii(domain) + b"\\x00" + utf8(canonical_json)` and are
rendered as `sha256:<lowercase hex>`. This profile is deliberately narrower than generic JSON and
does not claim RFC 8785/JCS conformance. The published digest corpus is normative for v0.1 ports.

## 9. Conformance boundary

A conforming deployment MUST demonstrate:

1. deterministic transition test vectors;
2. rejection of cross-request, cross-session, cross-candidate, and cross-charter receipt replay;
3. no silent horizon contraction;
4. obligation carry-forward and authorized discharge;
5. predecessor-ratified amendment;
6. `unknown` and `uncovered` preservation;
7. recourse fault injection;
8. backend-equivalent hard decisions; and
9. a public statement of trusted components and unmodeled dynamics.

An implementation that merely runs several evaluators, averages their scores, or adds a longer
retry loop is not Polyhorizon-conforming.

## 10. Limits and withdrawal condition

Every claim is conditional on the declared horizons, effect graph, adapters, evidence, identities,
and enforcement boundary. Polyhorizon cannot prove moral legitimacy, complete causal coverage,
forecast accuracy, or incorruptible institutions.

The method should be collapsed into a Viability or Forge policy library if controlled experiments
show no incremental protection against horizon contraction, claimant deletion, obligation
orphaning, self-ratification, or claimant-specific recourse failure at acceptable operational cost.
