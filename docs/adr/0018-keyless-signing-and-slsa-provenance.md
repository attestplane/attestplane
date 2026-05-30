---
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
---

# 0018. Sigstore keyless signing and SLSA Build L3 provenance for new releases

- **Date**: 2026-05-21
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot
- **Related**: [ADR-0006](0006-sigstore-rekor-redundant-anchor.md),
  [ADR-0017](0017-github-actions-release-cd.md),
  [`docs/release/verifying-signatures.md`](../release/verifying-signatures.md),
  [issue #18](https://github.com/attestplane/attestplaneissues18)

## Context

Issue #18 left the substrate in a state where:

- `sign-release.yml` implemented dry-run and execute paths for cosign
  keyless signing, but the execute path was never exercised on a real
  release because the only earlier attempt was local and hit
  Sigstore's device-flow timeout in a non-interactive environment.
- `provenance.yml` was a dry-run inventory only and explicitly
  refused execute mode, deferring any SLSA claim to a future
  decision.
- Released wheels, sdists, npm tarballs, and CycloneDX SBOMs shipped
  without cosign signatures or SLSA in-toto attestations, so
  downstream consumers could not verify the supply chain offline.

The substrate's positioning as Article-12-aligned audit infrastructure
made this gap load-bearing: an evidence substrate that cannot itself
demonstrate verifiable supply-chain evidence is structurally weak.

## Decision

Adopt the following supply-chain evidence regime for **new** releases,
applied forward only:

1. **Keyless cosign signing.** Primary release assets (Python wheel,
   sdist, npm tarball, CycloneDX SBOM files) are signed with
   Sigstore keyless cosign through the existing `sign-release.yml`
   workflow's execute path, invoked from GitHub Actions with
   `id-token: write` OIDC. The workflow now also accepts a
   `workflow_call` trigger so that future automation can invoke it
   from `release-cd.yml` without duplicating the signing logic.

2. **SLSA Build L3 provenance.** A new `slsa-provenance.yml` workflow
   computes SHA-256 digests of the release assets, then invokes the
   upstream
   [`slsa-framework/slsa-github-generator`](https://github.com/slsa-framework/slsa-github-generator)
   `generator_generic_slsa3.yml` reusable workflow at tag `v2.1.0`
   (audit-anchor commit `f7dd8c54c2067bafc12ca7a55595d5ee9b75204a`,
   released 2025-02-24). The generator emits an
   `attestplane-<TAG>.intoto.jsonl` attestation that is uploaded to
   the GitHub Release only when `execute=true`.

   **Tag-ref vs SHA-pin caveat.** GitHub Actions' reusable-workflow
   `uses:` clause only accepts a tag ref (`refs/tags/vX.Y.Z`), not a
   bare commit SHA; the upstream slsa-github-generator binary-fetch
   path explicitly rejects SHA-pinned calls with
   `Invalid ref: <sha>. Expected ref of the form refs/tags/vX.Y.Z`.
   The workflow therefore references the upstream by **tag**
   (`@v2.1.0`) and records the **commit SHA** in a sidecar comment as
   the audit anchor. Tag immutability on the upstream repository plus
   the published Sigstore signature on the upstream release together
   provide the SHA-equivalent integrity binding. A future bump
   requires the maintainer to (a) verify the new tag's commit SHA
   against the upstream release notes, (b) update both the `@vX.Y.Z`
   tag ref and the sidecar SHA comment in `slsa-provenance.yml`, and
   (c) re-run `slsa-verifier verify-artifact` end-to-end before
   merging the bump.

3. **Verification recipe owned by users, not by Attestplane.** The
   verification path is documented in
   [`docs/release/verifying-signatures.md`](../release/verifying-signatures.md)
   using `cosign verify-blob` and
   `slsa-verifier verify-artifact` against published assets. The
   trust root is the upstream Sigstore root and the upstream
   slsa-verifier binary; there is no Attestplane-hosted API in the
   verification path. This is consistent with
   [`docs/architecture/verifier_independence.md`](../architecture/verifier_independence.md).

4. **Forward-only application.** Existing tags
   (`v0.0.x`, `v0.7.x`, `v0.8.x`, and the early `v0.9.x` line) are
   **not** retroactively signed and **not** retagged. The historical
   evidence baseline for those releases remains the published wheel
   and tarball hashes in the release notes.

5. **No SLSA self-assessment.** The SLSA Build L3 claim attached to
   provenance files originates from the upstream slsa-github-generator
   implementation. Attestplane does not self-attest to a SLSA level
   in this ADR; the binding evidence is whatever
   `slsa-verifier` validates against the produced `.intoto.jsonl`
   against the recorded source tag and generator workflow.

6. **No legal compliance claim.** Signature verification is a
   supply-chain integrity check. It does not constitute an
   EU AI Act compliance conclusion, an Article 12 conformity
   assessment, ISO/IEC 42001 certification, or any other regulatory
   determination for any deployment that consumes the artifact. The
   Article-12-aligned profile framing in
   [`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md)
   is unchanged by this decision.

## Consequences

Downstream consumers, auditors, and EU AI Office reviewers can verify
the provenance of any Attestplane release published after this ADR
without trusting a hosted Attestplane endpoint. The verification
trust root is open: Sigstore Public Good, the upstream
slsa-github-generator, and the GitHub Actions OIDC issuer.

The release runbook must drive both `sign-release.yml`
(`execute=true`) and `slsa-provenance.yml` (`execute=true`) after a
release-cd publication run and before announcing the release.
Releases that ship without these artifacts are not covered by the
new evidence regime and must be flagged as such in their release
notes.

Pinning the SLSA generator by commit SHA means a deliberate
maintainer action is required to bump the generator version. The
bump is itself a release-evidence event: the new SHA, the new
version, and re-verification of a synthetic release with
`slsa-verifier` must be recorded before merging the bump.

Cosign keyless signatures expire from Sigstore's transparency log
view in the conventional sense — the signature itself remains
verifiable offline through the `.cosign.bundle`. Long-term
verifiability therefore depends on consumers retaining the bundle
alongside the artifact; this is documented in the verification
guide.

This decision does **not**:

- claim GA readiness, production readiness, or a security support
  SLA for any pre-`1.0` release line;
- modify any frozen ADR, schema, or fixture;
- introduce any dependency that would have to be replaced for the
  substrate to remain Apache-2.0 redistributable;
- change the
  [`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md)
  framing.

## Out of scope (deferred)

- Automatic invocation of `sign-release.yml` and `slsa-provenance.yml`
  from `release-cd.yml`. The `workflow_call` trigger is now wired so
  this is a future, separately-reviewed integration.
- Attaching CycloneDX SBOMs to GitHub Releases automatically. The
  signing workflow signs SBOM files only if they have already been
  attached to the release; closing the SBOM-attach loop is a
  follow-up.
- Bumping cosign or slsa-github-generator pinned versions. Each bump
  is its own evidence event and must follow the bump policy above.
- Retroactive signing or provenance for any pre-existing tag.
