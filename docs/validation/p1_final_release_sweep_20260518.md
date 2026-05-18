# P1 Final Release Sweep — 2026-05-18

## Scope

This sweep closes the final P1 release-hardening items for the
v0.0.2-alpha line after:

- P0 claim tightening
- P1 verifier closure
- P1 schema/canonical alignment

It does not upgrade the release posture. Attestplane remains an alpha-grade
dual-SDK tamper-evident evidence substrate. The CLI `verify` command remains
`chain_report_only` and must not be described as full ProofBundle, signature,
anchor, or compliance certification verification.

## Optional Extras / Export Surface

- Python root import smoke coverage was added for `import attestplane`.
- Python `__all__` now exports adapter symbols that are already part of the
  public surface and only exports signing symbols when optional signing
  dependencies are importable.
- Python anchoring package exports HTTP and Sigstore/Rekor optional symbols
  only when their optional dependencies are importable.
- TypeScript root package import smoke coverage was added for documented
  quickstart symbols and proof-bundle predicates.
- Optional sidecar primitives remain outside the core import path.

## Claim Drift Sweep

README, SDK README, policy docs, release notes, and validation docs were swept
for high-risk public claims. The remaining matches are no-go claim lists,
explicit negative/disclaimer language, tests, or validation/audit records.

The v0.0.2-alpha draft release notes explicitly preserve:

- alpha substrate posture
- `chain_report_only` CLI scope
- hardened verifier predicates
- strengthened Py/TS conformance
- no production readiness, compliance readiness, external certification, full
  ProofBundle verification, signed verification, or anchored verification claim

## Public API Surface Sweep

The companion report is:

- `docs/validation/public_api_surface_sweep_20260518.md`
- `docs/validation/public_api_surface_sweep_20260518.json`

No release-blocking missing documented symbols were found. Remaining Py/TS
asymmetries are P2 public API parity work.

## Examples Smoke Tests

There is no top-level `examples/` directory in this repository at this sweep
point. README and SDK README import examples are covered by:

- Python root/import smoke tests
- TypeScript root/named export smoke tests
- CLI chain/report-only behavior tests from the P0 claim tightening pass

No example text was found that upgrades the alpha posture or implies full,
signed, anchored, production, or compliance certification verification.

## Biome Warning Triage

The two existing TypeScript Biome warnings in `test/proof_bundle.test.ts` were
removed by replacing non-null assertions with a small checked helper. The final
lint target reports zero warnings.

## Safe Claims

- Alpha-grade dual-SDK tamper-evident evidence substrate.
- Restricted canonicalization and canonical text hashing.
- SHA-256 hash-chain primitives.
- Evidence payload schemas and fail-closed validators.
- Sidecar signing/anchoring primitives.
- Read-only verifier predicates.
- `attestplane verify` is chain/report-oriented only.

## No-Go Claims

- Production-ready, production-grade, or pre-beta-ready.
- Compliance-ready, EU AI Act compliant, DORA compliant, or GDPR compliant.
- Compliance certification or external certification.
- Full ProofBundle verifier in the CLI.
- Default CLI signed verification.
- Default CLI anchored verification.
- Runtime governance, execution authority, scheduler, gateway authority, or
  AIOS runtime integration.

## Remaining P2

- Generated public API diff gate for Python `__all__`, TypeScript `index.ts`,
  package metadata, and README snippets.
- Decide whether obligation registry and in-toto/DSSE helpers should gain
  TypeScript equivalents or remain documented as Python-only.
- Durable storage hardening, mutation testing, and broader fault-injection
  gates remain outside this P1 sweep.

## Validation Commands

| Command | Result |
|---|---|
| `sdk/python/.venv/bin/pytest` | PASS, 720 passed |
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
| `jq empty docs/validation/p1_final_release_sweep_20260518.json docs/validation/public_api_surface_sweep_20260518.json` | PASS |
| `git diff --check` | PASS |

## Readiness Verdict

Final P1 sweep passed. v0.0.2-alpha remains alpha-ready with claims aligned,
verifier predicates hardened, Py/TS conformance strengthened, optional import
surfaces smoke-tested, examples/import snippets covered, and lint warnings
cleared. It remains not production-ready, not compliance-ready, and not a
certification.
