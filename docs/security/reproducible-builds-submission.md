<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# reproducible-builds.org — listing submission draft

This document is the pre-prepared submission text for adding
Attestplane to the
[reproducible-builds.org](https://reproducible-builds.org/) public
projects directory. The submission itself is a community merge request
to the upstream website source repository on Salsa (Debian's GitLab),
[`reproducible-builds/reproducible-website`](https://salsa.debian.org/reproducible-builds/reproducible-website)
(linked from [reproducible-builds.org/contribute/](https://reproducible-builds.org/contribute/)
under "Patches for this website welcome via our Git repository") — or
its current `_projects/` directory equivalent; this file holds the
prepared text so the maintainer can submit when ready.

## Scope of this document

This PR adds the submission **text only**. It does not open the
upstream r-b.org PR; that step is a maintainer follow-up after this
file is merged. The submission cadence and the project's verification
posture are described below for the upstream reviewer's convenience.

## Submission fields

| Field | Value |
|-------|-------|
| Project name | Attestplane |
| Repository | `https://github.com/attestplane/attestplane/` |
| License | Apache-2.0 |
| Contact | `security@attestplane.com` (institutional channel — see [`SECURITY.md`](../../SECURITY.md)) |
| Project description | Verifiable audit substrate for AI agents. Apache-2.0. Pre-GA (v1.0 GA target 2026-08-15 per `SECURITY.md`). |
| Reproducibility status | Active — two-runner byte-equivalence enforced in CI on every push to `main` |
| Verification cadence | Per-push and per-PR (path-filtered to `sdk/python/**`) |
| Languages / artifact types | Python pure-Python wheel (`py3-none-any`); TypeScript SDK reproducibility tracked separately |

## Reproducibility status (verbatim, for submission)

> Attestplane runs a `reproducible-build` workflow at
> [`.github/workflows/reproducible-build.yml`](../../.github/workflows/reproducible-build.yml).
> The workflow builds the Python wheel on two independent runner images
> (`ubuntu-latest` and `macos-latest`), computes SHA-256 of each
> wheel, and fails CI if the two hashes differ. Two independent OSes
> producing byte-identical wheel bytes is the audit signal targeted
> here.
>
> The check has been enforced on every push to `main` since the
> workflow landed in the v1.0.x pre-GA line. The reproducibility claim
> applies to the v1.0.x tag line forward; earlier release lines
> (`0.7.x`, `0.8.x`) are not retroactively verified.

## Tooling and approach

| Element | Value |
|---------|-------|
| Source date | `SOURCE_DATE_EPOCH` derived from `HEAD` commit timestamp (`git log -1 --pretty=%ct HEAD`) |
| Python runtime | `uv venv --python 3.12` (pinned via `astral-sh/setup-uv`, SHA-pinned) |
| Build backend | `hatchling` via `python -m build --wheel` |
| Artifact hash | SHA-256 over the built wheel(s), compared across runners |
| Action pinning | All third-party actions in the reproducible-build workflow pinned by full commit SHA |
| Concurrency | Per-workflow / per-ref cancellation to avoid stale parallel runs |

## Framing — evidence-supporting, not compliance certification

Reproducible builds are framed in Attestplane's project documentation
as **evidence-supporting infrastructure**, not as a compliance
certification:

- The reproducible-builds.org listing, if accepted, records that the
  project participates in the reproducible-builds ecosystem. It is a
  process matter, not a conformity assessment.
- The byte-equivalence check is a release-hygiene control. It
  contributes to the SLSA Build L3 provenance recorded since
  v1.0.9 per
  [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md), but
  it is not itself a SLSA certification.
- The AIA-12 *aligned* profile recorded in
  [`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md)
  is unaffected by this listing.

## Maintainer follow-up action items

The maintainer's submission steps (to be performed after this prep doc
merges, when ready — no date promised here):

1. Fork
   [`reproducible-builds/reproducible-website`](https://salsa.debian.org/reproducible-builds/reproducible-website)
   on Salsa (Debian's GitLab — sign-up via
   [reproducible-builds.org/contribute/salsa/](https://reproducible-builds.org/contribute/salsa/)).
2. Add a `_projects/attestplane.md` (or whatever path the upstream
   layout currently expects — verify against the
   `CONTRIBUTING.md` / `README.md` of the upstream repo at submission
   time, since their `_projects/` directory layout has evolved).
3. Populate the front-matter and body using the **Submission fields**
   and **Reproducibility status** sections above verbatim.
4. Open the PR from the project's contributing identity
   (`@merchloubna70-dot`, DCO-signed per
   [`CONTRIBUTING.md`](../../CONTRIBUTING.md)).
5. Link the upstream PR back here when filed, and link the merged
   listing once accepted.

## When to revisit

- **At v1.0 GA cut (target 2026-08-15 per `SECURITY.md`).** The GA cut
  is the natural moment to confirm the upstream listing is still
  accurate and that the wheel-byte-equivalence claim remains in
  force on the GA tag.
- **If the reproducible-build workflow changes meaningfully** (added
  artifact types, new platforms, new build backend), update both this
  document and the upstream listing.

## Out of scope for this PR

- The actual upstream merge request to
  `reproducible-builds/reproducible-website` (on Salsa) —
  a maintainer task afterwards, not in this PR.
- TypeScript SDK reproducible-build coverage — currently tracked
  separately; the upstream listing covers only what the workflow
  actually enforces today (Python wheel).
- Retroactive verification of `0.7.x` / `0.8.x` lines — explicitly out
  of scope.

## Non-claim

Inclusion in the reproducible-builds.org listing, if accepted, is a
**process matter, not a compliance certification**. It does not
constitute SLSA Build L3 self-attestation, EU AI Act Article 12
logging conformance, CRA 2027 readiness, or any regulatory
determination. The substrate's pre-GA boundary (per
[`SECURITY.md`](../../SECURITY.md)) is unaffected by the listing
outcome.
