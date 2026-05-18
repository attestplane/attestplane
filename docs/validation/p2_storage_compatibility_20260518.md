# P2.6 Storage Compatibility / Migration Policy Validation

Date: 2026-05-18

## Scope

This P2.6 hardening step adds storage compatibility policy for JSONL storage,
storage scan issues, ProofBundle export behavior, and future migration policy.

It does not add SQLite/Postgres, does not implement destructive repair, does
not change `v0.0.2-alpha`, and does not claim production storage.

## Storage Compatibility Manifest

Added:

- `storage/compat/storage_compatibility_v1.json`
- `storage/compat/README.md`

The manifest records the Python JSONL backend as `alpha_opt_in`, not
multi-writer safe, read-only repair/report by default, and fail-closed on
unknown explicit storage record versions.

## Compatibility Fixtures

Added:

- `storage/compat/fixtures/jsonl_valid_v1.jsonl`
- `storage/compat/fixtures/jsonl_partial_tail_v1.jsonl`
- `storage/compat/fixtures/jsonl_malformed_middle_v1.jsonl`
- `storage/compat/fixtures/jsonl_unknown_record_version_v1.jsonl`
- `storage/compat/fixtures/storage_scan_issue_v1.json`
- `storage/compat/fixtures/export_refusal_corrupt_storage_v1.json`

Negative JSONL fixtures are consumed by Python tests and assert stable scan
issue kinds.

## Checker / Script Integration

Added:

- `scripts/storage/check_storage_compatibility.py`
- `scripts/check-storage-compatibility.sh`

The checker validates manifest schema, backend policy fields, no-go claims,
known issue codes against the implementation, fixture declarations, unknown
version fail-closed policy, and destructive repair defaults.

## JSONL Format Policy

Current rows require `seq`, `prev_hash_hex`, `event_hash_hex`, and `event`.
Existing rows without a storage record version remain accepted. Rows with an
explicit unsupported `storage_record_version` fail closed with
`unknown_record_version`.

## Scan Issue Policy

The stable issue fields remain:

- `kind`
- `line_no`
- `byte_offset`
- `detail`

Known issue kinds are locked in the compatibility manifest and tested against
the implementation.

## Export / Migration Policy

Export refuses corrupt storage by default. Migrations are non-destructive by
default. Destructive repair/truncate remains not implemented.

## CLI Behavior

Tests confirm:

- `inspect --json` reports storage issue kind for corrupt JSONL.
- `export --json` refuses corrupt JSONL and does not write a bundle.
- `doctor --json` reports alpha-safe JSONL capabilities and no multi-writer or
  destructive repair support.

## Public API Impact

No root public API exports were added. The public API manifest remains
unchanged.

## Validation Commands

Full command results are recorded in
`p2_storage_compatibility_20260518.json`.

Summary:

- `scripts/check-storage-compatibility.sh` PASS.
- `scripts/check-release-provenance.sh` PASS.
- `scripts/check-fault-injection.sh` PASS: active=50, covered=50, roadmap/language-specific=1.
- `scripts/check-public-api.sh` PASS: python=127 symbols, typescript=193 exports, allowlist=138 asymmetries.
- `sdk/python/.venv/bin/pytest` PASS: 791 passed.
- `cd sdk/python && .venv/bin/ruff check src tests` PASS.
- `cd sdk/python && .venv/bin/mypy` PASS.
- `cd sdk/typescript && npm test` PASS: 502 passed.
- `cd sdk/typescript && npm run typecheck` PASS.
- `cd sdk/typescript && npm run lint` PASS: zero warnings.
- Schema, fixture, ADR, policy, and cross-SDK gates PASS.
- JSON validation and `git diff --check` PASS.

## Remaining P2/P3

- TypeScript storage backend parity decision.
- Explicit file-locking or lock-provider policy.
- Operator-confirmed destructive repair tooling, if ever added.
- Database backend compatibility manifests if SQLite/Postgres are introduced.

## Status

PASS.
