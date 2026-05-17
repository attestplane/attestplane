<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Allowed Claims (v0.0.1-alpha)

This is the counterpart of [`forbidden_claims.md`](forbidden_claims.md): the
list of statements about Attestplane that are **supported by shipped
artifacts** as of the current milestone. Every claim here has at least one
of: (a) merged code path, (b) test in CI, (c) ADR with `Status: Accepted`,
(d) published artifact (TestPyPI, npm, GitHub Release).

If a claim is here, it is safe to use in README, SDK docs, release notes,
and marketing surface without further qualification.

## v0.0.1-alpha (as of 2026-05-17)

### Shipped substrate

- The SHA-256 hash chain primitive is implemented in
  `sdk/python/src/attestplane/hashchain.py` and `sdk/typescript/src/hashchain.ts`
  and is locked by [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md).
- The chain is **tamper-evident**: any single-event mutation, reorder, or
  deletion within a verified segment is detected by `verify_chain()`.
- Cross-language byte conformance between the Python and TypeScript SDKs is
  enforced on every CI run against
  `sdk/python/tests/conformance/vectors.json` (10 frozen vectors, schema
  version `1`).
- The EU AI Act **Article 12(2)(a) field set** (`session_id`,
  `reference_db_ref`, `matched_input_ref`, `human_verifier`) is built into
  `EventDraft` as first-class fields.
- GDPR Article 4(5) pseudonymization is enforced **at the type level** via
  the `SubjectRef` strong type (no raw PII can be silently written into the
  subject field).
- v0.0.1 is published to **TestPyPI** (sandbox) and **npm** (production with
  the `alpha` dist-tag); both artifacts carry the corresponding supply-chain
  attestation (OIDC trusted publishing for TestPyPI; npm `--provenance` for
  npm).
- GitHub Release v0.0.1-alpha ships the wheel + sdist + npm tarball +
  CycloneDX SBOM (JSON + XML), all signed with **Sigstore keyless cosign**;
  bundles are publicly verifiable against the Sigstore transparency log.
- Supply-chain hygiene: REUSE 3.3 compliance, CodeQL SAST on Python +
  GitHub Actions, OSV-Scanner daily, OSSF Scorecard weekly, reproducible
  wheel-build verification, all third-party GitHub Actions SHA-pinned.
- DCO sign-off is required on every commit; no CLA.

### Designed-toward but not yet shipped

These claims describe intent and design, not current behavior. They are
safe to use when paired with the milestone qualifier ("M5", "M6", or "M7").

- "Designed toward RFC-3161 anchoring" — design locked by
  [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md); implementation in M5.
- "Designed toward EU AI Act Article 12 auditability" — Art. 12(2)(a)
  fields shipped; obligation registry + verifier ship at M5.
- "Designed toward DORA Article 8 audit-trail obligations" — obligation
  registry ships at M5.

## Implementation-status phrasing rule

When a claim references an obligation registry entry under
`attestplane/obligations/`, the public phrasing must use the entry's
`implementation_status` value. Only four values are permitted; see
[`forbidden_claims.md` § Obligation-registry implementation_status](forbidden_claims.md#obligation-registry-implementation_status).

## Update cadence

This document is updated at every milestone (M5, M6, M7, M8+) and at every
release. New claims may be added when:

1. The corresponding feature is merged on `main`.
2. CI verifies the behavior the claim describes.
3. An ADR or release note records the addition.

Removing a claim from this list requires a release note and is generally
only done for security-driven retractions or scope changes.
