# npm Dist-Tag Policy

This document records Attestplane's npm dist-tag rules for prerelease and
stable publication. It is a release-control policy, not a package publication
script.

## Default Rules

| Release tag | npm version | Required dist-tag |
|---|---|---|
| `vX.Y.Z-alpha.N` | `X.Y.Z-alpha.N` | `alpha` |
| `vX.Y.Z-beta.N` | `X.Y.Z-beta.N` | `beta` |
| `vX.Y.Z-rc.N` | `X.Y.Z-rc.N` | `rc` |
| `vX.Y.Z` | `X.Y.Z` | `latest` |

Prerelease versions must publish under their matching prerelease dist-tag.
Stable releases publish under `latest`.

The release CD default path must reject prerelease publication with `latest`.
Any exception requires a maintainer-recorded decision before dispatch.

## Current Latest Ownership

`@attestplane/attestplane@0.8.0-beta.0` currently owns both:

- `beta`
- `latest`

This was an explicit maintainer decision made after the beta registry release
became visible on npm and PyPI. It means default npm installs exercise the
published beta package while the project remains pre-GA.

This does not change the claim boundary:

- `0.8.0-beta.0` is not GA.
- `0.8.0-beta.0` is not a production-readiness claim.
- `0.8.0-beta.0` is not a regulatory certification or legal-compliance claim.

## Planned RC Behavior

The planned `v0.8.0-rc.1` cut must publish as:

- npm version: `0.8.0-rc.1`
- npm dist-tag: `rc`

The RC release must not move `latest` unless a separate maintainer decision is
recorded before dispatch.

## Planned GA Behavior

When `v0.8.0` GA is cut, `latest` should move from `0.8.0-beta.0` to
`0.8.0` through the documented GitHub CD path.

The beta dist-tag may remain pinned to `0.8.0-beta.0` for reproducible
installation of the beta line.

## Manual Recovery

If a dist-tag points at the wrong version:

1. Do not delete or reuse the published version.
2. Record the observed registry state.
3. Use the dedicated npm-management path to move the dist-tag back to the
   intended version.
4. Add a release-note or validation entry explaining the correction.

Direct local `npm dist-tag add`, `npm dist-tag rm`, or `npm publish` commands
are not the normal release path.
