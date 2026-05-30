<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->
# Architecture Gap Audit for v1.5.0

## Milestone Context

| Field | Value |
|---|---|
| milestone_tag | `v1.5.0` |
| plan_level | `medium` |
| anchor_tag | `v1.0.0` |
| head_sha | `3b1ead442184599a68af266e9a564dbcb02acc12` |
| stable_release_count (since anchor) | 54 |
| real_commit_count (since anchor) | 57 |
| release_prep_commit_count (since anchor) | 58 |
| decision | `medium-plan` / `half_version_medium_upgrade` |

## Recent Real Commits (top 20)

| SHA | Date | Subject |
|---|---|---|
| `7a2aeb14` | 2026-05-21 | fix(release): watch fresh signing workflow runs |
| `7d001237` | 2026-05-21 | ci(release): always file medium upgrade plans |
| `5c9cf7c5` | 2026-05-21 | test(release): isolate stable train recovery test |
| `88f985e3` | 2026-05-21 | fix(release): recover superseded local stable tags |
| `f1eb2655` | 2026-05-21 | docs(security): add SECURITY_zh.md (Chinese translation, draft) (#53) |
| `09a58065` | 2026-05-21 | ci: hotfix codespell+typos+markdownlint for GPG playbook (#60) |
| `79fb7f2f` | 2026-05-21 | docs(security): upgrade MITRE CNA application to v2 (#59) |
| `499958ce` | 2026-05-21 | security: add GPG key generation playbook + SECURITY.md placeholder (#58) |
| `f14aff13` | 2026-05-21 | ci(release): harden architecture audit optional args |
| `f40c317f` | 2026-05-21 | ci(docs): add pdoc + typedoc auto API ref workflow (artifact-only) (#49) |
| `2c1d7570` | 2026-05-21 | docs: add 5-minute quickstart walkthrough (#55) |
| `e5335688` | 2026-05-21 | docs(security): expand threat model to v1 (#56) |
| `83f4a67e` | 2026-05-21 | docs(spec): add ISO/IEC 42001 AIMS alignment mapping (#54) |
| `48dccefe` | 2026-05-21 | docs(spec): add GDPR Articles 5/22/30 alignment mapping (#52) |
| `2908d793` | 2026-05-21 | docs(spec): add NIST AI RMF 1.0 alignment mapping (#50) |
| `b20508b4` | 2026-05-21 | docs(security): publish OpenSSF Scorecard badge + draft r-b.org (#46) |
| `9d6c99d4` | 2026-05-21 | docs(governance): add PR-level conflict-resolution procedure (#48) |
| `a6195c21` | 2026-05-21 | docs(governance): add Reviewer bridge tier (#51) |
| `98efca51` | 2026-05-21 | docs(governance): add MAINTAINERS.md consolidating maintainer roster (#47) |
| `2fead039` | 2026-05-21 | feat(release): autorelease cadence limiter (#45) |

## Product Commit Analysis

Since v1.0.0 anchor, **zero** commits touched SDK product modules:

| Module | Commits | Product delta |
|---|---|---|
| `sdk/python/src/attestplane/verifier.py` | 0 | None since v1.0.0 |
| `sdk/python/src/attestplane/reason_codes.py` | 0 | Frozen but unused in verifier output |
| `sdk/python/src/attestplane/hashchain.py` | 0 | None |
| `sdk/python/src/attestplane/proof_bundle.py` | 0 | None |
| `sdk/python/src/attestplane/cli/` | 0 | None |
| `sdk/python/src/attestplane/obligations/` | 0 | Only `eu_ai_act_article_12` + `dora_article_8` shipped |
| `sdk/python/src/attestplane/conformance/` | 0 | None |
| `sdk/typescript/` | 0 | None |

All 57 real commits are **docs, governance, security meta-docs, CI automation, or release train infrastructure**.

## Known Architecture Gaps (since v1.0.0)

### Gap A: ADR-0010 ReasonCodeV1 not wired into verifier result

- **File**: `reason_codes.py` (25 codes defined) vs `verify_reason_codes.py` (10 codes used)
- **Impact**: The full ADR-0010 semantic layer (CHAIN_OK, SIGNATURE_OK, ANCHOR_OK, etc.) exists as a Literal type but is never emitted by `BundleVerificationResult`. Downstream tooling (audit reports, compliance evidence packs) must regex-match the 10 `att.verify.*` codes.
- **Deferred since**: v1.0.0
- **Scope**: Medium — threading 25 codes through the verifier result requires updating `BundleVerificationResult`, extending reason derivation, and adding conformance vectors.
- **Forward path**: Follow-up ADR-0015 anticipated in `reason_codes.py` docstring.

### Gap B: Obligations registry incomplete

- **Files**: `obligations/eu_ai_act_article_12.json`, `obligations/dora_article_8.json`
- **Impact**: Compliance mappings for NIS2 Article 21, GDPR Article 30, and ISO 42001 clauses are listed as "future entries" in `__init__.py` but never shipped.
- **Deferred since**: v1.0.0
- **Scope**: Small/Medium — each registry is a JSON file + a `load_*` function following the existing pattern.

### Gap C: No obligation-driven verifier integration

- **Impact**: Registry data exists but is never consumed by verifier or CLI. No `--check-obligations` flag, no obligation-aware reason code derivation.
- **Deferred since**: v1.0.0
- **Scope**: Medium — requires verifier extension + CLI flag + conformance vectors.

### Gap D: Signing/anchoring not integrated into main verifier path

- **Impact**: `signing/verifier_ext.py` and `anchoring/verifier.py` contain production-ready crypto verification but are never called by `verify_proof_bundle()`. CLI reports `signature_verification_performed: false`.
- **Deferred since**: v1.0.0
- **Scope**: Large — for v1.5.0, defer full integration to v2.0.0 (architecture-level redesign). Partial shape-only validation is already done in the `verify-proofbundle` alpha command.

### Gap E: Dual taxonomy (ReasonCodeV1 vs VerifyReasonCodeV1) creates maintenance burden

- **Impact**: Two parallel reason-code systems in the same SDK. `reason_codes.py` is frozen at schema v1; `verify_reason_codes.py` is the active taxonomy.
- **Scope**: Medium — plan to converge by making `BundleVerificationResult` carry both the high-level `att.verify.*` code (for backward compatibility) AND the ADR-0010 `ReasonCodeV1` value (for semantic richness).

## Recommendation

For a **medium** upgrade at v1.5.0:

1. **P0**: Wire ADR-0010 `ReasonCodeV1` into `BundleVerificationResult` as an additive field alongside the existing `att.verify.*` reason codes. This is the most impactful medium-scope product gap.
2. **P1**: Add conformance vectors for the new reason code output.
3. **P1**: Ship the NIS2 Article 21 and GDPR Article 30 obligation registry stubs.
4. **P2**: Document the v1.5.0 user-visible delta (reason code integration + new obligation registries).
