<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Source planning issue: #0
Plan schema: `attestplane.plan.v1`
Plan ID: `dd7b313679e7e6f2`
Priority: P1

Title: [P1][sdk][test] Extend cross-SDK taxonomy_version conformance coverage for verifier surface

Affected modules:
- Python SDK verifier
- TypeScript SDK verifier
- cross-SDK roundtrip tests
- conformance fixtures

Acceptance criteria:
1. Verify Python and TypeScript SDKs expose the same `taxonomy_version` for identical proof bundles.
2. Add cross-SDK conformance test that compares `verify --json` output across SDK boundaries.
3. Keep existing `error_code` behavior and human-readable failure strings unchanged.

Validation commands:
- `PYTHONPATH=sdk/python/src pytest tests/verifier -k "taxonomy_version or reason_code" -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/cli -q --tb=short`
- `cd sdk/typescript && npm test -- --runInBand`
- `git diff --check`

Rollout / migration notes:
Keep the current failure semantics stable. Do not remove or rename existing error fields.

Generated from accepted development plan.
