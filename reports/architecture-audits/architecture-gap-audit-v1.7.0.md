<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Architecture Gap Audit — v1.7.0

- **Milestone:** `v1.7.0`
- **Anchor:** `v1.5.0`
- **Head:** `cb3d33451aeac60d6314e49e5079bdccc9862778`
- **Plan level:** daily (diff-level)
- **Decision:** `daily-plan` / `daily_small_upgrade`
- **Stable releases since anchor:** 14
- **Real commits since anchor:** 24
- **Release-prep commits since anchor:** 17

## Audit Summary

The v1.7.0 milestone is a daily small-upgrade that carries the first
product-bearing stable cut since v1.5.0. Three product changes (commits
`3f551d9`, `5b32c86`, `8cb5458`) form the user-visible delta:

1. **Non-empty proof bundles on demand (`3f551d9`)** — adds the
    `--require-non-empty` / `--strict-schema` flags to the CLI and wires
    `require_non_empty` / `require_signed_attestation` through the Python
    and TypeScript verifiers.
2. **Product-delta gate (`5b32c86`)** — blocks stable releases that carry
    no product changes, enforced in `scripts/release/release_gate.py` and
    `stable_auto_train.py`.
3. **Product autodev prioritization (`8cb5458`)** — ensures the stable
    train does not advance on release-prep-only commits.

The remaining infra commits (14 fix/ci/test commits, plus 17 release-prep
commits) are support work only and do not change product behavior.

## Verified Product Surface

### SDK verifier (Python + TypeScript)

- `verify_proof_bundle()` accepts `require_non_empty` and
  `require_signed_attestation` keyword arguments.
- `BundleVerificationResult` exposes `primary_reason`, `secondary_reasons`,
  `signed_attestation_schema_ok`, and
  `signed_attestation_schema_reason`.
- Error-code priority: chain mismatch > require_non_empty > signed_schema
  > metadata > policy > retention > isolation.
- TypeScript verifier mirrors the Python API with `requireNonEmpty` and
  `requireSignedAttestation` options.

### CLI

- `attestplane verify <bundle>` supports `--require-non-empty` and
  `--strict-schema` flags.
- `attestplane verify --json` and `--explain` expose the reason-code
  taxonomy.

### Conformance

- 8 verifier conformance vectors (v1.2 schema) including
  `empty_bundle_require_non_empty`.
- 4 proof-bundle minimum-schema negative vectors (v2 schema):
  `empty-bundle`, `attestations-array-empty`,
  `attestation-missing-signature`, `attestation-missing-subject-digest`.
- 5 frozen negative fixtures under `negative/` for chain-integrity
  violations.

## Identified Gaps

### GAP-1: SDK builder API boundary hardening

`ProofBundleBuilder.minimal(subject_digest, signer)` exists but the typed
error constructor (`EmptyProofBundleError`, `IncompleteProofBundleError`)
is tested on only one code path. Edge cases — zero-length digest, nil
signer, concurrent builder use — lack coverage.

### GAP-2: Strict-schema output-contract fixture

The `--strict-schema` verification path lacks a pinned JSON output fixture
for CI consumers. Downstream automation cannot deterministically validate
that strict-mode rejection follows a stable serialization contract.

### GAP-3: Python/TypeScript strict-mode behavioral parity

The `require_signed_attestation` parameter was added after the initial
`require_non_empty` implementation. The TypeScript verifier may not yet
expose the equivalent `requireSignedAttestation` option through the public
API consistently (e.g., CLI parity, error-code mapping for schema
rejection).

### GAP-4: User-visible v1.7.0 delta documentation

The release notes draft (`v1.7.0.draft.md`) exists but the final
integrator-facing documentation in `docs/release-notes/v1.7.0.md` must be
verified against the actual product delta. Missing: explicit reason-code
catalog, migration example for `EmptyProofBundleError`, and the
`--strict-schema` / `--require-non-empty` CLI semantics reference.

## Recommendation

Close GAP-1 and GAP-2 as P1 product work before cutting the v1.7.0 stable
tag. Address GAP-3 as P1 conformance work to guarantee cross-SDK
consistency. Treat GAP-4 as P2 docs/support work that must not block the
product cut.
