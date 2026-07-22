# Security policy

Version 0.1 is an alpha reference engine. It is not a cryptographic authorization service, a
distributed transaction coordinator, or a safety certification.

Please do not publish an exploit before the maintainer can assess it. Use GitHub private
vulnerability reporting once it is enabled, or another authenticated private channel already
agreed with the maintainer. Include the affected version, trust assumptions, smallest reproducer,
impact, and the last durable transition or audit state.

Highest-priority reports include:

- an effect executed without a corresponding authorized request;
- receipt replay, rebinding, sequence bypass, or idempotency collision;
- namespace confusion between independently defined horizon kinds;
- a hard obligation, unknown consequence, or uncovered observer collapsed into a passing score;
- an obligation losing its accountable owner during amendment;
- an evaluator, authority, or horizon authorizing its own replacement at the same layer;
- a false rollback, appeal, exit, handoff, or other recourse claim;
- canonicalization or digest disagreement across supported transports;
- audit history mutation or reordering accepted as valid; and
- local-only paths bypassing Git-history or distribution-archive controls.

Documented trust assumptions and explicit known limits are not vulnerabilities by themselves. A
result that exceeds a declared boundary, or silently weakens it, is.
