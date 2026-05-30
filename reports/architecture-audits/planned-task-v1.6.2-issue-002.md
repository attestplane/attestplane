<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# [P1][test][conformance] Pin cross-SDK coverage for the daily product change

Source planning issue: #113
Plan schema: `attestplane.plan.v1`
Plan ID: `8ffcf15c3da1d588`
Priority: P1

Title: [P1][test][conformance] Pin cross-SDK coverage for the daily product change

Affected modules:

- Python SDK tests
- TypeScript SDK tests
- conformance fixtures

Acceptance criteria:

1. Add or update conformance coverage for the product behavior from issue 1.
2. Confirm Python and TypeScript validation expectations stay aligned.
3. Record the validation evidence on the task issue before close.

Validation commands:

- `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'conformance or canonical or roundtrip' -x`
- `npm test --prefix sdk/typescript -- --runInBand`
- `git diff --check`

Rollout / migration notes: Coverage must follow the product change, not release metadata churn.

Generated from accepted development plan.
