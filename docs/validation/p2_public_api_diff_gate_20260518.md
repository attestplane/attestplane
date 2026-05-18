# P2.1 Public API Diff Gate — 2026-05-18

## 1. Scope

This P2.1 hardening adds a lightweight, executable public API drift gate for
the Python and TypeScript SDK root export surfaces. It does not change release
claims, CLI verification scope, runtime behavior, storage durability, package
publishing, tags, or release status.

## 2. Baseline Release

Baseline release: `v0.0.2-alpha`.

The manifests freeze the alpha public surface as released:

- `api/public/python_v1.json`
- `api/public/typescript_v1.json`
- `api/public/py_ts_allowlist_v1.json`

## 3. Python Public API Baseline

The Python extractor reads `sdk/python/src/attestplane/__init__.py` with Python
`ast` and extracts root `__all__` entries without importing `attestplane` or
optional sidecar dependencies.

Baseline count: 127 root symbols.

Documented symbols locked by this gate:

- `AttestSubstrate`
- `EventDraft`
- `SubjectRef`

## 4. TypeScript Public API Baseline

The TypeScript extractor reads `sdk/typescript/src/index.ts` and parses root
export declarations conservatively. It avoids adding a TypeScript AST
dependency for this P2.1 gate.

Baseline count: 171 root exports.

Documented symbols locked by this gate:

- `AttestSubstrate`
- `ProofBundleBuilder`
- `makeEventDraft`
- `makeSubjectRef`
- `verifyProofBundle`

## 5. Allowed Asymmetries

The allowlist records 130 exact Py/TS root API asymmetries:

- 86 `language_specific`
- 22 `experimental`
- 21 `roadmap`
- 1 `intentional`

Known P2 parity decisions remain allowlisted, not release blockers:

- Python-only obligation registry loaders and types.
- Python-only in-toto/DSSE helpers.
- Python-only JSONL storage exports.
- TypeScript structural type aliases/interfaces.
- TypeScript ergonomic helpers such as `VERSION`, `Signer`, and `TrustRoots`.
- Language-specific snake_case versus camelCase/factory naming.

Every allowlist entry requires a `reason` and `review_by`.

## 6. Drift Rules

The checker fails closed when:

- a manifest uses the wrong `schema_version`
- the current extractor output has a new unrecorded public symbol
- an `alpha_public` baseline symbol disappears
- a documented baseline symbol disappears
- a Py/TS asymmetry is missing from the allowlist
- an allowlist entry lacks `reason` or `review_by`
- a manifest or allowlist is not deterministic sorted JSON

The allowlist also records forbidden drift:

- removing an `alpha_public` symbol without a deprecation note
- changing symbol stability silently
- documenting a symbol that is not exported
- exporting a new `alpha_public` symbol without manifest update

## 7. Checker Commands

Local gate:

```bash
scripts/check-public-api.sh
```

Direct extractor/checker commands:

```bash
python scripts/api/extract_python_public_api.py --out /tmp/attestplane_python_api.json
python scripts/api/extract_typescript_public_api.py --out /tmp/attestplane_ts_api.json
python scripts/api/check_public_api_manifest.py \
  --python-current /tmp/attestplane_python_api.json \
  --typescript-current /tmp/attestplane_ts_api.json \
  --python-baseline api/public/python_v1.json \
  --typescript-baseline api/public/typescript_v1.json \
  --allowlist api/public/py_ts_allowlist_v1.json
```

## 8. CI / Local Integration

Local script:

- `scripts/check-public-api.sh`

CI integration:

- `.github/workflows/invariants.yml`
- job: `public-api`

This keeps the gate close to the schema/fixture/ADR invariant gates without
expanding release workflows.

## 9. Remaining Limitations

- This is a root export drift gate, not a semantic compatibility checker.
- The TypeScript extractor is conservative text parsing, not a full compiler
  API pass.
- The gate does not prove runtime behavior parity.
- The gate does not force Python and TypeScript to expose identical APIs.
- Public API deprecation policy remains a future P2/P3 governance decision.

## 10. Safe Claims Unchanged

- Alpha-grade dual-SDK tamper-evident evidence substrate.
- Restricted canonicalization and canonical text hashing.
- SHA-256 hash-chain primitives.
- Evidence payload schemas and fail-closed validators.
- Sidecar signing and anchoring primitives.
- Read-only verifier predicates.
- CLI verify remains `chain_report_only`.

## 11. No-Go Claims Unchanged

- Production-ready or production-grade.
- Compliance-ready.
- Certification or external certification.
- EU AI Act, DORA, or GDPR compliant.
- Full CLI ProofBundle verifier.
- Default CLI signed verification.
- Default CLI anchored verification.
- Runtime governance, execution authority, scheduler, gateway authority, or
  AIOS runtime integration.

## 12. Validation Commands

| Command | Result |
|---|---|
| `scripts/check-public-api.sh` | PASS, python=127 symbols, typescript=171 exports, allowlist=130 asymmetries |
| `sdk/python/.venv/bin/pytest` | PASS, 725 passed |
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
| `jq empty docs/validation/p2_public_api_diff_gate_20260518.json api/public/*.json` | PASS |
| `git diff --check` | PASS |

## 13. Status

PASS. The P2.1 public API diff gate is active locally and in the
`invariants` workflow. Safe claims and no-go claims are unchanged.
