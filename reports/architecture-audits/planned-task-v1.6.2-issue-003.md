<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# [P2]\[docs\]\[api\] Document the user-visible product delta for v1.6.2

Source planning issue: #113
Plan schema: `attestplane.plan.v1`
Plan ID: `8ffcf15c3da1d588`
Priority: P2

Title: [P2]\[docs\]\[api\] Document the user-visible product delta for v1.6.2

Affected modules:

- docs
- SDK API docs
- release notes

Acceptance criteria:

1. Document the verifier or proof-bundle behavior added by issue 1.
2. Link the documentation to the source planning issue and task issues.
3. Keep wording within claim boundaries and avoid secrets.

Validation commands:

- `git diff --check`

Rollout / migration notes: Docs-only work cannot satisfy the daily plan unless issue 1 lands a product change.

Generated from accepted development plan.
