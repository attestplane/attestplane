# 0017. Adopt GitHub Actions CD as the only package publication path

- **Date**: 2026-05-20
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot
- **Related**: [ADR-0016](0016-rc-api-freeze.md), [GitHub CD release runbook](../runbooks/github-cd-release.md)

## Context

Attestplane has already published beta packages to PyPI and npm and is
preparing the `v0.8.0-rc.N` line. The project now needs release discipline
stronger than local one-off publish commands: package publication must be
auditable, repeatable, tied to a reviewed Git tag, and protected from accidental
npm `latest` movement.

The existing Python and TypeScript publish workflows already use GitHub-hosted
runners and trusted-publishing-oriented credentials. What is missing is a
single CD entrypoint that validates the requested tag, checks package-version
alignment, computes the registry channel, runs build-only gates, and then
publishes both SDK packages through the same auditable path.

## Decision

GitHub Actions CD is the only supported publication path for Attestplane
packages.

The release CD path:

- Starts from an intentional release tag such as `v0.8.0-rc.1`.
- Validates the tag shape and package-version mapping before publication.
- Publishes Python through the PyPI trusted-publishing workflow.
- Publishes TypeScript through npm trusted publishing with provenance, with the
  existing token fallback only when trusted publishing is unavailable.
- Uses npm dist-tags derived from the release channel:
  `alpha`, `beta`, `rc`, or `latest`.
- Rejects pre-release publication with `latest` in the default path.
- Verifies PyPI and npm registry visibility after publication.
- Keeps local machines responsible only for release preparation, tagging,
  dispatch, and verification.

Local `npm publish`, `twine upload`, direct PyPI upload commands, force-push of
published tags, and ad-hoc publish scripts are not supported release paths.

## Consequences

Publication is easier to audit because the workflow run, tag, package versions,
registry channel, and verification logs are linked in GitHub Actions.

The release owner must keep package versions, tag names, and release notes in
sync before dispatch. A mismatch now blocks the release instead of producing a
partial registry state.

Emergency registry fixes must use explicit registry management or a new
release candidate. Existing published versions must not be deleted and reused.

This decision does not claim GA readiness, production readiness, legal
compliance certification, SLSA L3, or a security support SLA for pre-GA
packages.
