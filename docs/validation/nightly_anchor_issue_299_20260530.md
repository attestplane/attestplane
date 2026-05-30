<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Nightly Anchor Issue #299 Diagnosis - 2026-05-30

## Scope

This report records the P0 diagnosis for the claim-safety blocker
tracked in [`#299`](https://github.com/attestplane/attestplane/issues/299).
It covers the FreeTSA live anchoring path and the verifier quarantine
boundary.

This report does not change release status and does not expand public
claims.

## Finding

The verifier was treating cross-reference-correct anchors as a positive
claim even when no trust roots were configured. In that mode, the anchor
result was surfaced as `VALID_UNVERIFIED`, but the aggregate verifier
still returned `ok=true` / `verification_status="verified"` in the
substrate-only path.

That was claim-unsafe because a transient TSA outage, missing trust
roots, or an offline replay without cryptographic validation must not be
reported as a verified anchor.

## Fix

The anchor verifier now distinguishes:

- `anchor.invalid` for cryptographic or structural failures.
- `anchor.unverifiable` for transient or offline conditions where the
  anchor cannot be cryptographically verified.

Claim-safe behavior now follows these rules:

- `VALID_UNVERIFIED` no longer counts as a positive verification claim.
- Missing trust roots produce `verification_status="not_performed"`.
- Invalid anchors still fail closed with `verification_status="failed"`.
- The aggregate `reason_code` now surfaces the distinction between
  invalid and unverifiable anchor outcomes.

An offline regression was added using the frozen FreeTSA response
fixture in `sdk/python/tests/conformance/anchor_vectors.json`, and the
verifier regression suite now pins the quarantine boundary directly.

## Validation

Validated locally with:

- `pytest tests/anchoring -k freetsa -q`
- `pytest tests/verifier -k anchor_quarantine -q`
- `python3.11 -m pytest tests/ -q --tb=short 2>&1 | tail -20`
- `python3.11 -m ruff check sdk/python/`
- `python3.11 -m mypy sdk/python/src/ --ignore-missing-imports`

## Final Status

`nightly_anchor_issue_299_diagnosed_with_claim_safe_fix`
