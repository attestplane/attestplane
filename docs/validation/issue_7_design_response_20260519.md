<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Issue #7 Design Response — 2026-05-19

## Scope

This note records the conservative design response for
[#7](https://github.com/attestplane/attestplane/issues/7): EU AI Act
Article 12 specificity, independent verifier expectations, and
retention/deletion-proof handling.

This is a design response, not an implementation pass. It does not
expand Attestplane's public claims and does not assert compliance,
certification, production readiness, or legal sufficiency.

Claude Opus was consulted because the issue crosses regulatory,
authority-boundary, and verifier-trust design. The advisory result is
non-authoritative; the project policy and documented claim boundaries
remain authoritative.

## Design Stance

### 1. EU AI Act Article 12 Surface

Attestplane should describe this as an **AIA-12 aligned profile**, not
as EU AI Act compliance or certification.

The profile can add specificity beyond a generic append-only audit log:

- role-bound event fields for provider, deployer, operator, and human
  reviewer where applicable
- system, model, and policy version references
- decision, intervention, exception, and drift event categories
- continuity checkpoints that make missing log spans detectable
- optional external timestamp anchoring for time evidence
- offline-readable regulator/auditor export shape

This profile is useful because Article 12 is about automatic event
recording for high-risk AI systems, but Attestplane must keep the line
clear: it provides evidence substrate primitives, not a legal
determination that a system satisfies Article 12.

### 2. Verifier Independence

The trust root should be an open-source, deterministic verifier plus
versioned schemas.

An API can help users discover, slice, and retrieve records, but it must
not be required for truth. A third-party auditor should be able to take
a complete export, schema version, trust roots, signatures, and
timestamp evidence, then verify offline.

Red line:

```text
Verification must not require trusting an Attestplane-hosted production API.
```

The API is a convenience layer. The verifier and schema are the
authority.

### 3. Retention and Deletion Proof

Pure append-only tombstones are not enough if raw personal data was
written into the chain. Treating deletion as entirely out of scope is
also too weak for a project that discusses regulator-facing audit
substrates.

The conservative design is:

1. Minimize PII before ingest. Raw PII should not enter append-only
   evidence by default.
2. Store commitments or hashes in the audit chain where possible.
3. Keep deletable source material in a sidecar store controlled by the
   controller/deployer.
4. On deletion, destroy or redact sidecar material and append a
   redaction/deletion-evidence event that preserves chain continuity.

This can support a future "commit-then-redact" profile, but the alpha
project should not claim GDPR compliance or right-to-erasure automation.

Explicit alpha out-of-scope areas:

- cryptographic shredding for large media objects
- training-data erasure guarantees
- controller-specific legal sufficiency under GDPR Article 17

## Recommended Next Work

1. Add an AIA-12 aligned profile document with explicit
   non-certification wording.
2. Add verifier-independence documentation that separates OSS verifier
   trust from API convenience.
3. Add a retention/deletion proof ADR covering PII minimization and
   commit-then-redact.
4. Keep #7 open until the owner confirms whether this public-facing
   stance is acceptable and which pieces should become implementation
   work.

## Claim Safety

- EU AI Act compliance claimed: false
- GDPR compliance claimed: false
- compliance certification claimed: false
- production readiness claimed: false
- hosted API required for verification: false

## Explicit Non-Actions

- implementation: not performed
- tag: not performed
- release: not performed
- publish: not performed
- deploy: not performed
- workflow_dispatch for issue #7: not performed
- secrets printed: false

## Final Status

`issue_7_design_response_recorded`
