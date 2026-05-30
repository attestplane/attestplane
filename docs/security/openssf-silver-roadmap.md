<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# OpenSSF Best Practices Badge — Silver-tier roadmap

Attestplane is OpenSSF Best Practices project
[**12924**](https://www.bestpractices.dev/en/projects/12924/passing). On
2026-05-20T21:04:10Z the project reached the **passing** tier at 100%.
This document is the forward-looking roadmap toward the **silver** tier,
which currently sits at **15%** per
[`https://www.bestpractices.dev/projects/12924/badge.json`](https://www.bestpractices.dev/projects/12924/badge.json).

> **This is a roadmap, not a self-assessment.** It maps every silver-tier
> criterion against the repository's current observed state, flags
> gaps honestly, and proposes advancement work that the maintainer can
> sequence at their discretion. It does **not** modify
> [`/.bestpractices.json`](../../.bestpractices.json), it does **not**
> claim Met for anything that does not already have evidence in the
> source tree, and it does **not** promise dates beyond the
> v1.0 GA target (2026-08-15) that is already published in
> [`SECURITY.md`](../../SECURITY.md).

---

## Status snapshot

| Tier     | Status       | Percentage | Source                                                                                  |
|----------|--------------|-----------:|-----------------------------------------------------------------------------------------|
| Passing  | **achieved** | 100%       | [bestpractices.dev/projects/12924](https://www.bestpractices.dev/en/projects/12924/passing)        |
| Silver   | in progress  | 15%        | [`bestpractices.dev/projects/12924/badge.json`](https://www.bestpractices.dev/projects/12924/badge.json) |
| Gold     | in progress  | 13%        | (out of scope for this document)                                                        |

Passing-tier evidence is mirrored in
[`docs/security/openssf-best-practices.md`](openssf-best-practices.md).
This silver-tier roadmap is its forward-looking counterpart.

---

## Scope and disclaimers

- **Roadmap, not certification.** Receiving the OpenSSF passing or
  silver badge is not a compliance certification, a conformity
  assessment, or any other regulatory determination. The AIA-12
  *aligned* framing in
  [`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md)
  is untouched by this document.
- **No date commitments beyond v1.0 GA.** Where future work is named
  (e.g. third-party cryptanalysis review, ISO/IEC 42001 crosswalk,
  EU AI Office submissions), this document does **not** promise a
  specific date. Those are governance decisions for the maintainer.
  The only schedule anchor used here is v1.0 GA = 2026-08-15, which
  is already published in [`SECURITY.md`](../../SECURITY.md).
- **No real-name exposure.** The project's maintainer-of-record
  pointer is the GitHub handle `@merchloubna70-dot`, and all DCO
  sign-off attribution flows through the GitHub privacy email.
- **Pre-GA reality.** The project is pre-v1.0; several silver
  criteria depend on artifacts that only land at the first signed
  release (cosign keyless + SLSA Build L3, GPG key publication for
  `security@attestplane.com`, response-timeline SLAs becoming
  binding rather than best-effort). The table below states this
  honestly per criterion.
- **Honest gaps.** Where a silver criterion is unmet, this document
  says so; where the evidence is partial, this document says so.
  No criterion is marked Met unless the repository already supports
  the claim.

---

## Silver-tier criteria — evidence and gap table

The criterion identifiers below match the
[OpenSSF criteria.yml](https://raw.githubusercontent.com/coreinfrastructure/best-practices-badge/main/criteria/criteria.yml)
silver level (top-level key `'1'`) and the project form at
[`bestpractices.dev/projects/12924/1`](https://www.bestpractices.dev/en/projects/12924/1).

State legend: **Met** = evidence already in tree; **partial** = some
evidence, gap noted; **unmet** = no evidence yet; **N/A** = not
applicable to this project's surface, with reason.

### Basics — Prerequisites

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `achieve_passing` | Met | Passing tier reached 2026-05-20T21:04:10Z per [`bestpractices.dev/projects/12924`](https://www.bestpractices.dev/en/projects/12924/passing); mirrored in [`docs/security/openssf-best-practices.md`](openssf-best-practices.md). | None. |

### Basics — Basic project website content

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `contribution_requirements` | Met | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §1 DCO + §4 PR Checklist enumerate test, lint, CHANGELOG, sign-off requirements. | None. |

### Basics — Project oversight

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `dco` (SHOULD) | Met | DCO 1.1 enforced per [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §1 and [`DCO.txt`](../../DCO.txt); GitHub DCO app required on PRs. | None. |
| `governance` | Met | [`GOVERNANCE.md`](../../GOVERNANCE.md) §1–§13: roles, lazy consensus + supermajority, license-permanence (§6), succession (§8), foundation-migration path (§12). | None. |
| `code_of_conduct` | Met | [`CODE_OF_CONDUCT.md`](../../CODE_OF_CONDUCT.md) adopts Contributor Covenant v2.1; enforcement process in [`GOVERNANCE.md`](../../GOVERNANCE.md) §11. | None. |
| `roles_responsibilities` | Met | [`GOVERNANCE.md`](../../GOVERNANCE.md) §2 (Roles), §3 (Maintainer Responsibilities), Appendix A. | None. |
| `access_continuity` | partial | [`GOVERNANCE.md`](../../GOVERNANCE.md) §8.3 Emergency Continuity Protocol + §8.4 Permanent Incapacity define the recovery path. §8.5 records "designate named emergency successor" as a required deliverable not yet executed. | Named successor entry is the open governance item; date is a maintainer governance call (target band noted in §8.5 is M6 / 2026-09-01, not re-promised here). |
| `bus_factor` (SHOULD) | unmet | Active-maintainer count is currently one. [`GOVERNANCE.md`](../../GOVERNANCE.md) §8.1 discloses sole-maintainer state; §8.5 lists "≥ 1 additional Maintainer candidate" as a future milestone. | Adding a second active maintainer is a governance / community-growth decision; no date promised here. |

### Basics — Documentation

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `documentation_roadmap` | Met | [`docs/roadmap/p3_release_roadmap.md`](../roadmap/p3_release_roadmap.md) and [`docs/roadmap/next_alpha_release_plan_20260519.md`](../roadmap/next_alpha_release_plan_20260519.md); v1.0 GA milestone in [`SECURITY.md`](../../SECURITY.md). | None. |
| `documentation_architecture` | Met | [`docs/architecture/`](../architecture/) tree (verifier independence, TSA provider interface, attestation gates, AIOS absorption map). ADRs 0001–0018 in [`docs/adr/`](../adr/). | None. |
| `documentation_security` | Met | [`SECURITY.md`](../../SECURITY.md), [`docs/security/threat-model-v0.0.5-alpha.md`](threat-model-v0.0.5-alpha.md), ADR-0005 (signing), ADR-0006 (Rekor), ADR-0018 (Sigstore + SLSA). | None. |
| `documentation_quick_start` | partial | [`README.md`](../../README.md) and `sdk/python/README.md` + `sdk/typescript/README.md` provide install + a minimal example; coverage of the auditor-API end-to-end happy path is incremental as M5 surfaces land. | Full end-to-end quick-start tracks the v1.0 GA API freeze; not a hard blocker, but the artifact will deepen with M5. |
| `documentation_current` | Met | Docs are updated within each release window; ADRs carry effective dates; [`CHANGELOG.md`](../../CHANGELOG.md) reflects pre-GA cadence. | None. |
| `documentation_achievements` | partial | Achievements list is informal: passing badge, REUSE-3.3 compliance, Scorecard workflow. No consolidated achievements page yet. | A low-touch "achievements" section in `README.md` or a new `docs/achievements.md` would close this — see low-hanging items. |

### Basics — Accessibility and internationalization

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `accessibility_best_practices` (SHOULD) | N/A | Project surface is a CLI + library SDKs (Python, TypeScript) + machine-consumed APIs. There is no end-user GUI inside this repository. | N/A justification recorded here. |
| `internationalization` (SHOULD) | partial | Strings are not localized; documentation has a Chinese translation pair ([`CONTRIBUTING.md`](../../CONTRIBUTING.md) + [`CONTRIBUTING_zh.md`](../../CONTRIBUTING_zh.md)) but no programmatic i18n framework. | Substrate output is structured data, not user-facing text; full i18n is low priority pre-GA. |

### Basics — Other

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `sites_password_security` | N/A | The project does not operate a public website with user accounts. `attestplane.io` / `attestplane.com` are static. The substrate itself delegates authentication to operator gateways per [`SECURITY.md`](../../SECURITY.md) Hardening Guidance §3. | N/A justification recorded here. |

### Change Control — Previous versions

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `maintenance_or_update` | Met | Pre-GA versioning per [`CHANGELOG.md`](../../CHANGELOG.md) (Keep a Changelog 1.1) and [`SECURITY.md`](../../SECURITY.md) "Supported Versions" table; v1.0 GA SLA applies forward from 2026-08-15. | None. |

### Reporting — Bug-reporting process

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `report_tracker` | Met | [GitHub Issues](https://github.com/attestplane/attestplane/issues/) is the public bug tracker; referenced from [`CONTRIBUTING.md`](../../CONTRIBUTING.md) and [`SECURITY.md`](../../SECURITY.md). | None. |

### Reporting — Vulnerability report process

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `vulnerability_report_credit` | Met | [`SECURITY.md`](../../SECURITY.md) §"Coordinated Disclosure" and §"Hall of Fame / Bug Bounty" commit to crediting reporters by name or handle (opt-out available); a dedicated `SECURITY_HALL_OF_FAME.md` is scheduled by [`SECURITY.md`](../../SECURITY.md) at M5. | None for the policy claim; the hall-of-fame file itself is a future artifact. |
| `vulnerability_response_process` | partial | [`SECURITY.md`](../../SECURITY.md) §"Response Timeline" publishes the acknowledgement / triage / fix windows. The 7-day, 14-day, 30/60/90-day SLAs apply from v1.0 GA onwards; pre-GA cadence is best-effort triage on the same target intervals. | Hardening from "target" to "binding SLA" lands at v1.0 GA. |

### Quality — Coding standards

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `coding_standards` | Met | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §2 declares the standards stack (ruff + mypy --strict, biome, codespell, typos, yamllint, markdownlint, actionlint, shellcheck, REUSE). | None. |
| `coding_standards_enforced` | Met | [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) and [`.github/workflows/invariants.yml`](../../.github/workflows/invariants.yml) enforce the stack on every PR. | None. |

### Quality — Working build system

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `build_standard_variables` | N/A | Builds are language-native (hatchling / uv for Python, npm + tsc for TypeScript); the C/C++ `CC`/`CFLAGS` convention does not apply. | N/A justification recorded here. |
| `build_preserve_debug` (SHOULD) | N/A | Same reason as `build_standard_variables`; Python and TypeScript distributions are not stripped binaries. | N/A justification recorded here. |
| `build_non_recursive` | Met | No recursive `make`; workspaces use language-native task runners. | None. |
| `build_repeatable` | partial | Pinned lockfiles (`poetry.lock`, `package-lock.json`, `Cargo.lock`), pinned action SHAs in CI, [`.github/workflows/reproducible-build.yml`](../../.github/workflows/reproducible-build.yml). Full bit-for-bit reproducibility across hosts is not yet asserted. | Bit-for-bit reproducibility is a future hardening; the criterion text requires only that the project itself can reproduce. |

### Quality — Installation system

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `installation_common` | Met | `pip install attestplane` and `npm install @attestplane/sdk` are the standard install paths per the SDK READMEs. | None. |
| `installation_standard_variables` | N/A | No POSIX `DESTDIR`-style installation; packages install into the Python / Node environment per language convention. | N/A justification recorded here. |
| `installation_development_quick` | Met | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §2 "Local Dev Setup" gives a single-page bring-up (Rust + Python + TypeScript). | None. |

### Quality — Externally-maintained components

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `external_dependencies` | Met | All dependencies are upstream OSS pulled via pinned manifests; no vendored copies of third-party code in the source tree. | None. |
| `dependency_monitoring` | Met | [`.github/workflows/osv-scanner.yml`](../../.github/workflows/osv-scanner.yml) runs daily; Dependabot enabled at the repo level per [`SECURITY.md`](../../SECURITY.md) "Supply-Chain Security Posture"; [`.github/workflows/scorecard.yml`](../../.github/workflows/scorecard.yml) weekly. | None. |
| `updateable_reused_components` | Met | Dependabot PRs land regularly; 48-hour cooldown policy per [`SECURITY.md`](../../SECURITY.md) is enforced via PR review. | None. |
| `interfaces_current` (SHOULD) | Met | Upstream SDK interfaces are tracked via pinned versions; deprecation handling is part of the dependency-bump checklist. | None. |

### Quality — Automated test suite

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `automated_integration_testing` | Met | [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) runs unit + integration; [`.github/workflows/cross-sdk-roundtrip.yml`](../../.github/workflows/cross-sdk-roundtrip.yml) exercises Python ↔ TypeScript byte-conformance. | None. |
| `regression_tests_added50` | partial | Every bug fix lands with a regression test per [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §3–4 red→green→refactor rhythm; ratio is not formally measured. | A short bug-to-test mapping note in `CONTRIBUTING.md` would let this move to Met. |
| `test_statement_coverage80` | partial | Coverage is collected in CI; precise repo-wide statement-coverage number is not currently asserted publicly. | A published coverage badge or coverage report referenced from README would close this. |

### Quality — New functionality testing

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `test_policy_mandated` | Met | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §3–4 mandates tests for new functionality; PR template enforces it. | None. |
| `tests_documented_added` | Met | Test-with-feature requirement documented in [`CONTRIBUTING.md`](../../CONTRIBUTING.md). | None. |

### Quality — Warning flags

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `warnings_strict` | Met | `mypy --strict`, `ruff` with strict ruleset, `biome` strict, `cargo clippy -D warnings` per [`CONTRIBUTING.md`](../../CONTRIBUTING.md) §2; all enforced in CI. | None. |

### Security — Secure development knowledge

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `implement_secure_design` | partial | [`docs/security/threat-model-v0.0.5-alpha.md`](threat-model-v0.0.5-alpha.md) and [`SECURITY.md`](../../SECURITY.md) "Threat Categories" enumerate the model; explicit per-principle mapping (least privilege, fail-secure defaults, defense in depth) is implicit in ADR text but not consolidated. | A short "Secure Design Principles" subsection in `SECURITY.md` linking each principle to its ADR / control would close this. |

### Security — Use basic good cryptographic practices

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `crypto_weaknesses` | Met | No SHA-1, no MD5, no DES, no CBC-mode SSH in the primitive set; SHA-256 + Ed25519 + RFC-3161 + Sigstore per [ADR-0005](../adr/0005-event-signing-scheme.md), [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md). | None. |
| `crypto_algorithm_agility` (SHOULD) | partial | The hash and signature schemes are abstracted behind interfaces (canonical-text v1 hash chain; pluggable TSA provider per [`docs/architecture/tsa-provider-interface.md`](../architecture/tsa-provider-interface.md)). A formal "algorithm rotation runbook" is not yet documented. | A short rotation playbook is a low-touch addition. |
| `crypto_credential_agility` | partial | Sigstore keyless avoids long-lived signing keys; GPG publication for `security@attestplane.com` is planned per [`SECURITY.md`](../../SECURITY.md) for v1.0 GA. | GPG publication is the gating future commitment; see "Items requiring future commitments". |
| `crypto_used_network` (SHOULD) | Met | HTTPS only for distribution and TSA traffic; no plaintext fallback. | None. |
| `crypto_tls12` (SHOULD) | Met | Distribution channels (PyPI, npm, GitHub) and TSA providers are TLS 1.2+ only; the substrate has no TLS-terminating server of its own pre-GA. | None. |
| `crypto_certificate_verification` | Met | Certificates are validated by the underlying TLS stack of `urllib3` / `node:https`; no `verify=False` paths. | None. |
| `crypto_verification_private` | Met | No proprietary verification paths; verification flows use FLOSS toolchains end-to-end. | None. |

### Security — Secure release

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `signed_releases` | Met | [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md) commits to Sigstore keyless cosign + SLSA Build L3 (forward-only). Tag `v1.0.9` is the first release whose assets carry the **complete** chain — both Sigstore keyless cosign bundles ([`sign-release.yml` execute run](https://github.com/attestplane/attestplane/actions/runs/26192598447)) and SLSA Build L3 provenance ([`slsa-provenance.yml` execute run](https://github.com/attestplane/attestplane/actions/runs/26192349031)) — attached to a single release. From the autorelease-sign-and-slsa-integration PR onward, the autodev-train (`scripts/release/stable_auto_train.py`) auto-dispatches both workflows with `execute=true` after registry visibility is confirmed, so every autodev-train tag inherits the complete chain without manual workflow dispatch; signing failures are tracked separately on `PublicationStatus` so they do not block the publication cycle. Both verify with `cosign verify-blob` against the workflow-pinned identity and with `slsa-verifier verify-artifact` against the upstream generator and source repo. Evidence in [`CHANGELOG.md`](../../CHANGELOG.md) "First complete signed release: v1.0.9" and [`docs/release/verifying-signatures.md`](../release/verifying-signatures.md) "Worked example: v1.0.9". Tag `v1.0.8` (the earlier "First signed release" entry) carries cosign bundles only because the SLSA generator pin fix ([PR #32](https://github.com/attestplane/attestplane/pull/32), reconciling [ADR-0018 §"Tag-ref vs SHA-pin caveat"](../adr/0018-keyless-signing-and-slsa-provenance.md)) merged after `v1.0.8` was signed; `v1.0.9` is the first tag cut after that fix landed. | None for the OpenSSF criterion. SLSA pin fix is now in tree and the autodev-train autorelease integration extends the complete chain to every new tag rather than only manually-triggered runs. |
| `version_tags_signed` (SUGGESTED) | unmet | Tags are annotated but not GPG-signed today. | GPG-signed tags depend on the GPG key publication tracked under "Items requiring future commitments". |

### Security — Other security issues

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `input_validation` | Met | Auditor-API input validation per the FastAPI / Pydantic surface; canonical-text v1 enforces strict structural validation at chain ingress per [ADR-0011](../adr/0011-canonical-text-v1.md). | None. |
| `hardening` (SHOULD) | Met | [`SECURITY.md`](../../SECURITY.md) "Hardening Guidance for Operators" (7 controls); CI uses pinned action SHAs; `permissions: read-all` baseline in workflows. | None. |
| `assurance_case` | partial | [`docs/security/threat-model-v1.md`](threat-model-v1.md) restructures the threat list as GSN-style claims → arguments → evidence (AT-01..AT-14) with explicit residuals; sibling artifacts ([ADR set](../adr/), [`docs/architecture/verifier_independence.md`](../architecture/verifier_independence.md)) are cited from §10. A consolidated `docs/security/assurance-case.md` aggregating non-threat claims (release, supply-chain, governance) remains future work. | Aggregating the non-threat-model claims into a single assurance-case document is the remaining step to lift this from partial to Met. |

### Analysis — Static code analysis

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `static_analysis_common_vulnerabilities` | Met | [`.github/workflows/codeql.yml`](../../.github/workflows/codeql.yml) runs CodeQL for Python + TypeScript with security-extended queries. | None. |

### Analysis — Dynamic code analysis

| Criterion | State | Evidence or gap | Blocker |
|---|---|---|---|
| `dynamic_analysis_unsafe` | N/A | Load-bearing code is Python and TypeScript (memory-safe). No unsafe memory operations in scope; no C/C++ that would require ASAN/MSAN. | N/A justification recorded here. |

---

## Low-hanging items (advanceable without major engineering)

These five-to-ten items are reachable through documentation work
already grounded in existing repository artifacts. Each one is a
**suggestion**, not a commitment, and lands by ordinary PR review.

1. **`documentation_achievements` — add a brief achievements page.**
   A short `docs/achievements.md` (or a `## Achievements` section in
   `README.md`) listing: OpenSSF passing badge, REUSE 3.3 SPDX headers
   in tree, OSSF Scorecard workflow, daily OSV-Scanner. Pure documentation.

2. **`access_continuity` (Met-leaning) — record named emergency successor
   when the maintainer designates one.** The recovery protocol is
   already documented in [`GOVERNANCE.md`](../../GOVERNANCE.md) §8.3.
   Once the maintainer names a successor (a governance decision, not a
   roadmap commitment), updating Appendix A and §8.2 closes the gap.

3. **`implement_secure_design` — add "Secure Design Principles" subsection
   to [`SECURITY.md`](../../SECURITY.md).** Map least-privilege,
   fail-secure-defaults, defense-in-depth, and minimize-attack-surface
   to existing ADRs and to the hardening guidance already published.

4. **`crypto_algorithm_agility` — document the hash/sign rotation
   playbook.** A short `docs/security/crypto-rotation.md` describing
   the upgrade path from SHA-256 to a future primitive (BLAKE3 or
   SHA-3 is already named in [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md)
   re-anchor logic) — keeps the criterion's intent without claiming any
   imminent algorithm change.

5. **`assurance_case` — start a minimal claims → arguments → evidence
   document.** Each AT-01..AT-08 row in [`SECURITY.md`](../../SECURITY.md)
   "Threat Categories" already has a mitigation; restructuring those
   into an assurance-case template (e.g., the GSN-style claim / strategy
   / evidence triple, in plain Markdown) is a half-day documentation pass.

6. **`regression_tests_added50` — add explicit mapping note in
   [`CONTRIBUTING.md`](../../CONTRIBUTING.md).** Two sentences asserting
   "every bug fix lands with a regression test that fails before the fix
   and passes after" promote the practice from implicit to explicit.

7. **`test_statement_coverage80` — publish coverage report.** Wire an
   existing CI coverage step to upload its summary as a release asset
   or as a coverage badge in `README.md`. No new infrastructure
   required if coverage is already collected.

8. **`build_repeatable` (partial → Met) — add a
   reproducible-build runbook.** The
   [`.github/workflows/reproducible-build.yml`](../../.github/workflows/reproducible-build.yml)
   exists; a short `docs/runbooks/reproducible-build.md` explaining
   inputs (Python version, Node version, action SHA pins) makes the
   "project itself can reproduce" claim explicit.

9. **`internationalization` (SHOULD, partial) — record explicit
   justification.** The substrate's primary output is structured
   data, not user-facing text; recording that fact crisply in
   `.bestpractices.json` (in a later PR) clarifies the partial state.

---

## Items requiring future commitments

These items cannot be advanced by a roadmap PR; they require either
events that land alongside the v1.0 GA target (2026-08-15) or
governance decisions that are explicitly out of scope for this
document.

1. **`signed_releases` — first cosign keyless + SLSA Build L3 release.**
   Achieved on tag `v1.0.9` per the row above and the
   [`CHANGELOG.md`](../../CHANGELOG.md) "First complete signed
   release: v1.0.9" entry. The autodev-train
   ([`scripts/release/stable_auto_train.py`](../../scripts/release/stable_auto_train.py))
   now auto-dispatches `sign-release.yml` and `slsa-provenance.yml`
   with `execute=true` after registry visibility is confirmed, so the
   forward path per
   [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md)
   is operational for every new autorelease tag rather than only
   manually-triggered ones. Pre-ADR tags are not retroactively signed.

2. **`crypto_credential_agility` — publish GPG key for
   `security@attestplane.com`.** Tracked in [`SECURITY.md`](../../SECURITY.md)
   ("GPG key: To be published at `https://attestplane.com/.well-known/security.txt`
   no later than M5 W6 (2026-08-15 target)"). The parallel branch
   `docs/security-supported-versions-and-gpg-plan` carries the plan
   detail. This document does not re-promise the date; it points at
   the existing published target.

3. **`version_tags_signed` (SUGGESTED) — GPG-signed git tags.**
   Depends on (2). Once the project GPG key is published, the release
   runbook in [`docs/runbooks/github-cd-release.md`](../runbooks/github-cd-release.md)
   can be extended to require `git tag -s`.

4. **`crypto_weaknesses` hardening via third-party cryptanalysis review.**
   The project's primitives are already free of known-weak algorithms,
   so this is already Met for the OpenSSF criterion. A third-party
   review is an additional assurance posture (relevant to Side A
   auditors and to the EU AI Office / notified-body audience). It is
   a **governance decision**, not a roadmap-level commitment; no date
   is promised here.

5. **`bus_factor` — second active maintainer.** Tracked in
   [`GOVERNANCE.md`](../../GOVERNANCE.md) §8.5 as a future milestone.
   Recruiting and onboarding a second maintainer is a
   community-growth decision; no date is promised here.

---

## Out of scope for this roadmap

- **Gold tier (level `'2'` in `criteria.yml`).** Gold adds criteria
  around contributor independence (`contributors_unassociated`,
  `bus_factor` upgraded to MUST), per-file copyright/license headers
  (already partially covered via REUSE 3.3), and stronger crypto
  posture. A gold-tier roadmap is a separate document.
- **ISO/IEC 42001 crosswalk.** Maps to the project's framework-mapping
  layer but is its own work package. Not committed here.
- **NIST AI RMF crosswalk.** Same — separate work package.
- **EU AI Office submissions or notified-body engagement.** Strategic /
  governance decisions, not part of this roadmap.
- **`.bestpractices.json` updates.** This roadmap is documentation
  only. Any change to a criterion's recorded answer goes through a
  separate PR that updates `.bestpractices.json` and the passing-tier
  mirror together, per the discipline in
  [`docs/security/openssf-best-practices.md`](openssf-best-practices.md).

---

## Update flow

When a silver criterion advances:

1. Open a PR that updates the relevant repo artifact (e.g. a new
   `SECURITY.md` subsection, a published achievements page, a signed
   release tag, a successor named in `GOVERNANCE.md` Appendix A).
2. In the **same or a follow-up** PR, update
   [`/.bestpractices.json`](../../.bestpractices.json) and
   [`docs/security/openssf-best-practices.md`](openssf-best-practices.md)
   to reflect the new state. The two artifacts must agree at every
   merged commit.
3. Move the row in this document from `partial` / `unmet` to Met,
   updating the evidence link.

This document is the record. The
[bestpractices.dev dashboard](https://www.bestpractices.dev/en/projects/12924/passing)
remains the authoritative external scoreboard.
