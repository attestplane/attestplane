<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Planned Task: [P1][conformance][cli] Pin consensus `taxonomy_version` formatting across `verify --json` and `verify --explain` output surfaces

Source planning issue: #0 (v1.8.19 daily development plan)
Plan schema: `attestplane.plan.v1`
Plan ID: `88e77e0f70082fbf`
Priority: P1

Title: [P1][conformance][cli] Pin consensus `taxonomy_version` formatting across `verify --json` and `verify --explain` output surfaces

Affected modules:
- Python SDK CLI (`attestplane verify --json`, `attestplane verify --explain`)
- Python CLI output formatting
- Conformance golden fixtures
- Fixture-lock maintenance

Acceptance criteria:
1. `verify --json` and `verify --explain` expose the same stable `taxonomy_version` integer for the same proof bundle.
2. The Python SDK CLI renders `taxonomy_version` consistently across both output formats (no string vs. int mismatch, no missing field).
3. A conformance fixture pins the combined `--json` + `--explain` consensus contract.
4. Reference the existing open conformance issues rather than duplicating their scope.

Validation commands:
- `cd sdk/python && python -m pytest tests/cli -k 'taxonomy_version or explain' -x -q`
- `cd sdk/python && python -m pytest tests/conformance -k 'taxonomy_version' -x -q`
- `python scripts/conformance/verify_fixture_lock.py`
- `git diff --check`

Rollout / migration notes:
Keep existing `exit_code`, `error_code`, and human-readable failure strings unchanged. Update locked fixture hashes only for the intentionally added taxonomy_version assertion. Do not regenerate unrelated fixtures.

Generated from accepted development plan.
