# Release Signing Decision

Date: 2026-05-25

This document records the release-signing foundation decision for the
`#61` boundary. It also captures the explicit deferral chosen for the
release-signing / security-key custody model.

## Decision

Release-signing for the `v1.7.x` line is explicitly deferred.

The repository already carries release-provenance guidance and release
asset integrity controls, but it does not yet have a separately reviewed
release-signing custody model for the `v1.7.x` release surface or the
dedicated `security@attestplane.com` GPG custody model. Shipping a new
signing gate in this issue would overstate the current release boundary.

## Target Milestone

The deferred signing foundation is targeted for the later GA security
milestone documented in `SECURITY.md`. Until then, the release train stays
on checksum-plus-provenance verification only.

## Risk Acceptance

Until that milestone lands, release integrity for `v1.7.x` artifacts is
treated as checksum-plus-provenance based, not as a separate
release-signature guarantee.

The interim integrity control is:

- SHA-256 checksum pinning for the release asset set.
- Provenance attestation verification via the existing release-provenance
  recipes.

This control is the documented fallback for the release train; it does not
retrofit previously published artifacts or imply that a `--signature`
verifier path exists in the current CLI.

## Deferral window, blockers, and readiness impact

- **Deferral window.** The signing foundation remains deferred until the
  later GA security milestone published in `SECURITY.md`.
- **Blockers.** The project still lacks an approved protected-environment
  custody workflow for signing material and has not designated a second
  security triage contact.
- **Impact on readiness claims.**
  - CNA and CVE application material must not imply that a project GPG key
    is already published.
  - OpenSSF Scorecard claims are unaffected, because Scorecard does not
    depend on a private reporting-key rollout.
  - Release-readiness language must continue to say checksum-plus-provenance
    only until the deferral is lifted.

## Interim Verification Recipe

1. Pin the checksum manifest for the release you are consuming.
2. Verify the provenance attestation using
   [`docs/release/verifying-signatures.md`](../release/verifying-signatures.md).
3. Treat the release as integrity-checked only through checksums and
   provenance unless the tag-specific release notes explicitly state that a
   release-signing surface has landed.

## Closeout Requirement

The milestone owner must review and approve this decision before the issue
can be closed. That approval is tracked outside the repository and must be
recorded in the issue thread.
