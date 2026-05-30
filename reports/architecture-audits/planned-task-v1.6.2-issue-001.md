<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# [P1]\[sdk\]\[verifier\] Add a verifier-facing product increment for v1.6.2

Source planning issue: #113
Plan schema: `attestplane.plan.v1`
Plan ID: `8ffcf15c3da1d588`
Priority: P1

Title: [P1]\[sdk\]\[verifier\] Add a verifier-facing product increment for v1.6.2

Affected modules:

- Python SDK verifier
- TypeScript SDK verifier
- proof bundle fixtures

Acceptance criteria:

1. Implement one small verifier or proof-bundle behavior that is visible to SDK users.
2. Keep the change backward compatible with the current stable proof bundle contract.
3. Record the product-facing behavior and validation evidence on the task issue before close.

Validation commands:

- `sdk/python/.venv/bin/python -m pytest sdk/python/tests -k 'verifier or proof_bundle or conformance' -x`
- `npm test --prefix sdk/typescript -- --runInBand`
- `git diff --check`

Rollout / migration notes: Daily work should land a real Attestplane product delta before any release-train-only task.

Generated from accepted development plan.
