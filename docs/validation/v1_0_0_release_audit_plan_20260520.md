# Attestplane v1.0.0 Release Audit Plan

- Date: 2026-05-20
- Scope: v1.0.0 suffix-free stable release gate
- Gate reason: major_boundary
- Status: planned
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

## Evidence Matrix

| Dimension | Go condition | Evidence source |
| --- | --- | --- |
| API compatibility | Public API changes from v0.9.10 are additive or documented with a compatible migration path. | API diff or compatibility report, changelog breaking-change section. |
| Release CD | `release-cd` validates package policy, publishes via `channel=latest`, verifies PyPI/npm registry visibility, and creates the GitHub Release only after registry verification. | `release-cd` workflow run URL and job summary. |
| Push CI | The release commit waits for the required push workflows before package publication. Required workflows: `ci`, `sdk-python`, `sdk-typescript`, `cross-sdk-roundtrip`, `verifier-conformance`, `invariants`, `sbom`, `reproducible-build`, `osv-scanner`, and `codeql`. | Push workflow run URLs for the release commit. |
| Registry provenance | PyPI and npm packages resolve to the v1.0.0 version built from the release tag. npm provenance and Python Trusted Publisher runs complete successfully. | PyPI JSON, npm metadata, delegated publish workflow runs. |
| GitHub Release assets | GitHub Release exists for v1.0.0 and includes `artifact-manifest.json`, `checksums.sha256`, and `upload-plan.md`. | GitHub Release URL and asset list. |
| Security and supply chain | OSV scan has no untriaged blocking vulnerability, SBOM workflow succeeds, CodeQL succeeds, and gitleaks or secret scan evidence remains clean. | OSV, SBOM, CodeQL, and secret-scan reports. |
| Rollback | The rollback path is documented: PyPI yank rather than delete, npm dist-tag correction, GitHub Release marking, and hotfix release plan. | Rollback notes in this document or linked runbook. |

## Explicit Non-Goals

- Do not retag or rewrite any v0.9.x release.
- Do not publish v1.0.0 from local credentials.
- Do not move `ca`, `rc`, or `beta` npm dist-tags as part of the v1.0.0 gate.
- Do not treat skipped or unavailable evidence as passing evidence.

## Reviewer Sign-Off

Reviewer must fill this section before `audit_verified=true` is used.

- Reviewer:
- Evidence review commit:
- Push CI evidence:
- release-cd evidence:
- Registry evidence:
- GitHub Release evidence:
- Security evidence:
- Decision: pending

## Rollback Notes

If v1.0.0 is published and a release-blocking regression is found:

1. Yank the PyPI v1.0.0 files rather than deleting the release.
2. Move npm `latest` back to the last known-good stable version.
3. Edit the GitHub Release notes with a clear warning and affected versions.
4. Publish a v1.0.1 hotfix or a v0.9.11 continuity release, depending on the
   compatibility impact.
5. Record the incident in a follow-up validation report.
