# P2.3 Fault-Injection Gate — 2026-05-18

## 1. Scope

This P2.3 hardening adds a lightweight deterministic fault-injection gate for
Attestplane fail-closed invariants. It does not add a heavyweight mutation
testing platform, tag or release a version, change release claims, expand CLI
verification scope, or introduce AIOS runtime behavior.

The gate protects the highest-risk regression paths where malformed or
tampered evidence could accidentally drift from fail-closed to fail-open.

## 2. Fault Matrix Summary

Fault matrix:

- `tests/fault_injection/fault_matrix_v1.json`

Coverage summary:

- active faults: 50
- covered active faults: 50
- roadmap faults: 1

The matrix records area, language, mutation, expected behavior, protected
invariant, status, and test references for each fault.

## 3. Active Fault Coverage

Active coverage spans:

- canonicalization
- hashchain integrity
- payload validators
- reason-code format and known-code checks
- ProofBundle metadata closure
- policy trace references
- settlement precondition amount hash binding
- anchoring empty/malformed evidence behavior
- Python JSONL storage corruption handling
- CLI claim and storage-health regressions

Every active fault has at least one concrete test reference checked by
`scripts/fault/check_fault_matrix.py`.

## 4. Roadmap Faults

The only roadmap item is TypeScript JSONL backend parity:

- `jsonl.typescript_backend_parity`

This is explicitly not counted as active coverage because TypeScript does not
ship a JSONL backend in the current release line.

## 5. Python Coverage

Python fault tests:

- `sdk/python/tests/fault_injection/test_fault_matrix.py`

The Python suite covers:

- canonical reject cases for NaN, Infinity, lone surrogates, unsafe integers,
  key ordering, and negative-zero behavior
- hashchain mutations for previous hash, event hash, payload tamper, reorder,
  missing link, and duplicate index
- lease payload missing/unsupported schema version, unknown field, forbidden
  field, null required field, unknown enum, and reason-code format failures
- ProofBundle metadata and policy trace reference mutations
- settlement amount hash missing/empty/malformed/mismatched failures
- anchor absence and malformed anchor failures
- JSONL partial/corrupt/invalid row scan failures

## 6. TypeScript Coverage

TypeScript fault tests:

- `sdk/typescript/test/fault_injection.test.ts`

The TypeScript suite covers:

- canonical reject cases for NaN, Infinity, undefined, sparse arrays, unsafe
  integers, lone surrogates, Date objects, key ordering, and negative-zero
  behavior
- hashchain tamper/reorder/missing/duplicate mutations
- payload validator fail-closed paths
- ProofBundle metadata and policy trace reference mutations
- settlement amount hash failures
- anchor absence and malformed anchor failures

## 7. CLI / Storage / Verifier Fail-Closed Regressions

The gate protects these CLI/storage/verifier regressions:

- CLI verify must not claim full ProofBundle, signed, or anchored verification.
- CLI doctor must not overclaim JSONL multi-writer safety.
- CLI inspect must report storage corruption.
- CLI export must refuse corrupt JSONL storage.
- ProofBundle verifier must fail closed on metadata closure and policy trace
  reference mutations.
- Settlement verifier must fail closed when bound amount hashes are missing or
  malformed.
- Anchor verification must not treat empty anchor evidence as success.

## 8. CI Integration

Local gate:

```bash
scripts/check-fault-injection.sh
```

CI integration:

- `.github/workflows/invariants.yml`
- job: `fault-injection`

The job installs Python and TypeScript SDK test dependencies and runs the
lightweight fault-injection script. It is intentionally scoped to the fault
tests instead of running the full suite.

## 9. Limitations

- This is deterministic fault injection, not formal verification.
- This is not a full mutation-testing platform.
- The matrix checks coverage references, not semantic equivalence between every
  possible mutation and every verifier predicate.
- TypeScript JSONL storage parity remains roadmap.
- Fault IDs may need expansion as new public API or verifier predicates are
  added.

## 10. Safe Claims Unchanged

- Alpha-grade dual-SDK tamper-evident evidence substrate.
- Restricted canonicalization and canonical text hashing.
- SHA-256 hash-chain primitives.
- Evidence payload schemas and fail-closed validators.
- Sidecar signing and anchoring primitives.
- Read-only verifier predicates.
- CLI verify remains `chain_report_only`.
- JSONL storage is an alpha opt-in backend with read-only corruption scans.
- Deterministic fault-injection gate protects selected fail-closed invariants.

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
- Formal verification or exhaustive mutation testing.

## 12. Remaining P2

- Broader mutation operator generation for selected modules.
- Public API deprecation policy.
- Storage compatibility manifest and migration policy.
- TypeScript storage backend parity decision.
- Optional file-locking or database-backed storage adapter.

## 13. Validation Commands

| Command | Result |
|---|---|
| `scripts/check-fault-injection.sh` | PASS, active=50, covered=50, roadmap=1; Python fault tests 40 passed; TypeScript fault tests 39 passed |
| `scripts/check-public-api.sh` | PASS, python=127 symbols, typescript=171 exports, allowlist=130 asymmetries |
| `sdk/python/.venv/bin/pytest` | PASS, 774 passed |
| `cd sdk/python && .venv/bin/ruff check src tests` | PASS |
| `cd sdk/python && .venv/bin/mypy` | PASS |
| `cd sdk/typescript && npm test` | PASS, 490 passed |
| `cd sdk/typescript && npm run typecheck` | PASS |
| `cd sdk/typescript && npm run lint` | PASS, zero warnings |
| `bash scripts/check-schema-hashes.sh` | PASS |
| `bash scripts/check-fixture-hashes.sh` | PASS |
| `bash scripts/check-adr-frozen-blocks.sh` | PASS |
| `bash scripts/check-policy.sh` | PASS |
| `PATH="$PWD/sdk/python/.venv/bin:$PATH" bash scripts/test-cross-sdk-roundtrip.sh` | PASS |
| `jq empty docs/validation/p2_fault_injection_gate_20260518.json api/public/*.json` | PASS |
| `git diff --check` | PASS |

## 14. Status

PASS. P2.3 deterministic fault-injection gate is active locally and in the
`invariants` workflow. Safe claims and no-go claims are unchanged.
