# CA Admission Evidence — v1.10.1

This document records the Controlled Availability admission evidence for the
`v1.10.1` cut against the six criteria in
[`ga-ca-cut-criteria.md` → Required Evidence Before Controlled Availability](ga-ca-cut-criteria.md).
It is a per-cut go/no-go snapshot, separate from the long-lived rules document.

**CA is not GA, not a production-readiness claim, not a regulatory
certification, and not a legal-compliance claim.** Recording this evidence does
not assert any of those.

## Why 1.10.1 (not 1.10.0)

The published `1.10.0` packages fail the clean-install version guard: both SDKs
self-report `1.8.4` (a hand-maintained version literal the release train never
bumped — `attestplane.__version__` / CLI on PyPI, `VERSION` on npm). The wheel
is immutable, so CA admits the re-cut `1.10.1`, which ships the version
single-source-of-truth fix (PR #621) and self-reports correctly. See
[`../release-notes/v1.10.1.md`](../release-notes/v1.10.1.md).

## Criteria Status

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Written maintainer decision defining the controlled audience | **PROPOSED** | Draft in [§ Controlled Audience](#controlled-audience-proposed); awaiting maintainer ratification (edit or accept). |
| 2 | Written install path that does not accidentally move npm `latest` | **MET** | [`npm-dist-tag-policy.md`](npm-dist-tag-policy.md) (Default Rules; "RC must not move latest"); install commands in [`v1.10.1.md`](../release-notes/v1.10.1.md). |
| 3 | Clean-environment install smoke for the selected version | **READY (pending cut)** | `ca-postpublish-verify` workflow → `py-registry-smoke` / `ts-registry-smoke` jobs; scripts `scripts/release/ca_registry_smoke.{py,mjs}`. Run after 1.10.1 publishes; paste run URL here. |
| 4 | Verifier conformance + cross-SDK roundtrip for the selected version | **READY (pending cut)** | Same workflow → `cross-sdk-roundtrip` job (Python-built bundle verified by the npm package and vice versa) plus each SDK's build/verify/tamper smoke. Source conformance is byte-frozen in CI and the wheel is the reproducible byte-identical build of that source. Paste run URL here. |
| 5 | Release notes stating CA is not GA / not production / not regulatory / not legal-compliance | **MET** | [`v1.10.1.md` → Explicit Boundaries](../release-notes/v1.10.1.md). |
| 6 | Rollback owner and registry correction path | **PARTIAL** | Correction path fully documented ([`npm-dist-tag-policy.md` → Manual Recovery](npm-dist-tag-policy.md)). Owner role/path filled in [§ Rollback Owner](#rollback-owner); only the literal name is `[NAME REQUIRED]`. |

> Merging this PR does **not** make 1.10.1 admissible. #1 is a *proposed* draft
> the maintainer must ratify (or edit), and #6 still needs the owner's name;
> both are hard blockers, not post-merge TODOs. The remaining maintainer-only
> steps are listed in [§ Remaining Maintainer Actions](#remaining-maintainer-actions).

## Scope Notes (no silent caps)

- Criterion #4 evidence is a **focused public-surface roundtrip** against the
  installed packages (build → verify → tamper-reject, and a bundle produced by
  one SDK verified by the other), not a re-run of the full byte-frozen
  conformance vector suite on the wheel. The vectors are not shipped in the
  package; the full suite runs against source in CI, and the published artifact
  is the reproducible byte-identical build of that source — the byte-identity
  is itself a CI signal (the `reproducible-build` workflow's "Two independent
  runners produced byte-identical wheel" job). This scope boundary is
  intentional and disclosed rather than implied as full conformance.
- The `ca-postpublish-verify` workflow is **read-only** (`permissions:
  contents: read`, no registry token/OIDC, never publishes or moves a
  dist-tag). It cannot run green until `1.10.1` is published via `release-cd`.

## Controlled Audience (proposed)

> **Status: proposed default, pending maintainer ratification.** Edit or accept
> this text; the decision is the maintainer's. It is written here so #1 is a
> concrete decision to ratify rather than a blank.

attestplane is openly published under Apache-2.0 on PyPI and npm, so
"controlled" here does **not** mean access restriction — anyone can install the
package. The control is the **opt-in channel and the explicit pre-GA boundary**:

- The controlled audience is integrators who **explicitly opt in** to the CA
  line for **pre-GA evaluation and integration** of the audit substrate. On npm
  this opt-in is the `ca` dist-tag (`npm install @attestplane/attestplane@ca`).
  PyPI has no dist-tag concept, so there the opt-in is an **informed version
  pin** (`pip install attestplane==1.10.1`) plus the pre-GA boundary that
  travels with the release note — not a channel gate.
- CA is **not** offered as a GA default, a production-readiness signal, or any
  regulatory/legal-compliance posture; those boundaries travel with the release
  note ([`v1.10.1.md`](../release-notes/v1.10.1.md)).
- The default `latest` install resolving to this version reflects the openly
  published pre-GA line, not a production-readiness recommendation.

**Ratification:** to satisfy criterion #1 (a *written maintainer decision*),
the maintainer records their name/handle and the date here when accepting or
editing the above — flipping the status alone is not the decision:

- Ratified by: `[MAINTAINER NAME/HANDLE]` on `[DATE]`.

## Rollback Owner

- **Correction path** (done): [`npm-dist-tag-policy.md` → Manual
  Recovery](npm-dist-tag-policy.md) — do not delete/reuse a published version;
  record the observed registry state; move the `ca`/`latest` dist-tag back
  through the `manage-npm` path; add a release-note/validation entry. PyPI
  versions are immutable and are superseded by the next patch.
- **Owner**: the release maintainer who dispatches `release-cd` / `manage-npm`.
  Recorded name: `[NAME REQUIRED]`.

## Remaining Maintainer Actions

Everything automatable is done and merged. These steps are maintainer-only
(business decision, named accountability, and the consumer-facing publish):

1. **Ratify #1** — accept or edit § Controlled Audience above.
2. **Record #6 owner** — replace `[NAME REQUIRED]` with the rollback owner.
3. **Cut 1.10.1** via `release-cd` (the only publish path). The version bump
   now propagates correctly (derived `__version__` / `VERSION`); `release-cd`
   will also reject any reintroduced hardcoded version literal.
4. **Verify the published packages** — dispatch the read-only workflow and
   paste the three run URLs into rows #3/#4:

   ```sh
   gh workflow run ca-postpublish-verify.yml -f version=1.10.1
   gh run list --workflow=ca-postpublish-verify.yml --limit 1   # copy the run URL
   ```

5. **Move dist-tags** (`latest` and `ca` → `1.10.1`) through the `manage-npm`
   path per [`npm-dist-tag-policy.md`](npm-dist-tag-policy.md).

## Go / No-Go

Not admissible until #1 is ratified and #6's owner name is recorded by the
maintainer, and #3/#4 run green against the published `1.10.1` (run URLs pasted
in the table). #2 and #5 are met; #1 is drafted pending ratification.
