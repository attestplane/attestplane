# GA and CA Cut Criteria

This document records the minimum criteria for moving Attestplane from the
`v0.8.x-rc` line to a wider availability channel.

It is intentionally a decision checklist, not an implementation script. Package
publication must continue to run through GitHub `release-cd`.

## Current Decision (2026-06-07, supersedes the 2026-05-20 v0.8.5 record below)

The version scheme has advanced from the `v0.8.x` line to the `v1.x` pre-GA
line; the current released version on all channels is `v1.10.0`. The `v0.8.x`
line is **no longer supported** (see `SECURITY.md`).

Decision recorded on 2026-06-07: `ca` continues to mean **Controlled
Availability** and is **repointed from the unsupported `0.8.5` to the current
supported pre-GA version `1.10.0`**. CA remains a manual, maintainer-controlled
npm dist-tag decision, separate from `latest`. As before, CA is **not** GA,
**not** a production-readiness claim, and **not** a regulatory or
legal-compliance certification.

Everything below this section (RC ordinals, evidence cuts, dist-tag examples
anchored to `0.8.5`) is retained as the **historical 2026-05-20 record** and is
superseded by this section for any current cut. When executing a CA/GA cut on
the `v1.x` line, substitute the current version for the `0.8.x` examples and run
the same classes of evidence checks.

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

Decision recorded on 2026-05-20: `ca` means **Controlled Availability** for
`v0.8.5`. It is not GA/stable in the product-readiness sense, but it uses the
suffix-free stable package version `0.8.5`. The maintainer explicitly decided
that default PyPI and npm installs should advance to `0.8.5`, and that npm
should expose both `latest` and `ca` dist-tags for the package.

If a future decision is GA, the release may move npm `latest` only when the
maintainer explicitly records that GA default installs should advance from the
current CA line.

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

The current npm default install path is intentionally moved to the CA line:

- `latest`: `0.8.5`
- `ca`: `0.8.5`
- `beta`: `0.8.0-beta.0`
- `rc`: `0.8.5-rc.5`

Moving `latest` to a stable version is a consumer-facing decision. For
`v0.8.5`, maintainers selected Controlled Availability and explicitly allowed
default npm installs to resolve to `0.8.5`.

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
