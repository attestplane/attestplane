<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# ADR-0015: Adopt Commit-Then-Redact Retention Evidence Profile

Date: 2026-05-19

Status: Accepted

## Context

Attestplane is append-only by design: hash-chain evidence is useful because
insertions, deletions, and modifications are detectable. That property creates
tension with personal-data retention and deletion obligations. A naive
append-only tombstone is not enough if raw personal data was written directly
into the chain. Treating deletion as entirely out of scope is also too weak for
a project that publishes regulator-facing evidence substrate language.

Issue #7 asked how Attestplane should handle the tension between audit
continuity and deletion or redaction workflows.

The alpha project must preserve strict claim boundaries:

- no claim of GDPR compliance,
- no claim of legal sufficiency for a deployed controller,
- no claim that deleting sidecar data erases every downstream copy, and
- no hidden mutation of historical chain entries.

## Decision

Adopt a commit-then-redact retention evidence profile:

1. **Minimize before ingest.** Raw personal data should not enter append-only
   evidence by default. Callers should record opaque references, salted hashes,
   commitments, or content-addressed handles where practical.
2. **Separate chain evidence from deletable material.** Large objects, raw
   prompts, personal records, and other deletable material should live in a
   controller-owned sidecar store, not in the immutable chain.
3. **Commit to the sidecar object.** The chain may record a hash, content
   address, encrypted-object reference, or policy-scoped handle that lets a
   reviewer detect whether the sidecar object matched the event at commit time.
4. **Redact or delete sidecar material under controller policy.** When a
   deletion or redaction happens, the sidecar material is removed or replaced
   according to the controller's policy and legal basis.
5. **Append a redaction/deletion evidence event.** The chain records what was
   done, when, by which actor or policy, and which prior references were
   affected. The original chain entries remain intact, but the raw sidecar
   material can be unavailable by design.
6. **Fail closed on unsupported claims.** A verifier may report that a
   redaction/deletion evidence event exists. It must not conclude that a
   controller satisfied a legal request unless a higher-level profile and legal
   review explicitly support that conclusion.

## Consequences

Positive:

- Preserves hash-chain continuity.
- Avoids silent mutation of historical evidence.
- Gives auditors a durable record that a redaction or deletion action occurred.
- Keeps raw personal data out of the default append-only path.
- Leaves controller-specific retention policy outside the substrate core.

Negative:

- Requires deployers to manage sidecar stores and retention policy.
- Does not by itself prove legal sufficiency.
- Cannot erase data that was already copied into external systems.
- Requires clear export behavior when sidecar material has been removed.

## Verification Implications

The verifier can check:

- chain continuity,
- presence and shape of redaction/deletion evidence events,
- whether referenced prior events exist,
- whether the sidecar commitment still matches when material is present, and
- whether the export marks missing sidecar material explicitly.

The verifier should not check:

- whether the controller had a lawful basis,
- whether all external processors deleted their copies,
- whether a right-to-erasure request was legally complete, or
- whether retention windows satisfy a specific regulation.

## Public Claim Boundary

Safe:

- "Attestplane supports a commit-then-redact evidence profile."
- "Attestplane can record redaction/deletion evidence while preserving chain
  continuity."
- "Raw personal data should be kept out of append-only evidence by default."

Unsafe:

- claiming GDPR compliance,
- claiming automatic right-to-erasure completion,
- claiming legal sufficiency for controller-specific retention, or
- implying historical chain entries are silently rewritten.

## Relationship to Issue #7

This ADR resolves the retention/deletion proof portion of issue #7 as an
architecture decision. Follow-up implementation can add concrete event schemas
and verifier predicates under this boundary.

## References

- OM World Execution Proof — [`docs/execution-proof.md` §Deletion evidence
  (commit-then-redact)](https://github.com/omworldprotocol/om-world/blob/61979b1/docs/execution-proof.md#deletion-evidence-commit-then-redact)
  adopts the same commit-then-redact primitive: minimize PII before ingest →
  controller-owned sidecar for raw/deletable material → signed
  deletion-evidence event → append-only chain preserved. Cross-adoption
  tracked in [issue #7](https://github.com/attestplane/attestplane/issues/7).
