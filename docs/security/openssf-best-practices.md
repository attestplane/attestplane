<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# OpenSSF Best Practices Badge — passing-tier self-assessment

Attestplane is registered as project **12924** in the
[OpenSSF Best Practices Badge Program](https://www.bestpractices.dev/projects/12924/).
On 2026-05-21 the project reached the **passing** tier
(`badge_level: passing`, `badge_percentage_0: 100`) with the silver tier
at 15% and the gold tier at 13%.

This document mirrors the on-disk self-assessment artifact
[`/.bestpractices.json`](../../.bestpractices.json), provides a single
human-readable reference for downstream auditors, and links each
criterion's evidence back into this repository so the badge can be
verified offline against the source tree at any tagged release.

## Scope and explicit non-claims

- **AIA-12 *aligned* profile.** The project's positioning, recorded in
  [`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md),
  is *Article 12-aligned audit substrate*. The OpenSSF passing badge
  does **not** convert that framing into a compliance certification, a
  conformity assessment, or any other regulatory determination.
- **Forward-only signing.** Per
  [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md),
  Sigstore keyless cosign signatures and SLSA Build L3 provenance
  apply only to releases cut after the ADR; pre-ADR tags are not
  retroactively signed.
- **SLSA L3 attribution.** The SLSA Build L3 claim attached to release
  provenance originates from the upstream pinned
  `slsa-framework/slsa-github-generator`, not from project
  self-attestation.
- **Pre-GA SLAs.** The vulnerability response timelines published in
  [`SECURITY.md`](../../SECURITY.md) apply from v1.0 GA
  (target 2026-08-15) onwards; pre-GA cadence is best-effort triage
  on the same target intervals.
- **No real-name attribution.** The project's maintainer-of-record
  pointer is the GitHub handle `@merchloubna70-dot`. No additional
  personal identifier is exposed by this badge or by the
  `.bestpractices.json` self-assessment.

## Active-tier summary

| Tier     | Status       | Percentage |
|----------|--------------|-----------|
| Passing  | **achieved** | 100%      |
| Silver   | in progress  | 15%       |
| Gold     | in progress  | 13%       |

The badge dashboard at
[bestpractices.dev/projects/12924](https://www.bestpractices.dev/projects/12924/)
is the authoritative record. This document is a mirror that travels
with the source.

## Authority and update flow

- The `/.bestpractices.json` file in the repository root is the
  durable, version-controlled self-assessment. It is read by the
  OpenSSF Autofill detective on each form-load with the
  `?reanalyze` parameter, and serves as the canonical record of
  every criterion's status and justification.
- Pull requests that change a criterion's recorded answer MUST update
  `/.bestpractices.json` and SHOULD update this document. The two
  artifacts MUST agree at every merged commit.
- When OpenSSF's GitHub-scan detective auto-injects justification
  text (a "Non-trivial X file found" pattern), that auto-text wins
  on the dashboard regardless of `.bestpractices.json`. To preserve
  project-authored wording, the maintainer manually pastes the
  desired justification on the OpenSSF edit form. The
  `.bestpractices.json` value remains the durable source.

## Passing-tier evidence by section

The passing tier covers 67 criteria across six sections. The full
justifications are in `.bestpractices.json`; the table below points
each Met or N/A claim back at the in-repo evidence file or workflow.

### Basics (13 / 13 Met)

| Criterion | Evidence |
|---|---|
| `description_good` | [README.md](../../README.md) |
| `interact` | [CONTRIBUTING.md](../../CONTRIBUTING.md), Issues, Discussions |
| `contribution` | [CONTRIBUTING.md](../../CONTRIBUTING.md) |
| `contribution_requirements` | [CONTRIBUTING.md §4 PR Checklist](../../CONTRIBUTING.md) |
| `floss_license` | [LICENSE](../../LICENSE) (Apache-2.0) |
| `floss_license_osi` | Apache-2.0 is OSI-approved |
| `license_location` | [LICENSE](../../LICENSE) + [LICENSES/](../../LICENSES) per REUSE 3.3 |
| `documentation_basics` | [README.md](../../README.md) + [docs/](../) tree |
| `documentation_interface` | [sdk/python/README.md](../../sdk/python/README.md), [sdk/typescript/README.md](../../sdk/typescript/README.md), [docs/spec/](../spec/) |
| `sites_https` | attestplane.io, github.com, pypi.org, npmjs.com all HTTPS-only |
| `discussion` | GitHub Issues, Discussions |
| `english` | Primary docs in English; `CONTRIBUTING_zh.md` is a translation |
| `maintained` | [Commit history](https://github.com/attestplane/attestplane/commits/main/); v1.0 GA targeted 2026-08-15 |

### Change Control (9 / 9 Met)

| Criterion | Evidence |
|---|---|
| `repo_public` | github.com/attestplane/attestplane |
| `repo_track` | Full git history; DCO sign-off required on PRs |
| `repo_interim` | Conventional Commits; atomic per-feature commits |
| `repo_distributed` | git on GitHub |
| `version_unique` | Each release tag unique; v0.0.x → v1.0.x |
| `version_semver` | [CHANGELOG.md](../../CHANGELOG.md) declares SemVer 2.0 |
| `version_tags` | `vX.Y.Z` annotated tags; [ADR-0017](../adr/0017-github-actions-release-cd.md) |
| `release_notes` | [CHANGELOG.md](../../CHANGELOG.md) (Keep a Changelog 1.1) |
| `release_notes_vulns` | [SECURITY.md](../../SECURITY.md) coordinated disclosure policy |

### Reporting (8 / 8 Met)

| Criterion | Evidence |
|---|---|
| `report_process` | [CONTRIBUTING.md](../../CONTRIBUTING.md), [SECURITY.md](../../SECURITY.md) |
| `report_tracker` | GitHub Issues |
| `report_responses` | Issue triage cadence in recent activity |
| `enhancement_responses` | Feature requests in Issues + Discussions |
| `report_archive` | GitHub Issues archive |
| `vulnerability_report_process` | [SECURITY.md](../../SECURITY.md) §Reporting a Vulnerability |
| `vulnerability_report_private` | [SECURITY.md](../../SECURITY.md): email + GitHub Security Advisories |
| `vulnerability_report_response` | [SECURITY.md](../../SECURITY.md) §Response Timeline (v1.0 GA onwards) |

### Quality (13 / 13 Met)

| Criterion | Evidence |
|---|---|
| `build`, `build_common_tools`, `build_floss_tools` | [CONTRIBUTING.md §2](../../CONTRIBUTING.md); hatchling + uv + npm |
| `test`, `test_invocation`, `test_most` | [sdk/python/tests/](../../sdk/python/tests), [sdk/typescript/test/](../../sdk/typescript/test), `scripts/test-cross-sdk-roundtrip.sh` |
| `test_continuous_integration` | [.github/workflows/ci.yml](../../.github/workflows/ci.yml) |
| `test_policy`, `tests_are_added`, `tests_documented_added` | [CONTRIBUTING.md §3-4](../../CONTRIBUTING.md), [ADR template](../adr/0000-template.md) |
| `warnings`, `warnings_fixed`, `warnings_strict` | ruff + mypy `--strict`, biome, codespell, typos, yamllint, markdownlint, actionlint, shellcheck, REUSE — all CI-enforced |

### Security (16 — 13 Met + 3 N/A)

| Criterion | Status | Evidence |
|---|---|---|
| `know_secure_design`, `know_common_errors` | Met | [SECURITY.md](../../SECURITY.md) threat categories |
| `crypto_published`, `crypto_call`, `crypto_floss` | Met | SHA-256 (FIPS 180-4), Ed25519 (RFC 8032), RFC 3161, Sigstore/cosign |
| `crypto_keylength` | Met | [ADR-0005](../adr/0005-event-signing-scheme.md), [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md) |
| `crypto_working`, `crypto_weaknesses` | Met | No broken or weakening primitives; pre-GA, no third-party cryptanalysis audit |
| `crypto_pfs` | **N/A** | Evidence-substrate primitives, not a TLS-terminating network service |
| `crypto_password_storage` | **N/A** | Project does not store user passwords; auth delegated to operator gateways |
| `crypto_random` | Met | OS CSPRNG via pyca/cryptography (`secrets`, `os.urandom`) and `crypto.randomBytes` |
| `delivery_mitm` | Met | HTTPS-only distribution (PyPI / npm / GitHub Releases) |
| `delivery_unsigned` | Met | [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md): Sigstore keyless + SLSA Build L3 (forward-only) |
| `vulnerabilities_fixed_60_days`, `vulnerabilities_critical_fixed` | Met | [SECURITY.md §Response Timeline](../../SECURITY.md) (v1.0 GA onwards) |
| `no_leaked_credentials` | Met | OSV-Scanner daily; gitleaks in [invariants.yml](../../.github/workflows/invariants.yml); org-level secret-scanning push-protection |

### Analysis (8 — 7 Met + 1 N/A)

| Criterion | Status | Evidence |
|---|---|---|
| `static_analysis`, `static_analysis_common_vulnerabilities`, `static_analysis_fixed`, `static_analysis_often` | Met | [codeql.yml](../../.github/workflows/codeql.yml), [osv-scanner.yml](../../.github/workflows/osv-scanner.yml), [scorecard.yml](../../.github/workflows/scorecard.yml) |
| `dynamic_analysis`, `dynamic_analysis_enable_assertions`, `dynamic_analysis_fixed` | Met | Hypothesis property tests, [mutation.yml](../../.github/workflows/mutation.yml), `scripts/check-fault-injection.sh` |
| `dynamic_analysis_unsafe` | **N/A** | Load-bearing code is Python and TypeScript (memory-safe); no unsafe memory operations in scope |

## Verification

The badge SVG on the [project page](https://www.bestpractices.dev/projects/12924/)
is updated automatically by the OpenSSF dashboard whenever an
authorized maintainer edits the project on
[bestpractices.dev](https://www.bestpractices.dev/). For offline
verification, the durable source is
[`/.bestpractices.json`](../../.bestpractices.json) at the relevant
git tag.

## Roadmap toward higher tiers

Silver and gold add criteria around external auditing, supply-chain
controls, cryptographic agility, dependency-pinning practice,
multi-factor authentication enforcement, and signed releases. The
forward-looking work items most likely to advance the silver tier
include:

- Closing the cosign keyless signing + SLSA provenance loop on a
  real release tag (the workflow exists per ADR-0018; the first
  signed release will land alongside v1.0 GA).
- Publishing a GPG key for `security@attestplane` (planned for v1.0
  GA per SECURITY.md).
- Reconciling [SECURITY.md](../../SECURITY.md) "Supported Versions"
  to the current v1.0.x line.
- A third-party (or community) cryptanalysis review pass.

This document is the place to record those events as they land.
