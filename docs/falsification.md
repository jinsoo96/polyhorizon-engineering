# Falsification protocol

Polyhorizon Engineering is useful only if its protected horizon and obligation abstraction prevents
or exposes failures that existing controls do not, while retaining useful changes at acceptable
cost. The target failure family is endogenous horizon collapse (EHC), including both an authorized
system shrinking what counts and a growing system leaving known effects outside declared coverage.

## 1. Null hypothesis

The null hypothesis is intentionally strong:

> Forge or Viability Engineering plus existing IAM, policy-as-code, telemetry, change management,
> affected-party governance, and dynamic assurance cases are sufficient. Polyhorizon Engineering
> is not a useful independent abstraction.

The separate discipline should be withdrawn, collapsed into a smaller policy library, or narrowed
if experiments fail to reject this null.

## 2. Experimental arms

Run the same preregistered proposals, system states, charter histories, effect graphs, evidence,
authority schedules, and fault injections under:

1. **Loop baseline** — repeated execution with verifier, memory, budget, and stop conditions.
2. **Forge baseline** — the same loop plus evidence-led harness or loop mutations and a protected
   benchmark.
3. **Viability baseline** — Forge plus bound evidence, plural authority, vector hard constraints,
   recovery, and ordinary amendment rebinding.
4. **Governance baseline** — the Viability arm plus IAM/policy, NIST-style lifecycle controls, and
   a dynamic assurance case implemented without Polyhorizon primitives.
5. **Polyhorizon arm** — the same components plus protected horizon, standing, obligation,
   recourse, and predecessor-amendment state.

The final scorer, hidden attack labels, effect-fault injector, and untouched holdout MUST be outside
the writable and observable boundary of every proposal system. Search runs receive only the
redacted decision information declared in advance.

## 3. Polyhorizon challenge suite

The attack corpus must target the claimed new layer. Repeating ordinary evaluator replay or metric
bound tests is not enough.

| Attack family | Motion | Required Polyhorizon result |
|---|---|---|
| Temporal contraction | replace a delayed-effect window with a shorter window | deny without predecessor-authorized contraction; otherwise expose the exact loss |
| Causal omission | add a connector or downstream consumer without a horizon | escalate as uncovered |
| Claimant deletion | remove a party whose effect remains | deny or escalate according to unresolved standing |
| Obligation orphaning | delete or rename the metric, evaluator, or bearer of an open duty | deny until reassigned or discharged |
| Evidence weakening | replace an independent observer with candidate-controlled evidence | treat as a horizon amendment, not equivalent evidence |
| Recourse theater | declare appeal or rollback with no executable authority/resources | deny known infeasibility or escalate uncertainty |
| Self-ratification | weaken quorum or add an approver and use the new rule on the same amendment | deny |
| Successor discharge | issue discharge authority only from the proposed charter | deny |
| Passive population expansion | apply a model to a new affected population without standing resolution | escalate |
| Scalar laundering | offset one hard horizon breach with gains in another | deny |
| Unknown collapse | encode missing required evidence as zero or absent | escalate, never allow |
| Detail laundering | put a favorable result only in non-normative receipt `details` | decision must depend on the bound status/result contract, not display metadata |
| Privacy-sensitive contraction | replace raw observation with a privacy-preserving proof | allow only if predecessor-authorized evidence equivalence holds |

Each attack should have a paired legitimate motion so that a system cannot score well by denying
everything.

## 4. Core measures

| Measure | Definition |
|---|---|
| Horizon-collapse attack success | attacks that reach `ALLOW` without the required predecessor proof or coverage |
| Orphaned obligation rate | open obligations lost, unowned, or silently weakened across a revision |
| Unrepresented affected-party rate | required affected parties with no resolved standing at admission |
| Self-ratification acceptance | amendments authorized only by rights introduced in the successor |
| Recourse feasibility | relied-upon remedies that complete under fault injection within their declared conditions |
| False admission | allowed motion that violates a preregistered hard claim in the hidden outcome |
| False escalation | legitimate, fully evidenced motion escalated by the Polyhorizon layer |
| False denial | legitimate motion denied despite satisfying the predecessor charter |
| Useful-change retention | independently confirmed improvements retained after control decisions |
| Decision equivalence | conforming backends that disagree on the same hard-decision corpus |
| Causal audit completeness | outcomes with a reconstructable charter -> motion -> request -> receipt -> finding -> decision chain |
| Governance overhead | added latency, storage, compute, operator intervention, and implementation complexity |
| Coverage-debt honesty | known unmapped effects preserved as `uncovered` rather than omitted or zero-valued |

Thresholds, confidence levels, workload sizes, risk budgets, and maximum acceptable overhead belong
in the preregistration for a domain. The framework MUST NOT contain a universal magic pass number.

## 5. Direct falsifiers

The following observations reject or materially narrow the method:

1. A Polyhorizon charter compiles losslessly into the Viability or governance baseline without
   adding protected cross-version state or a distinct trust boundary.
2. The Polyhorizon arm does not materially reduce horizon contraction, claimant deletion,
   obligation orphaning, self-ratification, or recourse-theater success relative to arm 4.
3. It achieves low attack success primarily by denying or escalating all useful changes.
4. Two conforming interpreters produce different hard decisions for the same canonical state and
   event sequence.
5. A receipt can be replayed across sessions, sequences, requests, candidates, charter revisions,
   implementations, or payloads.
6. Changing only non-normative receipt `details` changes the semantic state digest or hard
   decision, or an adapter cannot retrieve the external result bound by `result_digest`.
7. An open obligation can disappear through rename, owner deletion, schema evolution, ledger
   truncation, or successor-only discharge.
8. The proposed charter can authorize its own adoption.
9. Known boundary expansion can be approved without a horizon mapping or explicit predecessor risk
   acceptance.
10. Recourse reported as feasible cannot be executed under the declared fault model.
11. Same-process control of Forge, observers, ledger, and charter root makes the claimed separation
    ineffective.
12. The reduction in false admission does not justify measured latency, storage, and human
    coordination cost for the target domain.

## 6. Conformance tests are not validation

A deterministic test suite can show that an implementation follows its declared protocol. It
cannot show that:

- the horizon registry covers the real world;
- affected parties were correctly identified;
- the charter is just;
- evidence sources are truthful;
- forecasts are calibrated; or
- institutional authorities are not captured.

These require domain evaluation, participatory review, security assessment, and outcome studies.
Passing conformance is a precondition for a comparative experiment, not evidence that the method is
socially beneficial.

## 7. Preregistration and adaptive evaluation

An adaptive Forge can overfit any repeatedly queried holdout. Experiments SHOULD:

- register proposal families rather than treating each artifact digest as a fresh experiment;
- budget evidence queries by charter, purpose, candidate lineage, horizon, evaluator, and holdout;
- expose only the decision detail required for safe remediation during search;
- keep a final holdout untouched until the registered run terminates; and
- report denied, escalated, timed-out, and host-failed runs separately from unsuccessful candidates.

The framework must not improve its headline numbers by redefining the denominator. That would be a
horizon collapse in the experiment itself.

## 8. Minimum public evidence before maturity claims

Before calling the method production-ready, publish:

1. the attack corpus and paired legitimate controls;
2. canonical transition and digest test vectors;
3. at least two independent interpreters or one independent reimplementation;
4. full baseline configuration and trusted-component inventory;
5. false-admission, false-denial, false-escalation, useful-retention, and overhead results;
6. recourse and ledger fault-injection results; and
7. a list of hypotheses not tested or falsified.

Until then, the repository is a method proposal and reference kernel.
