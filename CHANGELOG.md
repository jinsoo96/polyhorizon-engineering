# Changelog

All notable public changes to Polyhorizon Engineering are documented here. The project follows
semantic versioning for the Python package; each domain and wire protocol also carries its own API
identifier.

## [Unreleased]

No public changes yet.

## [0.1.0] - 2026-07-22

Initial public alpha.

### Added

- Polyhorizon Engineering method, formal theory, philosophy, falsification protocol, research
  review, architecture, threat model, integration guide, and wire specification.
- Typed `Charter` and `Proposal` models for purposes, horizons, affected-party standing,
  obligations, recourse, mandates, and predecessor amendment rules.
- Deterministic `PureKernel` admission state machine with `allow`, `deny`, and `escalate`
  decisions, plus a non-scalar per-horizon result vector.
- Host-owned `EffectRequest`/`EffectReceipt` protocol with four-state findings and bound external
  evidence/result digests.
- `Engine`, replaceable `SessionStore`, memory and local-file stores, in-process handler registry,
  and bounded in-process runner.
- Dependency-free CLI with capabilities, manifest validation, persisted session operations, and an
  NDJSON server.
- `polyhorizon.wire/v0.1` commands: `capabilities`, `open`, `advance`, `inspect`, and `abort`.
- Strict alpha JSON Schemas, an in-process Forge mutation example, a dependency-free Node sidecar
  client, and canonical digest vectors for port authors.
- Public-boundary hooks and CI checks to exclude credentials, internal worklogs, local state, and
  private evidence from outgoing commits and release artifacts.

### Security and semantic notes

- Amendment effects are resolved from the predecessor charter; a proposed successor cannot
  authorize its own adoption.
- Changing or removing a predecessor principal, trust domain, or adapter requires a release from
  that predecessor identity through its predecessor adapter.
- Amendment authority requests bind a deterministic typed before/after change set together with an
  externally maintained predecessor ledger-root digest.
- Changed or removed predecessor obligations require beneficiary discharge evidence in the alpha
  manifest transition.
- Hard findings are conjunctive; `unknown` and `uncovered` escalate rather than becoming zero or
  success.
- `EffectReceipt.details` is diagnostic and excluded from semantic receipt and session-state
  digests. `result_digest` binds the external result used by the adapter.
- The `polyhorizon.engine.v1` canonical profile rejects floats and surrogate code points, fixes
  UTF-8 object-key order, and publishes cross-language digest vectors.
- Local persistence uses strict one-step CAS transitions, atomic idempotency indexing, and hashed
  OS advisory locks; it remains a cooperative local-filesystem store, not distributed consensus.

### Known limits

- v0.1 does not yet implement a durable cross-session obligation ledger, semantic migration proof,
  independently validated cross-language interpreter, or distributed transaction.
- The kernel cannot prove that a charter is just, discover effects omitted by every adapter,
  authenticate principals without a host verifier, or force a hostile host to enforce a decision.
