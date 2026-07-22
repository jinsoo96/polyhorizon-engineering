# Theory: horizons as protected, amendable observation contracts

This document gives a falsifiable formal model for Polyhorizon Engineering. It does not claim a new
branch of control theory. Viability kernels, robust control, model predictive control,
multi-objective optimization, policy-as-code, assurance cases, and constitutional governance
provide substantial prior foundations.

The proposed contribution is an engineering abstraction for a particular second-order problem:
an adaptive system can change the boundary and constituency under which its adaptation is judged.
The primary sources and adjacent mechanisms are catalogued in the
[research review](research.md); no individual control, governance, or recourse mechanism is claimed
as new.

## 1. System and charter state

Let the governed configuration be:

\[
k_t = (H_t,L_t,F_t)
\]

where `H` is the execution harness, `L` the repeated trajectory policy, and `F` the operator that
proposes changes from evidence. A motion may change ordinary system state, `k`, or the charter
itself.

Let the world state be `x_t`, and let the protected telic charter be:

\[
\Theta_t=(P_t,\mathcal H_t,\mathcal O_t,\mathcal S_t,
\mathcal A_t,\mathcal R_t,\mu_t)
\]

The full modeled state is:

\[
z_t=(x_t,k_t,\Theta_t,\Lambda_t)
\]

where `Lambda` is an append-only event and obligation ledger. A transition proposal `m` contains an
exact base revision and candidate digest. It does not carry ambient authority.

The v0.1 reference implementation projects `Theta` into `Charter`, `m` into `Proposal`, and the
ordered request/receipt trace into `SessionState`. It checks manifest-level carry-forward by
requesting predecessor-beneficiary discharge for each changed or removed obligation. It does not
yet implement the durable cross-session `Lambda` assumed by the full model; that is a stated alpha
limit rather than an implicit guarantee.

## 2. Horizon model

A horizon is:

\[
h=(q,s,\pi,\tau,W,e)
\]

- `q` is a namespaced kind and version;
- `s` is a declared scope;
- `pi` is an observation projection;
- `tau` is a time interval or review cadence;
- `W` is an uncertainty or disturbance model; and
- `e` is an evidence contract.

An evaluator returns a conservative set of possible observations or postconditions:

\[
Post_h(x_t,m,W_h)\subseteq Y_h
\]

`Post` may be produced by a simulator, theorem prover, policy engine, test suite, human review,
assurance case, monitoring system, or composite. The kernel knows only the typed receipt and its
binding. It does not assume every evaluator returns a scalar.

The standard profile uses temporal, causal, standing, authority, and epistemic axes. These are
heterogeneous governance dimensions, not the multiple discretization horizons of multi-horizon
MPC. Deployments can add a privacy, ecological, legal, financial, or domain-specific horizon
without changing the core decision algebra.

## 3. Relative coverage

Let `G_m` be the registered effect and dependency graph for a motion, and let
`BoundaryEdges(G_m)` be edges that cross the currently governed boundary. Coverage is:

\[
Covered_{\Theta}(m)
\iff
\forall d\in BoundaryEdges(G_m),
\exists h\in\mathcal H:
observes(h,d)\land owner(h)\land fresh(e_h)
\]

If the charter requires standing resolution, coverage also requires:

\[
Affected(d)\subseteq
\{p\mid represented_{\mathcal S}(p,d)\}
\]

This definition is relative to `G_m`, its discovery adapters, and the accuracy of `Affected`. It is
not ontological completeness. A known edge with no mapping is `uncovered`; an edge whose relevant
state cannot be determined is `unknown`. Both remain distinct from a satisfied predicate.

## 4. Obligations and recourse

An obligation is:

\[
o=(h,b,c,\phi_o,mode,d,r)
\]

where `b` is the bearer, `c` the beneficiary or claimant, `phi` the predicate, `d` the deadline,
and `r` the recourse plan.

For a non-compensable obligation:

\[
Sat_o(m)
\iff
\forall y\in Post_{h(o)}(x_t,m,W_h),\;\phi_o(y)
\]

For a remediable obligation, a temporary violation can count as admissible only when an authorized
and reserved recourse path reaches the required terminal within the deadline:

\[
Sat_o(m)
\iff
\forall y\in Post_{h(o)}(x_t,m,W_h),
\phi_o(y)\lor
\left[Reserved(r_o)\land
Reach(y,r_o,Safe_o)\le d_o\right]
\]

This is conditional on the fidelity of the reachability evidence and the host honoring the
reservation. A nominal `rollback` string does not satisfy the predicate.

These equations distinguish semantic remediability from decision severity. In the reference API,
`ObligationMode` is `hard`, `review`, or `advisory`; proposal `Reversibility` and linked
`Recourse` carry the remediation claim.

Open obligations persist:

\[
Open(\mathcal O_t)
\subseteq
\mathcal O_{t+1}\cup Discharged_t
\]

and every discharge must be valid under `Theta_t`. A change that removes the bearer without
reassignment or discharge is an orphaning violation.

## 5. Endogenous horizon collapse

### 5.1 Active collapse

Let `Obs_Theta(m)` denote the consequence claims that a charter requires for motion `m`. An active
horizon contraction occurs when:

\[
Obs_{\Theta_{t+1}}(m)\subset Obs_{\Theta_t}(m)
\]

The contraction becomes **endogenous horizon collapse (EHC)** when it lacks predecessor-authorized
discharge, substitution, or contraction evidence and contributes to the candidate's apparent
acceptability.

Examples include:

- shortening a 180-day delayed-effect horizon to 30 days;
- dropping a downstream consumer from the causal graph;
- deleting standing for a class that bears the effect;
- removing an open obligation by removing its metric;
- replacing an independent evidence source with a candidate-controlled source; or
- deleting an appeal or exit edge.

### 5.2 Passive collapse

A passive collapse occurs when the system expands without expanding declared coverage:

\[
Footprint(k_{t+1})\nsubseteq Coverage(\mathcal H_{t+1})
\]

Examples include a new tool, connector, data flow, customer population, or downstream automated
decision. A conforming engine escalates a known uncovered expansion. It cannot escalate an effect
that no adapter or principal identifies.

## 6. Amendment recursion

A charter transition is valid only if:

\[
Amendable_{\Theta_t}(\Theta_{t+1})
=
AuthProof_{\Theta_t}(\Delta\Theta)
\land Carry(\mathcal O_t,\mathcal O_{t+1})
\land AccountedContraction(\Theta_t,\Theta_{t+1})
\]

The proof binds both charter digests, the exact semantic diff, the current ledger root, and the
predecessor authority revision. The successor's authority cannot satisfy the proof.

This gives a local well-founded rule:

\[
\Theta_t \text{ judges } \Theta_t\rightarrow\Theta_{t+1}
\]

It does not provide a self-grounding constitution. `Theta_0` and its root of trust are external.

## 7. Admission function

Let `E_m` be the set of receipts bound to motion `m`. The admission function is:

\[
A_{\Theta_t}(m,E_m)
\in\{ALLOW,DENY,ESCALATE\}
\]

One conservative formulation is:

\[
DENY
\quad\text{if}\quad
\neg Authorized(m)
\lor KnownHardViolation(m)
\lor OrphanedObligation(m)
\lor SelfRatification(m)
\lor KnownInfeasibleRecourse(m)
\]

\[
ESCALATE
\quad\text{if}\quad
Uncovered(m)
\lor UnknownRequiredFinding(m)
\lor UnresolvedStanding(m)
\lor UnresolvedConflict(m)
\]

\[
ALLOW
\quad\text{otherwise, when every required hard predicate is satisfied.}
\]

Soft observations form a product order. Pareto dominance can identify a non-dominated candidate,
but it does not resolve every conflict. Scalarization is a separate governance decision and must be
named in the charter.

## 8. Conditional propositions

### Proposition 1: no self-ratification

If amendment receipts must bind `digest(Theta_t)` and authority is resolved exclusively from
`Theta_t`, then authority introduced only by `Theta_{t+1}` cannot authorize that transition.

This guarantee is conditional on immutable bindings, correct digest verification, and an external
authority verifier.

### Proposition 2: no silent obligation deletion

If every terminal transition checks the carry-forward relation against the predecessor ledger root,
then removing an open obligation without an authorized discharge cannot produce `ALLOW`.

This does not ensure the original obligation was just or complete.

### Proposition 3: known footprint expansion cannot be silently approved

If every boundary edge returned by the registered impact adapter requires a matching horizon and
standing rule, then a known new edge without those mappings cannot produce `ALLOW`.

This makes no claim about edges absent from the adapter's output.

### Proposition 4: pure-step replay equivalence

If `step` is deterministic and all clock, randomness, identity, policy, network, and evaluator
inputs arrive as ordered bound receipts, then two conforming interpreters starting from the same
state and receiving the same event sequence produce the same hard outcome.

Wire codecs and canonicalization must be covered by shared test vectors for this to be meaningful
across languages.

## 9. Relationship to adjacent mathematics

Viability theory can augment the state with `Theta` and describe viable trajectories of the entire
system. Robust control and model predictive control can evaluate particular temporal or physical
horizons. Multi-objective optimization can organize soft result vectors. Access-control logics can
decide authority. Assurance cases can provide structured evidence.

Polyhorizon does not replace any of these. It defines a composition boundary in which their outputs
remain typed, bound to the same motion, continuous across charter versions, and subject to
standing and amendment invariants.

The layer earns independence through different write authority, not computational irreducibility.
If the same candidate-controlled process owns the Forge, horizon registry, evidence sources,
ledger, and amendment root, the separation is nominal.

## 10. Computational and ethical limits

- Infinite-horizon reachability is generally intractable or undecidable. Deployments use bounded
  horizons, conservative approximations, sentinels, and periodic renewal.
- Causal and affected-party discovery are fallible.
- Conflicting obligations may deadlock; the kernel does not invent a social choice rule.
- Strategic or captured principals can authorize harmful outcomes.
- Sybil resistance and principal authentication belong to external identity systems.
- Evidence freshness does not prove evidence truth.
- Recourse after irreversible harm may be impossible.
- Additional horizons can create surveillance pressure; privacy-preserving evidence or authorized
  contraction may be preferable to collecting more raw data.

These limits are part of the method, not deferred implementation trivia.
