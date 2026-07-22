# Polyhorizon Engineering

**Engineer what a self-changing system is not allowed to stop seeing.**

Polyhorizon Engineering is an engineering discipline for plural consequence horizons around
evolving agent systems. It makes purposes, affected-party standing, obligations, authority,
evidence boundaries, and recourse explicit and versioned. It then governs how those objects may
change while a Loop or Forge changes the system beneath them.

The core failure it addresses is **endogenous horizon collapse (EHC)**: a system can appear to improve by
shortening the period it evaluates, moving effects outside its causal scope, removing an affected
party, deleting the metric that represented an obligation, weakening the evidence contract, or
using a new rule to approve that same rule.

> Forge asks whether the system can become better. Polyhorizon asks: better for whom, over which
> consequences, for how long, and under whose authority to revise those answers?

## Position in the engineering stack

This is a hierarchy of controlled objects, not a claim about the order in which labels were
published.

| Discipline | Primary controlled object | Characteristic question |
|---|---|---|
| Prompt Engineering | instruction | What should the model be told? |
| Context Engineering | decision information | What should be made available now? |
| Harness Engineering | one execution system | How may one run act, observe, and recover? |
| Loop Engineering | repeated trajectory | How are runs triggered, checked, remembered, and stopped? |
| Forge Engineering | evolution operator | How should harness or loop policy change from evidence? |
| Polyhorizon Engineering | constitution of consequence boundaries | What must remain visible and owed while those policies change? |

[Jinsoo Kim's first public Forge Engineering commit](https://github.com/jinsoo96/forge-engineering/commit/4d33c53e6b1d76a86b75e8115d2ae8e00304bdaf)
is dated 2026-04-24. [Addy Osmani's explicit Loop Engineering formulation](https://addyosmani.com/blog/loop-engineering/)
is dated 2026-06-07. `Harness -> Loop -> Forge -> Polyhorizon` is therefore useful as a
control-object decomposition, not as a publication chronology.

## What makes this more than Viability renamed

Viability theory studies whether at least one evolution can remain inside a declared constraint
set. A viability gate can answer whether a candidate remains inside an already declared envelope.
Polyhorizon governs the constitution of that envelope:

- which temporal, causal, stakeholder, authority, and epistemic horizons exist;
- who has standing to observe, contest, consent, discharge, or appeal;
- which obligations survive metric, evaluator, owner, and policy changes;
- whether recourse is executable for the party to whom it is owed; and
- which predecessor rule may authorize a change to those terms.

An augmented viability model can represent these variables. The claim here is not new control
mathematics. It is an engineering boundary: these variables are protected, versioned, portable,
and controlled by a trust domain distinct from the Forge that proposes improvements.

If a Polyhorizon charter can be compiled losslessly into an ordinary Forge or viability policy
without protected cross-version state, this project has not earned a separate name. The
[falsification protocol](docs/falsification.md) makes that a direct rejection condition.

## Five standard axes, an open type system

The standard profile recognizes five common axes:

1. **Temporal** — immediate, delayed, and intergenerational effects.
2. **Causal** — direct outputs, downstream dependencies, and externalities.
3. **Standing** — principals, users, third parties, and affected communities.
4. **Authority** — delegation, approval, amendment, and expiry boundaries.
5. **Epistemic** — observations, provenance, uncertainty, and known coverage gaps.

These are not a closed enum in the kernel. Horizon kinds are namespaced extension points with
versioned schemas and evaluators. A medical deployment, an infrastructure controller, and a code
agent should be able to define domain horizons without patching core logic.

## Engine shape

The reference design is a pure transition kernel:

```text
step(session_state, input_event)
    -> next_state + effect_requests + optional_outcome
```

The kernel never performs network, filesystem, identity, policy, clock, or model effects directly.
The host executes a requested effect and returns a receipt bound to the session, sequence,
request, charter, and candidate. The next step accepts only the matching receipt.

```text
host discovery + artifact binding
   -> proposal with declared and independently discovered claims
   -> standing / evidence / authority / recourse requests
   <- bound receipts
   -> ALLOW | DENY | ESCALATE
```

This separation provides two equivalent attachment surfaces:

- an in-process Python interface; and
- a versioned NDJSON protocol suitable for a subprocess, sidecar, CI gate, or non-Python host.

The protocol is asynchronous in shape even when an in-process host completes effects immediately.
See [architecture](docs/architecture.md), [integration](docs/integration.md), and the
[wire protocol](docs/wire-protocol.md).

## Use it as an engine

```bash
python -m pip install polyhorizon-engineering
polyhorizon capabilities
```

The public Python surface centers on `Charter`, `Proposal`, `PureKernel`, `Engine`,
`SessionStore`, `EffectRequest`, and `EffectReceipt`. `Engine` can use the bundled in-memory or
local-file store, or any compare-and-swap store supplied by the host. The same session semantics are
available through `polyhorizon.wire/v0.1` with `capabilities`, `open`, `advance`, `inspect`, and
`abort` commands.

The engine is deliberately attachable rather than vendor-aware. A Python application can register
in-process effect handlers; another language can run it as a subprocess or sidecar; CI can use the
CLI; and HTTP, MCP, A2A, policy engines, identity systems, or queues can connect through host
adapters. Those transports and systems do not become authority merely by being connected.

Runnable [Python and Node sidecar examples](examples/README.md), JSON Schemas, and a canonical
digest corpus are included so an integration can start from executable artifacts rather than prose
alone.

`EffectReceipt.details` is non-normative diagnostic metadata even when it appears in serialized
session state. The exact external result used by an adapter is bound by `result_digest`, and its
supporting evidence by `evidence_digest`. See the [integration contract](docs/integration.md#4-effect-execution-contract).

## Normative decision semantics

Polyhorizon does not produce a universal goodness score.

- A known hard obligation breach, unauthorized change, self-ratifying amendment, or orphaned open
  obligation is `DENY`.
- An uncovered consequence, unresolved affected party, stale evidence, or conflict without an
  authorized ordering rule is `ESCALATE`.
- A proposal is `ALLOW` only when all required horizons are covered, hard obligations hold,
  amendments are predecessor-authorized, and any claimed recourse is reserved and executable.

Soft outcomes remain a vector. Scalar aggregation is permitted only when the charter explicitly
authorizes the aggregation rule; it can never erase a hard obligation.

## Repository map

```text
POLYHORIZON.md             normative method
docs/philosophy.md         stewardship claims and limits
docs/theory.md             formal model and failure definitions
docs/research.md           primary-source lineage and non-novel mechanisms
docs/falsification.md      baselines, attacks, measures, rejection conditions
docs/threat-model.md       trust boundaries and adversary model
docs/architecture.md       pure kernel, state, effects, receipts, extensions
docs/integration.md        embedding and host responsibilities
docs/wire-protocol.md      versioned NDJSON contract
examples/                  Python and Node attachment examples plus digest corpus
schemas/                   strict alpha manifest and wire schemas
ROADMAP.md                 evidence-driven milestones
CHANGELOG.md               public release history and known limits
```

## Status and claim discipline

This repository is an alpha reference implementation and a falsifiable method proposal. It is not
a moral oracle, regulator, identity provider, causal-discovery system, or guarantee against unknown
unknowns. Authorization proves a declared procedure was followed; it does not prove that the
procedure is just. The genesis charter and its root authorities remain external human or
institutional choices.

The v0.1 kernel implements predecessor-sourced ratification and manifest-level discharge requests
for changed or removed obligations. It does not yet provide a durable cross-session obligation
ledger, an in-kernel impact-discovery phase, semantic migration proofs, an independent interpreter,
or a distributed transaction with external effects. Hosts must bind independently discovered
claims before `open`; the kernel cannot detect an effect omitted from every input. Those are
explicit [roadmap](ROADMAP.md) gates, not implied capabilities.

The phrase `polyhorizon engineering` had no obvious exact-match AI-agent discipline collision in
the scoped search performed for this release. That is not a trademark opinion, exhaustive
prior-art search, or priority claim. Multiple planning horizons, viability theory, constitutional
AI, participatory governance, policy-as-code, algorithmic recourse, and dynamic assurance cases all
predate this work and are explicitly reused or distinguished in [the research review](docs/research.md).

## License

MIT.
