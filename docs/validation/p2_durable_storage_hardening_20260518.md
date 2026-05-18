# P2.2 Durable Storage Hardening — 2026-05-18

## 1. Scope

This P2.2 hardening tightens the existing Python JSONL storage backend. It does
not add a database backend, tag or release a version, change release claims,
expand CLI verification scope, or introduce AIOS runtime behavior.

The goal is alpha durable-storage guardrails: append discipline, read-only
corruption scans, fail-closed reads, explicit CLI storage health reporting, and
fault-injection tests.

## 2. Existing Storage Model

The current storage abstraction remains `AbstractStorageBackend` with a Python
`JsonlStorageBackend` implementation. TypeScript does not have a matching JSONL
storage backend in this release line; that parity decision remains a documented
P2 roadmap item rather than a release blocker.

JSONL storage is opt-in. It stores one `ChainedEvent` per newline-terminated
record and remains separate from core `substrate.append` network/KMS/TSA
boundaries.

## 3. JSONL Alpha Durable Semantics

The JSONL backend now documents and enforces these alpha semantics:

- one complete JSON object per line
- append output is newline terminated
- reads fail closed by default through `read_all()`
- `scan()` is read-only and returns a valid prefix plus precise issues
- partial or corrupt data is never treated as full valid storage
- automatic repair, truncation, and destructive recovery are not implemented
- multi-writer safety is not claimed

These are guardrails for an alpha opt-in backend, not production storage
durability, ACID behavior, or database-grade crash safety.

## 4. Atomic Append / Flush / Fsync Behavior

`JsonlStorageBackend.append()` still serializes a complete event row before
writing. It writes one line, flushes the file handle, and fsyncs by default.
Callers may explicitly pass `durable=False` for tests or best-effort local
storage; this disables fsync without changing read-time fail-closed behavior.

The implementation remains process-local and uses a `threading.Lock` only
inside the process. No file lock or multi-process append guarantee is claimed.

## 5. Partial Write and Corruption Handling

`JsonlStorageBackend.scan()` tracks line numbers and byte offsets. It reports:

- `partial_trailing_line`
- `invalid_utf8`
- `malformed_json`
- `malformed_record`
- `missing_fields`
- `malformed_event`

The scan returns only the valid prefix before the first issue. `read_all()`
raises `StorageReadError` on any issue and never silently skips corrupt rows.

## 6. CLI Inspect / Export / Verify / Doctor Behavior

`attestplane inspect` now uses the storage scan path. Corrupt or partial JSONL
returns `ok=false`, `error=storage_corruption`, `storage_health=corrupt`, a
valid prefix count, and the first issue with line and byte offset.

`attestplane export` refuses to export from corrupt JSONL storage. It does not
write a ProofBundle from a polluted file unless the storage scan is complete.

`attestplane doctor` now reports JSONL backend capabilities separately from
chain validity:

- `jsonl_backend_available`
- `durable_fsync_enabled`
- `fsync_supported`
- `file_lock_supported`
- `multi_writer_safe`
- `concurrent_append_behavior`
- `repair_supported`
- `destructive_repair_supported`

`attestplane verify` scope is unchanged and remains `chain_report_only`.

## 7. Concurrent Writer Semantics

The JSONL backend remains single-process only:

- `multi_writer_safe=false`
- `file_lock_supported=false`
- `concurrent_append_behavior=single_process_thread_lock_only`

Cross-process writes to the same file are not a supported correctness boundary.
Future file-locking or database-backed storage remains roadmap work.

## 8. Fault-Injection Tests

New and updated tests cover:

- valid JSONL append/read roundtrip behavior
- newline-terminated append output
- fsync enabled and disabled paths
- partial trailing line detection
- malformed JSON in the middle of a file
- non-object JSONL rows
- CLI inspect storage corruption output
- CLI export refusal on corrupt storage
- CLI doctor storage capability reporting
- alpha concurrency semantics in the health report

## 9. Public API Impact

No root public API exports were added. The P2.1 public API manifest gate remains
unchanged. New storage scan and health-report methods are part of the existing
Python JSONL backend surface and are documented as alpha storage diagnostics.

## 10. Safe Claims Unchanged

- Alpha-grade dual-SDK tamper-evident evidence substrate.
- Restricted canonicalization and canonical text hashing.
- SHA-256 hash-chain primitives.
- Evidence payload schemas and fail-closed validators.
- Sidecar signing and anchoring primitives.
- Read-only verifier predicates.
- CLI verify remains `chain_report_only`.
- JSONL storage is an alpha opt-in backend with read-only corruption scans.

## 11. No-Go Claims Unchanged

- Production-ready, production-grade, or production storage.
- Compliance-ready.
- Certification or external certification.
- EU AI Act, DORA, or GDPR compliant.
- Full CLI ProofBundle verifier.
- Default CLI signed verification.
- Default CLI anchored verification.
- Runtime governance, execution authority, scheduler, gateway authority, or
  AIOS runtime integration.
- ACID storage, database-grade durability, crash-proof behavior, or
  multi-writer correctness.

## 12. Remaining Storage Roadmap

- File-locking or explicit lock-provider semantics.
- Destructive repair or truncate tooling with explicit operator confirmation.
- Database-backed storage adapter.
- TypeScript storage backend parity decision.
- Storage compatibility manifest and migration policy.

## 13. Validation Commands

| Command | Result |
|---|---|
| `scripts/check-public-api.sh` | PASS, python=127 symbols, typescript=171 exports, allowlist=130 asymmetries |
| `sdk/python/.venv/bin/pytest` | PASS, 734 passed |
| `cd sdk/python && .venv/bin/ruff check src tests` | PASS |
| `cd sdk/python && .venv/bin/mypy` | PASS |
| `cd sdk/typescript && npm test` | PASS, 451 passed |
| `cd sdk/typescript && npm run typecheck` | PASS |
| `cd sdk/typescript && npm run lint` | PASS, zero warnings |
| `bash scripts/check-schema-hashes.sh` | PASS |
| `bash scripts/check-fixture-hashes.sh` | PASS |
| `bash scripts/check-adr-frozen-blocks.sh` | PASS |
| `bash scripts/check-policy.sh` | PASS |
| `PATH="$PWD/sdk/python/.venv/bin:$PATH" bash scripts/test-cross-sdk-roundtrip.sh` | PASS |
| `jq empty docs/validation/p2_durable_storage_hardening_20260518.json api/public/*.json` | PASS |
| `git diff --check` | PASS |

## 14. Status

PASS. P2.2 durable storage hardening is complete for the alpha JSONL backend.
Safe claims and no-go claims are unchanged.
