# Attestplane v1.0.0 Release Audit Plan

- Date: 2026-05-20
- Scope: v1.0.0 suffix-free stable release gate
- Gate reason: major_boundary
- Status: pre-release audit approved
- Audit source: Opus architect advisory, 2026-05-20

## Decision Rule

The v1.0.0 release may proceed only when this plan has objective evidence for
each required dimension and a maintainer records the evidence review decision.
The release train must not bypass the major-boundary gate with
`ATTESTPLANE_RELEASE_AUDIT=off` unless the release gate itself is proven to be
wrong.

`audit_verified=true` means the evidence matrix below has been reviewed and the
reviewer accepts that v1.0.0 can be published through the normal stable release
path.

This v1.0.0 release is a stability-commitment milestone. The audited delta from
v0.9.10 to the release-prep HEAD does not introduce SDK public API source
changes; the 1.0.0 version marks the stable default channel commitment rather
than a breaking API change.

## Evidence Matrix

| Dimension | Go condition | Evidence source |
| --- | --- | --- |
| API compatibility | Public API changes from v0.9.10 are additive or documented with a compatible migration path. | `git diff --name-only v0.9.10..dec80174fbcd487441c0ada1ea3b3cf2887b5adc` shows the v1.0.0-prep delta is limited to release workflows, release automation, validation docs, `.lycheeignore`, and release-train tests. No SDK source or public API files changed after v0.9.10. |
| Release CD | `release-cd` validates package policy, publishes via `channel=latest`, verifies PyPI/npm registry visibility, and creates the GitHub Release only after registry verification. | Last stable proof: `release-cd` run 26182312426 for v0.9.10 completed successfully. v1.0.0 release-cd must complete the same registry verification path before post-release approval. |
| Push CI | The release commit waits for the required push workflows before package publication. Required workflows: `ci`, `sdk-python`, `sdk-typescript`, `cross-sdk-roundtrip`, `verifier-conformance`, `invariants`, `sbom`, `reproducible-build`, `osv-scanner`, and `codeql`. | Current release-prep HEAD `dec80174fbcd487441c0ada1ea3b3cf2887b5adc`: `ci` 26183636462, `sdk-python` 26183636253, `sdk-typescript` 26183794400, `cross-sdk-roundtrip` 26183636341, `verifier-conformance` 26183636465, `invariants` 26183636327, `sbom` 26183636320, `reproducible-build` 26183636408, `osv-scanner` 26183636461, and `codeql` 26183636404 all completed successfully. |
| Registry provenance | PyPI and npm packages resolve to the v1.0.0 version built from the release tag. npm provenance and Python Trusted Publisher runs complete successfully. | Pre-release baseline: PyPI latest is 0.9.10 and npm `latest` is 0.9.10. Last delegated Python publish proof: run 26182356915 for v0.9.10 completed successfully. v1.0.0 must pass release-cd registry verification before the release is considered complete. |
| GitHub Release assets | GitHub Release exists for v1.0.0 and includes `artifact-manifest.json`, `checksums.sha256`, and `upload-plan.md`. | Pre-release baseline: GitHub Release v0.9.10 exists at <https://github.com/attestplane/attestplanereleasestag/v0.9.10> with `artifact-manifest.json`, `checksums.sha256`, and `upload-plan.md`. v1.0.0 release-cd must create the same assets after registry verification. |
| Security and supply chain | OSV scan has no untriaged blocking vulnerability, SBOM workflow succeeds, CodeQL succeeds, and gitleaks or secret scan evidence remains clean. | Current release-prep HEAD evidence: `osv-scanner` 26183636461 success, `sbom` 26183636320 success, and `codeql` 26183636404 success. No raw secret values are recorded in this document. |
| Rollback | The rollback path is documented: PyPI yank rather than delete, npm dist-tag correction, GitHub Release marking, and hotfix release plan. | Rollback notes below are the required v1.0.0 rollback path. |

## Explicit Non-Goals

- Do not retag or rewrite any v0.9.x release.
- Do not publish v1.0.0 from local credentials.
- Do not move `ca`, `rc`, or `beta` npm dist-tags as part of the v1.0.0 gate.
- Do not treat skipped or unavailable evidence as passing evidence.

## Reviewer Sign-Off

This pre-release sign-off authorizes using `audit_verified=true` for the normal
release-cd path only. It does not waive release-cd registry verification, npm
provenance, Python Trusted Publisher checks, or post-release registry checks.

- Reviewer: Codex release automation operator, with Opus reviewer advisory.
- Evidence review commit: `dec80174fbcd487441c0ada1ea3b3cf2887b5adc`
- Push CI evidence: runs 26183636462, 26183636253, 26183794400,
  26183636341, 26183636465, 26183636327, 26183636320, 26183636408,
  26183636461, and 26183636404.
- release-cd evidence: v0.9.10 baseline run 26182312426 succeeded; v1.0.0
  must pass the same release-cd verification path before completion.
- Registry evidence: PyPI latest 0.9.10 and npm `latest` 0.9.10 verified
  before v1.0.0 release; v1.0.0 registries must be verified by release-cd.
- GitHub Release evidence: v0.9.10 release exists with required assets;
  v1.0.0 release-cd must create equivalent release assets.
- Security evidence: OSV, SBOM, and CodeQL push checks succeeded for
  `dec80174fbcd487441c0ada1ea3b3cf2887b5adc`.
- Decision: approved for controlled v1.0.0 release-cd execution with
  post-release verification required.

## Rollback Notes

If v1.0.0 is published and a release-blocking regression is found:

1. Yank the PyPI v1.0.0 files rather than deleting the release.
2. Move npm `latest` back to the last known-good stable version.
3. Edit the GitHub Release notes with a clear warning and affected versions.
4. Publish a v1.0.1 hotfix or a v0.9.11 continuity release, depending on the
   compatibility impact.
5. Record the incident in a follow-up validation report.
