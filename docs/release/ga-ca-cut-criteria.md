# GA and CA Cut Criteria

This document records the minimum criteria for moving Attestplane from the
`v0.8.x-rc` line to a wider availability channel.

It is intentionally a decision checklist, not an implementation script. Package
publication must continue to run through GitHub `release-cd`.

## Naming Decision

`ca` is not a SemVer, npm, or PEP 440 release-stage identifier. Do not publish
versions such as `0.8.5-ca.1` or `0.8.5ca1`.

Before any CA or GA cut, maintainers must record which meaning is intended:

- **GA / stable**: publish the stable version without a prerelease suffix, for
  example `v0.8.5`, PyPI `0.8.5`, and npm `0.8.5`.
- **Controlled Availability / Customer Availability**: keep the version on the
  existing RC or stable version scheme, and express CA through release notes,
  documentation, and an optional registry/channel tag. Do not encode `ca` in
  the version string.

If the decision is GA, the release may move npm `latest` only when the
maintainer explicitly records that default npm installs should advance from the
current beta line.

## Current RC Rule

The current RC patch line is `v0.8.5-rc.N`.

- Valid ordinals are `v0.8.5-rc.1` through `v0.8.5-rc.10`.
- If more RCs are needed after `v0.8.5-rc.10`, continue with
  `v0.8.6-rc.1`; do not publish `v0.8.5-rc.11`.
- Skipping the remaining RC ordinals requires an explicit maintainer waiver
  that records the reason and the replacement validation evidence.

## Required Evidence Before GA

The following checks must pass before a stable `v0.8.5` cut:

1. `release-cd` dry-run passes for the exact commit that will be tagged.
2. The latest RC is visible on both registries:
   - PyPI: `attestplane==0.8.5rcN`
   - npm: `@attestplane/attestplane@0.8.5-rc.N`
3. Clean-environment install smoke passes from both registries.
4. Verifier conformance passes against the released package.
5. Cross-SDK roundtrip passes against the released package.
6. Negative conformance cases pass, including tampered bundle,
   version-skew, malformed policy-trace reference, and missing-event cases.
7. Package metadata is checked for version, license, homepage, repository, and
   artifact manifest consistency.
8. Release notes summarize RC-to-GA changes and repeat the claim boundary.
9. Rollback steps are reviewed for npm dist-tag correction and PyPI yank.
10. Release permissions are reviewed so registry publishing remains scoped to
    GitHub `release-cd`.

## Required Evidence Before Controlled Availability

Controlled Availability may be used before GA only if the project still avoids
stable or production-readiness claims. The minimum evidence is:

1. A written maintainer decision defining who the controlled audience is.
2. A written install path that does not accidentally move npm `latest` unless
   that is explicitly intended.
3. Clean-environment install smoke for the selected package version.
4. Verifier conformance and cross-SDK roundtrip for the selected package
   version.
5. Release notes stating that CA is not GA, not production readiness, not a
   regulatory certification, and not a legal-compliance claim.
6. A rollback owner and registry correction path.

## npm Latest Decision

The current npm default install path is intentionally pinned to the beta line:

- `latest`: `0.8.0-beta.0`
- `beta`: `0.8.0-beta.0`
- `rc`: latest published `0.8.5-rc.N`

Moving `latest` to a stable version is a consumer-facing decision. It must be
recorded before dispatching a stable release, because it changes what
`npm install @attestplane/attestplane` resolves to by default.

Prerelease RC packages must continue to publish under `rc` and must not move
`latest`.

## Release Notes Requirements

Before a stable or CA cut, release notes must include:

- the selected channel and version;
- changes since the previous beta or RC;
- the npm dist-tag decision;
- PyPI and npm installation commands;
- verification commands used for clean-environment smoke;
- rollback contacts and registry correction steps;
- explicit non-claims for production readiness, legal certification,
  regulatory compliance, certified provenance, and SLSA L3 unless separate
  evidence exists.

## No-Go Conditions

Do not cut GA or CA when any of the following is true:

- `ca` has not been defined as either GA/stable or Controlled Availability.
- The npm `latest` decision is missing for a stable release.
- The selected RC is not visible on PyPI or npm.
- Clean-environment install smoke has not run.
- Verifier conformance or cross-SDK roundtrip is missing or failing.
- Rollback ownership is unclear.
- Registry publishing can be reached from PR or fork workflows.
- GitHub `release-cd` is not the publication entrypoint.
