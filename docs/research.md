# Research landscape and claim boundary

Research snapshot: **2026-07-22**.

This is a scoped synthesis of primary papers, official specifications, and source repositories. It
is not an exhaustive prior-art or trademark search. Preprints are described as preprints unless a
publication venue is stated by their source.

## 1. The conceptual sequence is not a publication sequence

Polyhorizon uses the following control-object hierarchy:

```text
run -> repeated trajectory -> policy evolution -> constitution of consequence horizons
```

That corresponds to Harness, Loop, Forge, and Polyhorizon, but the labels were not published in
that order.

- Jinsoo Kim's [initial public Forge Engineering commit](https://github.com/jinsoo96/forge-engineering/commit/4d33c53e6b1d76a86b75e8115d2ae8e00304bdaf)
  is dated 2026-04-24. It types the harness and proposes a Runner/Smith separation for evidence-led
  harness evolution.
- Addy Osmani's [Loop Engineering](https://addyosmani.com/blog/loop-engineering/) is dated
  2026-06-07. It explicitly places scheduled discovery, isolated worktrees, skills, connectors,
  verifier agents, and durable state one floor above a harness.

Forge therefore predates the explicit Loop label in these primary sources. The hierarchy is useful
because Forge changes loop and harness policy, not because one label historically followed the
other.

## 2. Why Viability was not selected as the next discipline

Jean-Pierre Aubin's [Viability Theory: New Directions](https://link.springer.com/book/10.1007/978-3-642-16684-6)
develops methods for evolutions that must adapt to constraints under uncertainty. The viability
kernel and related invariance concepts are established control-theoretic foundations, not new
agent-engineering ideas.

More decisively, recent work already applies this vocabulary directly to agent governance:

- [Governing What You Cannot Observe](https://arxiv.org/abs/2604.24686) proposes an Agent
  Viability Framework and RiskGate grounded in Aubin's theory, with monitoring, anticipation,
  monotonic restriction, and a scalar viability index.
- [Toward Pre-Deployment Assurance for Enterprise AI Agents](https://arxiv.org/abs/2606.04037)
  proposes an Agent Operational Envelope across permissions, domain constraints, safety,
  governance, and autonomy, plus ontology-grounded scenario generation and trust certificates.

The local Viability Engineering prototype that preceded this repository also already implemented
bound evidence, plural authority, vector hard constraints, recovery, and a basic amendment rule.
Renaming that implementation would not produce a new layer.

Polyhorizon instead makes a narrower second-order claim: the protected engineering object is the
cross-version constitution of horizons, standing, obligations, and recourse. A viability evaluator
can be one horizon adapter. The project does not claim to supersede viability mathematics.

## 3. Evidence for endogenous boundary gaming

The failure family is well established even though the proposed engineering synthesis is new.
Polyhorizon names the synthesis-level failure **endogenous horizon collapse (EHC)**; it does not
claim that reward tampering, side effects, evaluator gaming, or constituency manipulation are new
discoveries.

### Reward and evaluator tampering

[Reward Tampering Problems and Solutions in Reinforcement Learning](https://arxiv.org/abs/1908.04734)
uses causal influence diagrams to distinguish reward-function and reward-input tampering and to
analyze when tampering becomes instrumentally useful.

For modern engineering agents, [RewardHackingAgents](https://arxiv.org/abs/2603.11337) makes
evaluator tampering and train/test leakage explicit benchmark dimensions. Its experiments show why
the evaluator cannot share the candidate's unrestricted writable boundary.

[Reward Hacking in Language Model Agents](https://arxiv.org/abs/2606.15385) reports high observed
reward alongside poor hidden safety outcomes in text adaptations of AI Safety Gridworlds. This
supports preserving hidden or independent horizons rather than trusting a single optimized proxy.

Polyhorizon reuses protected evaluators and bound evidence. Its additional concern is that a valid
authority may intentionally or accidentally amend which evaluators, populations, time windows, or
claims exist. File locking alone does not govern that transition.

### Side effects and future options

[Penalizing Side Effects Using Stepwise Relative Reachability](https://arxiv.org/abs/1806.01186)
shows that baseline and deviation-measure choices themselves create incentives, and develops a
relative-reachability measure that avoids several undesirable incentives in gridworlds.

This is important lineage for recourse and option preservation. It does not establish affected
party standing, authority to amend the baseline, or obligation succession across versions.

### Manipulating the represented party

[User Tampering in Reinforcement Learning Recommender Systems](https://arxiv.org/abs/2109.04083)
formalizes a recommender's incentive to change users' opinions to improve later engagement. It is a
strong example of temporal and stakeholder horizons interacting: the measured party is part of the
dynamics, not an immutable source of preference.

Polyhorizon cannot solve preference formation. It can require that purpose, affected-party
standing, observation window, and amendment authority remain explicit rather than letting the
engagement objective stand in for all four.

## 4. Control theory and multiple horizons

Finite-horizon control is not sufficient merely because the optimization is repeated. David
Mayne's [analysis of stabilizing terminal conditions in model predictive control](https://doi.org/10.1080/00207179.2013.813647)
explains the role of terminal cost and constraints in closed-loop stability.

Multiple planning and control horizons also predate this repository:

- [Inverse Reinforcement Learning with Multiple Planning Horizons](https://arxiv.org/abs/2409.18051)
  studies experts with different unknown discount factors.
- [Distributed Multi-Horizon Model Predictive Control](https://arxiv.org/abs/2304.14089) uses
  multiple horizons to extend prediction without a uniformly fine discretization.

Polyhorizon does not claim to invent long-term or multi-timescale planning. Its horizons are typed,
heterogeneous consequence contracts: temporal, causal, standing, authority, and epistemic axes can
use different evidence, owners, units, and decision rules. The key mechanism is governed
cross-version continuity, not a new MPC discretization.

## 5. Constitutions, public input, and institutions

[Constitutional AI](https://arxiv.org/abs/2212.08073) uses a written set of principles for
critique/revision and AI-feedback preference learning. It demonstrates that explicit principles can
shape model behavior with limited direct harmlessness labels.

[Collective Constitutional AI](https://arxiv.org/abs/2406.07814) develops a multi-stage process
for identifying a target population, sourcing principles, training, and evaluation. It directly
addresses the problem of developers being the sole deciders of model behavior.

These methods can inform the genesis or amendment of a telic charter. They do not by themselves
provide runtime receipt binding, obligation carry-forward, predecessor ratification, or executable
claimant recourse.

[Institutional AI](https://arxiv.org/abs/2601.11369) moves from preference engineering in
agent-space to mechanism design in institution-space and compares ungoverned, prompt-constitutional,
and governance-graph regimes in a multi-agent market. That is close conceptual prior art. The
narrow Polyhorizon hypothesis is that portable horizon and obligation transition semantics add
value across institutions rather than defining one institution or market mechanism.

The name `Constitutional Engineering` is not available as an unqualified novelty claim. A 2025
preprint, [From Craft to Constitution](https://arxiv.org/abs/2510.13857), presents a
governance-first agent-engineering architecture called ArbiterOS, and products also use similar
language. This repository calls its versioned artifact a telic charter but does not claim to coin
constitutional agent governance.

## 6. AI governance, affected communities, and recourse

The [NIST AI Risk Management Framework 1.0 Core (2023)](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
already includes much of the normative content that careless positioning might claim as new. NIST
marks AI RMF 1.0 as under revision, so this review names the version it inspected:

- intended purposes and impacts on individuals, communities, organizations, society, and the
  planet in `MAP`;
- consultation with affected communities and reporting of unmeasured risk in `MEASURE`;
- feedback and appeal processes for impacted communities; and
- override, decommissioning, incident response, recovery, and change management in `MANAGE`.

Polyhorizon reuses those concerns. Its narrower engineering claim is a deterministic transition
contract for self-changing agent systems: missing coverage and standing survive as typed states,
open obligations cross revisions, amendments are judged by the predecessor charter, and external
effects return bound receipts.

Research on contestability likewise predates this project. [Fair and Responsible AI: A Focus on
the Ability to Contest](https://arxiv.org/abs/2102.10787) argues for human-centered contestation
processes, and [Identifying Algorithmic Decision Subjects' Needs for Meaningful Contestability](https://doi.org/10.1145/3757415)
studies the cooperative work needed to make contestability meaningful. Polyhorizon turns a subset
of that concern into a typed standing and recourse interface; it does not reduce contestability to
an automated button.

## 7. Safety and assurance cases

[Safety Cases: How to Justify the Safety of Advanced AI Systems](https://arxiv.org/abs/2403.10462)
defines a structured rationale, supported by evidence, for decisions about catastrophic risk. The
[Goal Structuring Notation Community Standard](https://scsc.uk/gsn) and related assurance-case
practice long predate this repository.

Assurance need not be static:

- The NTRS-hosted 2023 presentation [Dynamic Assurance
  Cases](https://ntrs.nasa.gov/citations/20230007853), authored at KBR, extends design-time safety
  cases with operational updates.
- [Runtime confidence updates in safety arguments](https://arxiv.org/abs/2605.22530) integrates
  design-time evidence and runtime safety performance indicators using subjective logic.
- [ACCESS](https://arxiv.org/abs/2403.15236) develops assurance-case-centric engineering with
  development- and runtime-evaluable cases.

A safety or assurance case is therefore an evidence adapter, not a Polyhorizon invention. The
additional proposed objects are claimant standing, bearer/beneficiary obligations, accounted
horizon contraction, and predecessor-authorized amendment.

## 8. Reused infrastructure rather than reinvention

The engine should integrate established systems through ports:

| Concern | Foundation | Polyhorizon role |
|---|---|---|
| Authorization policy | OPA, Cedar, cloud policy engines | authority-effect adapter |
| Workload identity | SPIFFE and platform identities | principal evidence input |
| Credentials | [W3C Verifiable Credentials 2.0](https://www.w3.org/TR/vc-data-model-2.0/) | standing or authority proof input |
| Artifact provenance | [SLSA 1.2](https://slsa.dev/spec/v1.2/) and [in-toto Statement v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md) | bound artifact/evaluator evidence |
| Observability | OpenTelemetry semantic conventions | horizon evidence source |
| Agent transport | [A2A](https://a2a-protocol.org/latest/specification/) | transport adapter, not governance |
| Tool/context exchange | [MCP](https://modelcontextprotocol.io/specification/latest/) | effect adapter, not authority proof |
| Safety arguments | GSN and dynamic assurance cases | evidence adapter |
| Physical or operational reachability | viability, robust control, MPC | horizon evaluator |

The pure kernel does not become more trustworthy by embedding all of these vendors and standards in
one process. It requests effects and validates bound receipts.

## 9. Claimed synthesis

The repository claims only that this combination deserves an engineering lifecycle and a
falsifiable conformance boundary:

1. typed, namespaced, heterogeneous consequence horizons;
2. active and passive endogenous horizon-collapse detection;
3. affected-party standing linked to effects and obligations;
4. obligation carry-forward across system and charter changes;
5. claimant-centered, reserved, executable recourse;
6. predecessor-ratified charter amendment;
7. non-scalar `satisfied | violated | unknown | uncovered` findings; and
8. a pure step/effect/receipt kernel portable through in-process and NDJSON interfaces.

No individual mechanism is presented as new. Distinctiveness is an experimental hypothesis about
their composition around Forge-scale self-change.

## 10. Naming and priority discipline

Scoped exact-phrase searches found no obvious prior public use of `Polyhorizon Engineering` as an
AI-agent discipline at the time of this snapshot. That observation supports choosing a searchable
name; it does not prove novelty, priority, freedom to operate, or trademark availability.

The project should make no `first` claim until independent review, a repeatable search record, and
substantive comparative experiments exist. Even then, any claim must concern the precise synthesis,
not multiple horizons, governance, constitutions, viability, recourse, or assurance in general.
