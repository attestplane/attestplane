# P1 Schema and Canonical Alignment Validation — 2026-05-18

## Source

This validation follows `docs/validation/full_software_audit_20260518.md` and the
P1 verifier closure commit `b5ed29e`. It addresses the remaining P1
cross-language schema/canonical hardening items only.

## Scope

- Tightened TypeScript canonical JSON edge handling.
- Aligned Python and TypeScript payload validators with the v1 JSON Schemas.
- Expanded shared negative conformance fixtures for lease lifecycle, policy
  check, and replay event payloads.
- Kept CLI `verify` scoped as `chain_report_only`.
- Did not add production, compliance, full ProofBundle, signed verification, or
  anchored verification claims.

## Canonical Edge Cases

- TypeScript `canonicalize()` now rejects `undefined` at top level, object
  property values, and array items.
- Sparse array holes fail closed instead of becoming `null`.
- `function`, `symbol`, direct `bigint`, unsafe integers, `NaN`, `Infinity`, and
  `-Infinity` are rejected.
- `-0` is locked to canonical `0`, matching Python integer behavior.
- Direct `Date` objects are rejected by canonical JSON; hash-chain code performs
  an explicit typed timestamp conversion before hashing `AuditEvent`.
- Lone Unicode surrogate code points are rejected in both Python and TypeScript.
- Canonical JSON continues to require NFC strings and does not silently normalize
  ordinary strings.
- Existing frozen `vectors.json` remains unchanged. TypeScript conformance tests
  use a test-only int64 literal wrapper for JSON literals that exceed the JS
  safe-integer range; public `canonicalize(1n)` remains rejected.

## Payload Schema Alignment

- Lease lifecycle, policy check, and replay event validators now reject unknown
  top-level fields in both SDKs, matching `additionalProperties: false`.
- Optional fields distinguish missing from explicit `null`; `null` is rejected
  where schemas require strings/arrays/hashes.
- Optional `reason_code` fields must match the schema regex
  `^[A-Z][A-Z0-9_]{1,63}$`. Domain-specific codes remain allowed if they match
  the documented extension-by-format behavior.
- Required schema-version fields remain mandatory and fixed at `1`.
- Enum and required-field behavior remains aligned across Python and TypeScript.

## TS Negative Fixture Replay

TypeScript now continues to replay the same shared negative fixtures as Python,
with added coverage for:

- `lease_lifecycle_event_vectors.json`: unknown field, missing schema version,
  nullable optional reason code, invalid reason code format.
- `policy_check_event_vectors.json`: unknown field, missing schema version,
  nullable optional kind, invalid reason code format.
- `replay_event_vectors.json`: unknown field, missing schema version, nullable
  optional snapshot ref, invalid reason code format.
- Existing settlement, reason-code, and forbidden-field negative fixture replay
  remains active.

## Fixtures and Schemas

- Schemas were not changed.
- Frozen canonical vectors were not changed.
- Fixture files changed:
  - `sdk/python/tests/conformance/lease_lifecycle_event_vectors.json`
  - `sdk/python/tests/conformance/policy_check_event_vectors.json`
  - `sdk/python/tests/conformance/replay_event_vectors.json`
  - `sdk/python/tests/conformance/FIXTURE_HASHES.lock`

## Remaining Limits

- Schema and payload validation is not compliance certification.
- CLI `verify` remains `chain_report_only`.
- Signature and anchor verification are still not performed by CLI `verify`.
- TypeScript direct `Date` objects are rejected by canonical JSON, but
  `AuditEvent` hashing still supports the typed SDK event boundary through an
  explicit timestamp conversion.

## Safe Claims

- Alpha-grade dual-SDK tamper-evident evidence substrate.
- Restricted canonical JSON and canonical-text primitives with cross-language
  conformance gates.
- Payload schemas and validators with fail-closed negative fixture replay.
- Read-only verifier predicates and chain/report-oriented CLI verification.

## No-Go Claims

- Production-ready.
- Compliance-ready or certified.
- EU AI Act, DORA, or GDPR compliant.
- Full ProofBundle verifier in the CLI.
- CLI signed verification or anchored verification.
- Runtime governance, control-plane execution, or AIOS runtime integration.

## Validation Results

| Command | Result |
|---|---|
| `sdk/python/.venv/bin/pytest` | PASS, 714 passed |
| `cd sdk/python && .venv/bin/ruff check src tests` | PASS |
| `cd sdk/python && .venv/bin/mypy` | PASS |
| `cd sdk/typescript && npm test` | PASS, 449 passed |
| `cd sdk/typescript && npm run typecheck` | PASS |
| `cd sdk/typescript && npm run lint` | PASS, exit 0 with two existing Biome warnings |
| `bash scripts/check-schema-hashes.sh` | PASS |
| `bash scripts/check-fixture-hashes.sh` | PASS |
| `bash scripts/check-adr-frozen-blocks.sh` | PASS |
| `bash scripts/check-policy.sh` | PASS |
| `PATH="$PWD/sdk/python/.venv/bin:$PATH" bash scripts/test-cross-sdk-roundtrip.sh` | PASS |
| `jq empty docs/validation/p1_schema_canonical_alignment_20260518.json` | PASS |
| `git diff --check` | PASS |
