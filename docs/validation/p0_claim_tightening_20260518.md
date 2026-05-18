<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# P0 Claim Tightening Validation — 2026-05-18

## Audit Source

This remediation follows
[`full_software_audit_20260518.md`](full_software_audit_20260518.md) and
[`full_software_audit_20260518.json`](full_software_audit_20260518.json).

The source audit classified Attestplane as alpha-ready as an OSS substrate,
but not pre-beta-ready and not production-ready. It identified two P0 release
blockers:

1. `attestplane verify` was chain/report-oriented, not full ProofBundle
   verification.
2. Release-facing docs could be read as claiming full verifier, signed
   verification, anchored verification, or compliance readiness.

## P0 Fix Scope

This pass only aligns public claims and CLI output with the implementation.
It does not implement a larger verifier and does not change verification exit
code semantics.

Modified claim surfaces:

- `README.md`
- `CHANGELOG.md` was reviewed; no edit was required.
- `docs/policy/allowed_claims.md`
- `docs/policy/forbidden_claims.md`
- `docs/release-notes/v0.0.2-alpha.draft.md`
- `sdk/python/README.md`
- `sdk/typescript/README.md`

Modified CLI/test surfaces:

- `sdk/python/src/attestplane/cli/main.py`
- `sdk/python/tests/cli/test_main.py`
- `sdk/python/tests/test_release_claims.py`

Validation artifacts added:

- `docs/validation/p0_claim_tightening_20260518.md`
- `docs/validation/p0_claim_tightening_20260518.json`

## Retained Limitations

- `attestplane verify` remains chain/report-oriented.
- It does not perform full ProofBundle verification.
- It does not verify signatures.
- It does not verify anchors.
- It does not verify `policy_trace_refs` closure.
- It does not issue compliance certification.
- Sidecar signing and anchoring primitives remain separate from the default
  CLI verify path.
- Schemas, recipes, and adapter fixtures remain evidence surfaces; they are
  not runtime governance.

## Safe Claims

- Attestplane is an alpha-grade dual-SDK tamper-evident evidence substrate.
- It provides restricted canonicalization, SHA-256 hash-chain primitives,
  evidence payload schemas, sidecar signing/anchoring primitives, and
  read-only verifier predicates.
- Python and TypeScript conformance fixtures are byte-locked and enforced in
  tests.
- `attestplane verify` is chain/report-oriented.

## No-Go Claims

- Production-ready or production-grade.
- Compliance-ready, EU AI Act compliant, DORA compliant, or GDPR compliant.
- Full ProofBundle verifier.
- Signed verification by the default CLI.
- Anchored verification by the default CLI.
- Compliance certification.
- Runtime governance, runtime execution authority, scheduler, gateway
  authority, billing, secret store, or UI read model.
- Completed AIOS runtime integration in the OSS repository.

## Validation Commands and Results

| Command | Result |
|---|---|
| `sdk/python/.venv/bin/pytest` | PASS, 683 passed |
| `cd sdk/python && .venv/bin/ruff check src tests` | PASS |
| `cd sdk/python && .venv/bin/mypy` | PASS |
| `cd sdk/typescript && npm test` | PASS, 415 passed |
| `cd sdk/typescript && npm run typecheck` | PASS |
| `cd sdk/typescript && npm run lint` | Exit 0 with the two pre-existing Biome `noNonNullAssertion` warnings in `test/proof_bundle.test.ts` |
| `bash scripts/check-schema-hashes.sh` | PASS |
| `bash scripts/check-fixture-hashes.sh` | PASS |
| `bash scripts/check-adr-frozen-blocks.sh` | PASS |
| `bash scripts/check-policy.sh` | PASS |
| `PATH="$PWD/sdk/python/.venv/bin:$PATH" bash scripts/test-cross-sdk-roundtrip.sh` | PASS |
| `sdk/python/.venv/bin/pytest sdk/python/tests/test_release_claims.py sdk/python/tests/cli/test_main.py -q` | PASS, 16 passed |

Note: `bash scripts/test-cross-sdk-roundtrip.sh` without the Python SDK venv on
`PATH` fails with `ModuleNotFoundError: No module named 'attestplane'`; the
script documents that the Python SDK must be installed in the active venv.

## Release Posture After Fix

The next alpha can claim a restricted, alpha-grade evidence substrate with
chain/report-oriented CLI verification. It must not claim production
readiness, compliance readiness, full ProofBundle verification, signed
verification, anchored verification, or compliance certification.
