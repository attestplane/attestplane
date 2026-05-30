<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Source planning issue: #0
Plan schema: `attestplane.plan.v1`
Plan ID: `dd7b313679e7e6f2`
Priority: P1

Title: [P1][verifier][conformance] Pin additive-optional schema_version conformance contract and verifier output fixture

Affected modules:
- Python SDK verifier
- verifier conformance fixtures
- CLI output-contract fixture
- schema_version vectors

Acceptance criteria:
1. Add or update the positive forward-compatible vector for unknown additive-optional fields under `schema_version`.
2. Pin a stable `verify --json` output-contract fixture for CI consumers in the v1.5.7 milestone.
3. Keep the negative vectors rejecting malformed or non-forward-compatible shapes passing.
4. Reference existing schema_version conformance issues without duplicating their scope.

Validation commands:
- `PYTHONPATH=sdk/python/src pytest tests/conformance -k "schema_version or forward or additive" -q --tb=short`
- `PYTHONPATH=sdk/python/src pytest sdk/python/tests/conformance -q --tb=short`
- `git diff --check`

Rollout / migration notes:
Update locked fixture hashes only if the new vector is intentionally added. Do not regenerate unrelated fixtures.

Generated from accepted development plan.
