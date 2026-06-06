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

As of 2026-06-07 (supersedes the historical `0.8.5` record below):

- `latest`: `1.10.0`
- `ca`: repointed to `1.10.0`

`latest` advanced with the `v1.x` pre-GA line. `ca` (Controlled Availability)
is a separate, manual maintainer dist-tag decision; it was **repointed from the
unsupported `0.8.5` to the current supported `1.10.0`** so that
`npm install @attestplane/attestplane@ca` resolves to a supported version. See
`docs/release/ga-ca-cut-criteria.md` (2026-06-07 decision).

This does not change the claim boundary:

- `1.10.0` is Controlled Availability / pre-GA, not GA.
- `1.10.0` is not a production-readiness claim.
- `1.10.0` is not a regulatory certification or legal-compliance claim.

### Historical record (2026-05-20)

`@attestplane/attestplane@0.8.5` previously owned both `latest` and `ca`, an
explicit maintainer decision made after the `v0.8.5-rc.5` evidence gate. The
`0.8.x` line is now no longer supported (see `SECURITY.md`); retained here for
provenance.

The beta dist-tag may remain pinned to `0.8.0-beta.0` for reproducible
installation of the beta line.

## RC Behavior

The latest RC evidence cut, `v0.8.5-rc.5`, publishes as:

- npm version: `0.8.5-rc.5`
- npm dist-tag: `rc`

The current RC patch line may advance through `0.8.5-rc.10`. If another RC is
needed after that, the next npm version must be `0.8.6-rc.1` and the PyPI
version must be `0.8.6rc1`; do not publish `0.8.5-rc.11`.

RC releases must not move `latest` unless a separate maintainer decision is
recorded before dispatch. The recorded maintainer decision for `v0.8.5` moves
`latest` only for the suffix-free stable package version.

## Controlled Availability Behavior

`v0.8.5` is a Controlled Availability cut, not GA. It uses the stable package
version because `ca` is an availability channel, not a SemVer suffix.

- `latest` moves to `0.8.5` through the documented GitHub CD path so default
  npm installs use the CA package.
- `ca` points to `0.8.5` as an explicit channel marker.
- `rc` remains pinned to the latest RC evidence package, currently
  `0.8.5-rc.5`.

The GA/CA checklist is recorded in [`ga-ca-cut-criteria.md`](ga-ca-cut-criteria.md).

## Manual Recovery

If a dist-tag points at the wrong version:

1. Do not delete or reuse the published version.
2. Record the observed registry state.
3. Use the dedicated npm-management path to move the dist-tag back to the
   intended version.
4. Add a release-note or validation entry explaining the correction.

Direct local `npm dist-tag add`, `npm dist-tag rm`, or `npm publish` commands
are not the normal release path.
