# P2.4 Parity: Obligations and in-toto / DSSE API Decisions

Date: 2026-05-18

## Scope

This validation records P2.4 public API parity decisions for:

- Python-only obligation registry exports.
- Python-only in-toto / DSSE helper exports.
- TypeScript structural exports and camelCase ergonomics.
- Public API manifest and allowlist updates after minimal TypeScript parity.

This is a P2 hardening change only. It does not change the v0.0.2-alpha release posture, does not upgrade CLI verification, and does not introduce runtime governance.

## Public API Asymmetry Summary

The P2.1 public API gate identified intentional Python/TypeScript asymmetries in three relevant groups:

- Python obligation registry loaders and registry classes.
- Python in-toto / DSSE shape helper functions.
- TypeScript structural types, interfaces, and camelCase helper names.

P2.4 resolves the first two groups with minimal TypeScript parity where the Python surface is static, deterministic, and does not perform legal interpretation or cryptographic signing.

## Obligation Registry Decision

Decision: implement minimal TypeScript static registry parity.

The Python obligation registry is a static informational mapping for registry entries such as EU AI Act Article 12 and DORA Article 8. It validates and exposes stable obligation ids, event-type mappings, reason-code mappings, implementation status, and disclaimer text.

The TypeScript SDK now provides the same static registry content and lookup/filter helpers:

- `loadEuAiActArticle12`
- `loadDoraArticle8`
- `loadAllRegistries`
- `obligationById`
- `obligationsByEventType`
- `obligationsByImplementationStatus`
- `ObligationEntry`
- `Registry`
- `ObligationRegistryError`
- `ObligationImplementationStatus`

Boundary: this registry is informational mapping only. It is not legal advice, not compliance readiness, and not certification.

## in-toto / DSSE Decision

Decision: implement minimal TypeScript shape parity.

The Python in-toto / DSSE helpers build deterministic in-toto Statement v1 objects and unsigned DSSE envelope shapes. They do not sign, verify signatures, manage keys, submit transparency-log entries, or implement a complete SLSA provenance pipeline.

The TypeScript SDK now provides equivalent shape helpers:

- `proofBundleToInTotoStatement`
- `statementToDsseEnvelope`
- `dsseEnvelopeToStatement`
- `canonicalJsonBytes`
- `PREDICATE_TYPE_V1`
- `DSSE_PAYLOAD_TYPE`
- `STATEMENT_TYPE`
- `IntotoError`
- `IntotoStatement`
- `IntotoSubject`
- `DsseEnvelope`
- `DsseSignature`

Boundary: these helpers are deterministic envelope/statement helpers only. They are not default signed verification, not release asset signing, not SLSA L3, and not a supply-chain attestation pipeline.

## TS Structural Exports Decision

TypeScript keeps structural exports that do not have one-to-one Python root equivalents, including types and interfaces used for compile-time ergonomics. These remain allowlisted as `language_specific` or `experimental`.

CamelCase TypeScript helper names remain intentional language-specific API shape. Python keeps snake_case names.

## Implemented Parity

Implemented now:

- Static TypeScript obligation registry parity for EU AI Act Article 12 and DORA Article 8 mapping data.
- TypeScript in-toto Statement v1 and DSSE envelope shape helpers.
- TypeScript tests for registry loading, stable ids, lookup/filter behavior, defensive frozen copies, disclaimers, DSSE envelope roundtrip, malformed envelope rejection, deterministic payload bytes, and caller-supplied signature preservation without verification.
- Public API manifest update for new TypeScript exports.
- Public API allowlist cleanup for resolved exact-name asymmetries and new camelCase/structural asymmetries.

## Deferred Parity and Reasons

Deferred:

- Python `bundle_to_dsse_envelope` remains a Python convenience helper. TypeScript exposes the equivalent composition through `proofBundleToInTotoStatement` and `statementToDsseEnvelope`.
- Python JSONL storage exports remain Python-only; TypeScript storage backend parity remains roadmap.
- TypeScript structural types remain language-specific; Python parity is not required.

## Public API Manifest Impact

Updated files:

- `api/public/typescript_v1.json`
- `api/public/py_ts_allowlist_v1.json`

The public API drift gate passes with:

- Python symbols: 127
- TypeScript exports: 193
- Allowlisted asymmetries: 138

## Tests Added

Added:

- `sdk/typescript/test/obligations.test.ts`
- `sdk/typescript/test/intoto.test.ts`

Focused validation:

- `cd sdk/typescript && npm test -- obligations intoto`
- `cd sdk/typescript && npm run typecheck`
- `cd sdk/typescript && npm run lint`
- `scripts/check-public-api.sh`

Full validation:

- `scripts/check-fault-injection.sh` PASS: active=50, covered=50, roadmap/language-specific=1.
- `scripts/check-public-api.sh` PASS: python=127 symbols, typescript=193 exports, allowlist=138 asymmetries.
- `sdk/python/.venv/bin/pytest` PASS: 774 passed.
- `cd sdk/python && .venv/bin/ruff check src tests` PASS.
- `cd sdk/python && .venv/bin/mypy` PASS.
- `cd sdk/typescript && npm test` PASS: 502 passed.
- `cd sdk/typescript && npm run typecheck` PASS.
- `cd sdk/typescript && npm run lint` PASS: zero warnings.
- `bash scripts/check-schema-hashes.sh` PASS.
- `bash scripts/check-fixture-hashes.sh` PASS.
- `bash scripts/check-adr-frozen-blocks.sh` PASS.
- `bash scripts/check-policy.sh` PASS.
- `PATH="$PWD/sdk/python/.venv/bin:$PATH" bash scripts/test-cross-sdk-roundtrip.sh` PASS.
- `jq empty docs/validation/p2_parity_obligations_intoto_20260518.json api/public/*.json` PASS.
- `git diff --check` PASS.

## Safe Claims Unchanged

Attestplane remains an alpha-grade dual-SDK tamper-evident evidence substrate with restricted canonicalization, hash-chain primitives, evidence payload schemas, read-only verifier predicates, sidecar signing/anchoring primitives, public API drift checks, durable JSONL guardrails, and deterministic fault-injection gates.

## No-Go Claims Unchanged

No production readiness, compliance readiness, certification, EU AI Act/DORA/GDPR compliance, full CLI ProofBundle verification, default signed verification, default anchored verification, runtime governance, AIOS runtime integration, ACID/database-grade durability, multi-writer correctness, formal verification, exhaustive mutation testing, legal compliance certification, or full SLSA provenance pipeline is claimed.

## Remaining P2/P3

- Decide whether TypeScript should get a direct `bundleToDsseEnvelope` convenience helper in a later alpha.
- Decide whether TypeScript should get JSONL storage backend parity in a later alpha.
- Consider a generated shared obligation fixture if obligation registries grow beyond the current static pair.
- Consider explicit experimental stability marking for in-toto / DSSE helper symbols in a later public API manifest revision.

## Validation Result

Status: PASS

Full validation commands and results are recorded in `p2_parity_obligations_intoto_20260518.json`.
