<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# P1 Verifier Closure Validation — 2026-05-18

## Scope

This P1 hardening pass closes verifier/proof/settlement gaps identified by
`docs/validation/full_software_audit_20260518.md`. It does not expand
Attestplane into runtime governance and does not change the release posture to
pre-beta, production-ready, or compliance-ready.

## Fixes

- ProofBundle verification now fails closed on unknown top-level critical
  metadata, unsupported versions/methods, missing required redaction terms,
  mismatched chain head metadata, and mismatched embedded verification reports.
- `policy_trace_refs` are verified against actual `policy_check_event` rows:
  missing, dangling, wrong-event-type, duplicate, empty-when-absent, and hash
  mismatch cases fail.
- Settlement precondition verification now fails closed when a claim binds
  `expected_settlement_amount_hash` but the matching settlement event omits,
  nulls, empties, malforms, or mismatches `amount_hash`.
- Anchor verification no longer treats an empty anchor list as anchored
  success. Empty evidence returns `verification_status = "not_performed"` and
  `ok = false` on the anchor verifier result.
- Python and TypeScript verifier semantics were updated together.

## Not Fixed

- Default CLI verification is still not a full verifier.
- Signature verification is still not performed by the default CLI path.
- Anchor verification is still not performed by the default CLI path.
- No compliance certification, legal opinion, production readiness, or runtime
  governance claim is introduced.

## CLI Scope

`attestplane verify` remains non-full and release-safe. It now performs
chain/report-oriented verification plus ProofBundle metadata and
`policy_trace_refs` closure guardrails. It still reports:

- `full_proof_bundle_verification = false`
- `signature_verification_performed = false`
- `anchor_verification_performed = false`
- `compliance_certification = false`

## Py/TS Consistency

The same settlement conformance fixture is consumed by both SDKs. The
settlement fixture schema version was bumped from `1` to `2` because new
negative amount-hash cases were added, and
`sdk/python/tests/conformance/FIXTURE_HASHES.lock` was updated.

## Tests Added or Updated

- Python ProofBundle metadata closure tests.
- TypeScript ProofBundle metadata closure tests.
- Python and TypeScript `policy_trace_refs` verifier tests.
- Python and TypeScript settlement amount-hash fail-closed fixture cases.
- Python and TypeScript anchor empty-evidence status tests.
- Python and TypeScript read-only verifier invariant tests.
- CLI tests updated to reflect metadata and `policy_trace_refs` guardrails
  while preserving non-full verifier wording.

## Safe Claims

- Alpha-grade dual-SDK tamper-evident evidence substrate.
- Chain/report-oriented CLI verification with metadata and
  `policy_trace_refs` closure guardrails.
- Read-only verifier predicates.
- Sidecar signing/anchoring primitives.

## No-Go Claims

- Production-ready or production-grade.
- Compliance-ready, EU AI Act compliant, DORA compliant, or GDPR compliant.
- Full ProofBundle verifier.
- Default CLI signed verification.
- Default CLI anchored verification.
- Runtime governance or AIOS runtime integration.
- Compliance certification.

## Validation Commands and Results

| Command | Result |
|---|---|
| `sdk/python/.venv/bin/pytest` | PASS, 700 passed |
| `cd sdk/python && .venv/bin/ruff check src tests` | PASS |
| `cd sdk/python && .venv/bin/mypy` | PASS |
| `cd sdk/typescript && npm test` | PASS, 432 passed |
| `cd sdk/typescript && npm run typecheck` | PASS |
| `cd sdk/typescript && npm run lint` | Exit 0 with two existing Biome `noNonNullAssertion` warnings in `test/proof_bundle.test.ts` |
| `bash scripts/check-schema-hashes.sh` | PASS |
| `bash scripts/check-fixture-hashes.sh` | PASS |
| `bash scripts/check-adr-frozen-blocks.sh` | PASS |
| `bash scripts/check-policy.sh` | PASS |
| `PATH="$PWD/sdk/python/.venv/bin:$PATH" bash scripts/test-cross-sdk-roundtrip.sh` | PASS |
| `jq empty docs/validation/p1_verifier_closure_20260518.json` | PASS |

## Release Posture

This moves verifier closure closer to pre-beta quality but does not make
Attestplane production-ready or compliance-ready. Public claims remain
conservative.
