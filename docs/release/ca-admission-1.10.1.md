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
| 1 | Written maintainer decision defining the controlled audience | **BLOCKED** | `[MAINTAINER DECISION REQUIRED]` — record who the controlled audience is. |
| 2 | Written install path that does not accidentally move npm `latest` | **MET** | [`npm-dist-tag-policy.md`](npm-dist-tag-policy.md) (Default Rules; "RC must not move latest"); install commands in [`v1.10.1.md`](../release-notes/v1.10.1.md). |
| 3 | Clean-environment install smoke for the selected version | **READY (pending cut)** | `ca-postpublish-verify` workflow → `py-registry-smoke` / `ts-registry-smoke` jobs; scripts `scripts/release/ca_registry_smoke.{py,mjs}`. Run after 1.10.1 publishes; paste run URL here. |
| 4 | Verifier conformance + cross-SDK roundtrip for the selected version | **READY (pending cut)** | Same workflow → `cross-sdk-roundtrip` job (Python-built bundle verified by the npm package and vice versa) plus each SDK's build/verify/tamper smoke. Source conformance is byte-frozen in CI and the wheel is the reproducible byte-identical build of that source. Paste run URL here. |
| 5 | Release notes stating CA is not GA / not production / not regulatory / not legal-compliance | **MET** | [`v1.10.1.md` → Explicit Boundaries](../release-notes/v1.10.1.md). |
| 6 | Rollback owner and registry correction path | **PARTIAL** | Correction path: [`npm-dist-tag-policy.md` → Manual Recovery](npm-dist-tag-policy.md). Owner: `[MAINTAINER DECISION REQUIRED]`. |

## Scope Notes (no silent caps)

- Criterion #4 evidence is a **focused public-surface roundtrip** against the
  installed packages (build → verify → tamper-reject, and a bundle produced by
  one SDK verified by the other), not a re-run of the full byte-frozen
  conformance vector suite on the wheel. The vectors are not shipped in the
  package; the full suite runs against source in CI, and the published artifact
  is the reproducible byte-identical build of that source. This scope boundary
  is intentional and disclosed rather than implied as full conformance.
- The `ca-postpublish-verify` workflow is **read-only** (`permissions:
  contents: read`, no registry token/OIDC, never publishes or moves a
  dist-tag). It cannot run green until `1.10.1` is published via `release-cd`.

## Go / No-Go

Not admissible until #1 (audience) and #6 (rollback owner) are recorded by the
maintainer, and #3/#4 run green against the published `1.10.1` (run URLs
pasted above). #2 and #5 are met.
