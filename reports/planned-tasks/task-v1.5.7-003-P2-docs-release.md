<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Source planning issue: #0
Plan schema: `attestplane.plan.v1`
Plan ID: `dd7b313679e7e6f2`
Priority: P2

Title: [P2][docs][release] Document the v1.5.7 user-visible delta and conformance boundary

Affected modules:
- docs
- validation evidence
- release notes

Acceptance criteria:
1. Document the `schema_version` additive-optional behavior and the cross-SDK `taxonomy_version` verification.
2. Record the validation evidence for the verifier output-contract fixture.
3. Keep wording within claim-safety boundaries and do not touch `CHANGELOG.md`.

Validation commands:
- `markdown-link-check docs/**/*.md`
- `git diff --check`

Rollout / migration notes:
Docs-only work cannot satisfy the daily plan unless ISSUE 1 and ISSUE 2 land product changes.

Generated from accepted development plan.
