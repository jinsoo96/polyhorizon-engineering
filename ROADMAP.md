# Roadmap

Polyhorizon advances by evidence, not by feature count. Each milestone must improve the ability to
detect horizon collapse, preserve obligations, keep affected-party standing and recourse real, or
make independent implementations agree. Work that does not strengthen a falsifiable claim belongs
in an adapter or another project.

## v0.1: executable alpha

The initial alpha establishes the smallest portable engine shape:

- immutable `Charter` and `Proposal` manifests with semantic digests;
- plural horizons, standing, obligations, recourse, mandates, and predecessor amendment rules;
- a deterministic `PureKernel` that emits host-owned `EffectRequest` values;
- four-state `EffectReceipt` findings and non-scalar `Decision.horizon_vector` results;
- `Engine` orchestration over a replaceable compare-and-swap `SessionStore`;
- in-process effect handlers, a dependency-free CLI, and `polyhorizon.wire/v0.1` NDJSON;
- strict alpha JSON Schemas, executable Python/Node examples, and a canonical digest corpus;
- predecessor-sourced amendment ratification and manifest-level obligation carry-forward checks;
  and
- a falsification protocol, threat model, research boundary, and public-release guards.

Alpha status is deliberate. The manifest comparison in v0.1 is not yet a durable obligation
ledger or a semantic migration proof, and one Python implementation is not cross-language
conformance evidence.

## v0.2: continuity and interoperability

The next milestone targets the gaps most likely to invalidate the method:

- validate the published canonicalization profile and digest vectors with an independent-language
  implementation;
- stabilize and extend the alpha JSON Schemas with complete response, state, and transition vectors
  for every domain and wire API;
- add an append-only obligation lifecycle with carry-forward, substitution, discharge, and
  externally anchorable ledger roots;
- define semantic charter diffs and explicit evidence-equivalence migrations so renames cannot
  hide contractions;
- define an external result/evidence resolver contract around `result_digest` and
  `evidence_digest` without making `details` normative;
- strengthen receipt provenance, implementation identity, expiry, and revocation adapter
  contracts; and
- add crash-recovery and duplicate-delivery conformance cases for stores and effect providers.

Exit evidence: two implementations must reproduce the same canonical digests and hard decisions on
the published corpus, including obligation orphaning and predecessor-ratification attacks.

## v0.3: adapter and deployment conformance

- Publish an adapter SDK for horizon evaluators, authority verifiers, standing resolvers, impact
  discovery, evidence systems, and recourse executors.
- Add capability negotiation for typed horizon contracts without hardcoding vendors or domains.
- Ship a deployment conformance kit covering bypass resistance, trust-domain separation, stale
  authority, result retrieval, state rollback, and resource exhaustion.
- Demonstrate at least one isolated sidecar and one independent-language interpreter.
- Add signed checkpoints or transparency-log integration as optional ports rather than kernel
  dependencies.
- Document privacy-preserving observation and authorized contraction patterns so added horizons do
  not default to added surveillance.

## v0.4: comparative evidence

- Release the preregistered horizon-collapse challenge corpus with paired legitimate motions.
- Compare Loop, Forge, Viability, ordinary governance, and Polyhorizon arms under the same hidden
  outcomes and fault injections.
- Report false admission, false denial, false escalation, useful-change retention, recourse
  feasibility, obligation orphaning, and operational overhead without a framework-wide magic
  threshold.
- Run the same corpus against multiple stores and interpreters and publish disagreements.
- Invite affected-domain reviewers to challenge standing, recourse, and genesis-charter
  assumptions, not only implementation correctness.

## v1.0: conditional maturity

Version 1.0 is justified only if comparative results show material protection beyond a Forge or
Viability policy library while retaining useful change at acceptable domain-specific cost. It also
requires stable protocol compatibility, independent implementation evidence, a security review,
documented migrations, and at least one deployment with an enforcement boundary the subject cannot
bypass.

If the direct falsifiers in [docs/falsification.md](docs/falsification.md) hold, the project will
narrow its claims or collapse into a smaller governance library instead of relabeling the same
mechanisms.

## Explicit non-goals

The roadmap does not aim to make the kernel a universal moral theory, identity provider, causal
oracle, workflow engine, policy language, model host, distributed database, or regulator. Those
systems remain replaceable ports with declared trust assumptions.
