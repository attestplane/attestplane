# Full Software Audit - 2026-05-18

Audit start commit: `4d1bf9c228f796f7dc7072f8ebc227e27f9d6150`
Branch at audit start: `main...origin/main`
Mode: read-only audit plus report generation; no product code changes.

## 1. Executive Summary

Attestplane is **alpha-ready as an OSS substrate**, but **not pre-beta-ready** and **not production-ready** until the verifier, cross-language edge cases, and claim-safety drift are tightened.

One-sentence true state: Attestplane is a real Python + TypeScript tamper-evident evidence substrate with meaningful conformance, schema, signing, anchoring, adapter, and CI work, but its public verifier currently verifies only chain/report consistency and several docs imply stronger release/compliance/verification coverage than the implementation can prove.

Current classification:

| Status | Verdict |
|---|---|
| OSS alpha | Yes, with blockers clearly documented |
| Pre-beta substrate | No, blocked by verifier and cross-SDK conformance gaps |
| Production/compliance runtime | No |
| Runtime governance engine | No, and should not be claimed |

Primary no-go: do not claim production governance, full ProofBundle verification, EU AI Act/DORA compliance, runtime execution authority, completed AIOS integration, or SLSA L3 release provenance.

## 2. Audit Scope

Audited:

- Python SDK under `sdk/python/src/attestplane` and `sdk/python/tests`
- TypeScript SDK under `sdk/typescript/src` and `sdk/typescript/test`
- Cross-SDK fixtures under `sdk/python/tests/conformance` and `tests/cross_sdk`
- JSON Schemas under `schemas/v1`
- CI workflows under `.github/workflows`
- Policy/gate scripts under `scripts`
- README, SDK READMEs, ADRs, architecture docs, release notes, policy docs
- AIOS boundary and absorption docs under `docs/adr`, `docs/architecture`, and `docs/validation`

Not fully audited:

- Live GitHub Actions execution history
- Live npm/PyPI/TestPyPI publication state
- Live TSA/Rekor/OCSP network behavior
- Full dependency CVE scan with fresh network access
- Full mutation testing run
- Opus reviewer consultation, because `ask_opus.sh reviewer ...` failed with `Not logged in - Please run /login`

## 3. Architecture Findings

Actual layer map from code and tests:

| Layer | Actual status | Evidence |
|---|---|---|
| Layer -1: cross-language conformance gates | Present | `sdk/python/tests/conformance`, `tests/cross_sdk`, `scripts/check-fixture-hashes.sh`, `cross-sdk-roundtrip.yml` |
| Layer 0: core primitives | Present | `canonical`, `canonical_text`, `hashchain`, `types`, `event_types` in both SDKs |
| Layer 1: adapter layer | Partial | `GenericRuntimeAdapter`, LangSmith, Langfuse; AIOS is docstring-only spec |
| Layer 2: sidecars | Partial/real | Python anchoring, signing, storage; TypeScript anchoring/signing subset |
| Layer 3: evidence/payload schemas | Present but validator drift | `schemas/v1`, payload validators, reason codes |
| Layer 4: verifier predicates | Partial | ProofBundle verifier, replay verifier, settlement verifier, signing and anchoring verifiers |
| Layer 5: conformance/replay infrastructure | Partial | shared fixtures and tests; TS negative chain fixtures missing |

Architecture boundary is mostly sound: `AttestSubstrate.append()` in Python and TypeScript stays core-only and does not call network, KMS, TSA, env, storage, or external I/O. Runtime authority is absent by design.

Architecture gaps:

- No canonical repo doc maps the user's Layer -1..5 terminology to shipped modules.
- README and release notes conflict on what is shipped in v0.0.2-alpha.
- AIOS adapter remains a spec-only docstring stub, which is correct, but public docs must keep that boundary explicit.
- Governance ingestion has schema and recipe coverage, but no first-class SDK builder.

## 4. Code Quality Findings

High-risk modules:

- `sdk/python/src/attestplane/verifier.py` and `sdk/typescript/src/verifier.ts`: chain-only ProofBundle verification can be mistaken for full verification.
- `sdk/typescript/src/canonical.ts`: UTF-16 key sorting, `undefined` as `null`, unsafe integer acceptance, and surrogate handling can break byte-level conformance.
- `sdk/python/src/attestplane/storage/jsonl.py`: direct writes do not meet the documented unchanged-on-failure atomicity contract.
- `sdk/python/src/attestplane/anchoring/worker.py` and `sdk/python/src/attestplane/signing/signer.py`: unexpected provider exceptions can drop queued work or hide failures.
- `sdk/python/src/attestplane/__init__.py` and `sdk/python/src/attestplane/anchoring/__init__.py`: optional-extra symbols appear in `__all__` even when imports are unavailable.

Positive code observations:

- Core hashchain functions are pure and I/O-free.
- Payload validators are cheap and explicit.
- Adapter ABCs reject forbidden execution/authority method names.
- Signing and anchoring sidecars are separated from substrate append.

## 5. Py/TS Cross-Language Findings

P1 gaps:

- TypeScript canonical object key sort uses UTF-16 ordering, not Unicode code-point ordering.
- TypeScript accepts `undefined`, array holes, and unsafe JS numbers in canonicalization.
- Surrogate rejection is not explicit and consistent across SDKs.
- TypeScript `Date` cannot preserve Python microsecond timestamp semantics.
- TypeScript auditor export drops framework coverage; Python can compute covered/uncovered obligation rows.
- TS does not replay Python's frozen negative chain fixtures.
- ProofBundle metadata closure is unchecked in both SDKs.
- Settlement verifier passes when an expected amount hash is supplied but the settlement event omits `amount_hash`.

P2 gaps:

- Adapter fixtures do not cover nested date/datetime, Unicode, null, and non-JSON-native hashing edges.
- API surface drift is not machine-gated by an allowlisted Py/TS surface diff.
- TypeScript substrate snapshots expose mutable object and `Uint8Array` references.

## 6. Security Findings

Security and supply-chain positives:

- Workflows use pinned action SHAs.
- No `pull_request_target` workflow was found.
- Most workflows use least-privilege `contents: read`.
- PyPI trusted publishing uses OIDC.
- npm publish uses provenance and a scoped environment.
- CodeQL, OSV, SBOM, Scorecard, reproducible-build, sign-release, and provenance workflows exist.

Security gaps:

- `attestplane verify` can return success for chain/report consistency while ignoring signatures, anchors, `policy_trace_refs`, and metadata closure.
- `verify_chain_with_anchors()` returns `ok=True` for zero anchors because `all([])` is vacuously true; callers can confuse "hash chain valid" with "anchored valid".
- `DigiCertProvider.DEFAULT_URL` is `http://timestamp.digicert.com`; token verification can still protect configured trust roots, but default metadata/privacy posture is weak.
- `FileKeyProvider` leaks local key paths in default `provider_id` and error messages.
- JSONL storage does not verify chain integrity on read and has no corruption repair/quarantine tool.
- Reproducible-build docs already acknowledge the current check is same-runner self-check, not independent dual-runner proof.

## 7. Verifier and Proof Findings

P0 blocker:

- Public CLI `attestplane verify` is only a chain/report verifier. It does not verify signatures, anchors, `policy_trace_refs`, metadata closure, or claimed `verification_method`. This is a release blocker if the next release presents it as full ProofBundle verification.

P1 gaps:

- ProofBundle verifiers do not compare `chain_metadata.head_hash_hex`, `head_seq`, `genesis_hash_hex`, or schema version against recomputed chain state.
- `policy_trace_refs` is builder-derived but not verified.
- Anchored verification can pass with zero anchors unless callers inspect `anchored_seqs`/`unanchored_seqs`.
- Settlement precondition is not fail-closed for missing `amount_hash` when the claim requires amount binding.
- Replay payload validators do not reject `proof_type*` authority fields because unknown fields are not rejected by hand validators.

The verifier surface must distinguish:

- `chain_only_valid`
- `bundle_metadata_valid`
- `signature_valid`
- `anchor_valid`
- `policy_trace_valid`
- `full_bundle_valid`

## 8. Test Coverage Findings

Coverage strengths:

- Python and TypeScript have substantial unit and conformance tests.
- Fixture hash locks protect committed conformance vectors.
- Schema hash locks protect `schemas/v1`.
- Python tests cover negative chain fixtures.
- Signing, anchoring, payload, reason-code, settlement, replay, and adapter tests exist.

Coverage gaps:

- TS does not replay `sdk/python/tests/conformance/negative/*.json`.
- No shared ProofBundle metadata tamper fixtures.
- No shared auditor-export framework coverage fixture.
- No settlement vector for expected amount hash with missing observed amount.
- Event payload schemas are not all included in Draft 2020-12 meta-validation tests.
- No schema/validator allowlist parity test for `additionalProperties: false`.
- Mutation testing is advisory and limited to `canonical_text.py` and `reason_codes.py`.
- Test/product ratio is meaningful for alpha, but snapshot/fixture volume should not be treated as production assurance.

## 9. Documentation and Claims Findings

Claim-safety issues:

- `README.md` has conflicting release status language: early sections describe v0.0.2-alpha features as shipped, while later sections describe v0.0.1 and list verifier/proof bundle/anchoring/signing/storage/adapters as not implemented.
- `docs/release-notes/v0.0.2-alpha.draft.md` is stale relative to current anchoring/signing/storage code.
- Some docs use strong framing like SLSA-for-AI-Agents and EU-regulated readiness; policy docs correctly add disclaimers, but release-facing docs must keep those caveats adjacent to the claims.
- `schemas/v1/README.md` documents fewer schemas than the lockfile tracks.

Safe documentation stance:

- Implemented: core substrate, canonical bytes, hash chain, payload schemas, proof bundle builder, chain verifier, sidecar signing/anchoring primitives, LangSmith/Langfuse evidence adapters.
- Deterministic/mock: conformance fixtures, test TSA/Rekor, recorded transports.
- Adapter stub: AIOS spec-only file, no concrete AIOS adapter.
- Experimental: anchoring/signing/JSONL/storage/CLI verifier until full verification semantics are hardened.
- Production not claimed: runtime governance, compliance certification, hosted product, enterprise controls, SLSA L3.

## 10. Release Readiness

Release readiness: **alpha with P0 blocked next-release messaging**.

P0 blockers:

| Area | Blocker |
|---|---|
| Verifier | Public `attestplane verify` is chain/report-only but can be read as full ProofBundle verification |
| Release claims | Next release must not claim full verifier, anchored verification, signed verification, or compliance readiness until P1 verifier gaps are fixed or clearly labeled partial |

P1 hardening:

- Add full ProofBundle metadata closure checks in Py/TS.
- Add explicit partial/full verifier result states.
- Verify `policy_trace_refs`.
- Fix TS canonical ordering, unsafe numbers, `undefined`, surrogate handling, and timestamp contract.
- Align payload validators with schema `additionalProperties: false`.
- Enforce `reason_code` format in payload validators.
- Add TS negative fixture replay.
- Fix settlement missing `amount_hash` fail-open.
- Fix TypeScript auditor export framework coverage.
- Tighten JSONL atomicity/read integrity contract.
- Make anchor empty-set behavior explicit and fail under anchored-verification policy.
- Repair docs/release notes status drift.
- Fix optional-extra `__all__` behavior.

P2 roadmap:

- API surface diff gate with intentional allowlist.
- First-class governance ingestion builder.
- Multi-writer durable storage backend.
- Stronger worker queue durability and quarantine semantics.
- Independent dual-runner reproducible build.
- Expanded mutation/fault-injection suite.
- More adapter edge fixtures and additional runtime adapters outside the substrate core.

Explicit no-go claims:

- EU AI Act compliant, DORA compliant, GDPR compliant, production-ready, production-grade governance.
- Full ProofBundle verifier.
- Runtime execution/governance/control-plane authority.
- Concrete AIOS integration in OSS repo.
- SLSA L3 provenance completed.
- Anchored/signed verification unless the verification path actually checks anchors/signatures.

Safe claims:

- Alpha OSS tamper-evident evidence substrate.
- Deterministic restricted canonical bytes for covered fixtures.
- SHA-256 hash-chain primitives.
- Python and TypeScript SDKs with meaningful conformance coverage.
- Payload schemas and validators for observed governance evidence.
- Read-only verifier predicates for replay and settlement observations.
- Sidecar signing/anchoring primitives, with production hardening still required.
- Runtime evidence adapter abstraction and LangSmith/Langfuse evidence normalization.

## 11. AIOS Absorption Recommendations

Good absorption candidates:

- Lease lifecycle evidence semantics.
- Policy decision traces.
- Verification-before-settlement as read-only predicate.
- Replay timeline and deterministic replay evidence shape.
- Event causality/correlation references.
- Worker/runtime adapter evidence.
- Audit projection and evidence pack semantics.
- Capability boundary as evidence, not authority.
- Governance timeline vocabulary.

Rejected from Attestplane core:

- Rust control plane runtime.
- Worker scheduler.
- Distributed execution protocol.
- Gateway authority.
- UI read model.
- Secret store.
- Billing/settlement execution.
- Real runtime side effects.
- Concrete AIOS adapter in this OSS repo.

Recommended phases:

| Phase | Recommendation |
|---|---|
| A | Absorb schema/evidence semantics only, with no AIOS crate names or runtime dependency |
| B | Harden verifier/replay/settlement predicates and reason-code outputs |
| C | Expand adapter bridge contracts and fixtures for generic runtimes |
| D | Keep optional AIOS bridge package outside this repo or in AIOS-owned code |
| E | Production hardening for storage, signing, anchoring, release provenance, not runtime expansion |

## 12. Action Plan

| Priority | Area | File/Module | Problem | Recommended Fix | Tests Needed | Release Impact |
|---|---|---|---|---|---|---|
| P0 | Verifier | `sdk/python/src/attestplane/cli/main.py`, `verifier.py`, `verifier.ts` | `verify` is chain/report-only | Rename/label partial verifier or implement full bundle verification states | Invalid signature/anchor/metadata CLI tests | Blocks next release claims |
| P1 | Verifier | `verifier.py`, `verifier.ts` | Metadata closure unchecked | Compare recomputed head/genesis/schema/method | Tampered metadata fixtures | Required pre-beta |
| P1 | ProofBundle | `proof_bundle.py`, `proof_bundle.ts` | `policy_trace_refs` unverified | Verify absent/present/order/exact refs | forged/missing/extra refs | Required pre-beta |
| P1 | Core TS | `canonical.ts` | UTF-16 key order | Sort by Unicode code point | astral key vector | Required pre-beta |
| P1 | Core TS | `canonical.ts` | accepts `undefined` and unsafe numbers | Reject undefined/holes/unsafe numbers | negative canonical tests | Required pre-beta |
| P1 | Core Py/TS | `canonical.py`, `canonical.ts` | surrogate behavior inconsistent | Reject surrogates explicitly | negative surrogate vector | Required pre-beta |
| P1 | Core TS | `types.ts`, `canonical.ts` | Date loses microseconds | Add timestamp value type or constrain TS to ms | `.123456Z` vector | Required pre-beta |
| P1 | Payload | `event_payloads.py`, `event_payloads.ts` | unknown fields accepted | Enforce schema allowlists | extra field vectors | Required pre-beta |
| P1 | Payload | `event_payloads.py`, `event_payloads.ts` | reason code regex not enforced | Call reason-code format validator | invalid reason-code vectors | Required pre-beta |
| P1 | Settlement | `settlement_verifier.py`, `settlement_verifier.ts` | missing amount hash can pass | Fail with `amount_hash_missing` | shared settlement vector | Required pre-beta |
| P1 | Anchoring | `anchoring/verifier.py`, `anchoring.ts` | empty anchors can pass `ok` | Add require-anchors policy or status split | empty-anchor negative test | Required pre-beta if anchoring claimed |
| P1 | Storage | `storage/jsonl.py` | atomicity/read integrity gaps | Clarify contract or write temp+rename/strict read | fsync/tamper/concurrency tests | Required before durable-storage claim |
| P1 | Docs | `README.md`, release notes | status contradictions | Reconcile shipped/partial/roadmap language | policy grep/gate | Blocks release claims |
| P1 | Exports | `__init__.py`, `anchoring/__init__.py` | optional extras in `__all__` | Conditional `__all__` or stubs with clear errors | substrate-only import/star tests | Required for packaging |
| P2 | CI | `sdk-typescript.yml` | shared conformance trigger too narrow | Include all shared fixture paths | CI path-filter test/review | Hardening |
| P2 | Governance | `governance_ingestion.schema.json` | schema but no builder | Add SDK builder or label as recipe | schema builder tests | Roadmap |
| P2 | Supply chain | `reproducible-build.yml` | same-runner self-check only | dual-runner proof | artifact comparison | Roadmap |

## 13. Machine-readable JSON

See `docs/validation/full_software_audit_20260518.json`.

## Verification Commands

Commands requested by the audit and their status:

| Command | Result |
|---|---|
| `git status --short --branch` | PASS at audit start: `## main...origin/main` |
| `git rev-parse HEAD` | PASS: `4d1bf9c228f796f7dc7072f8ebc227e27f9d6150` |
| `ask_opus.sh reviewer ...` | BLOCKED: local Claude auth returned `Not logged in - Please run /login` |
| `./scripts/check-schema-hashes.sh` | PASS in Agent D: `AP-EVD/1.0 schemas: 8 files, all canonical hashes match` |
| `.venv/bin/pytest` in `sdk/python` | PASS: 680 passed in 12.30s |
| `.venv/bin/ruff check src tests` in `sdk/python` | PASS: all checks passed |
| `.venv/bin/mypy` in `sdk/python` | PASS: no issues in 45 source files |
| `npm test` in `sdk/typescript` | PASS: 24 files, 415 tests passed |
| `npm run lint` in `sdk/typescript` | PASS exit 0, with 2 existing Biome warnings for non-null assertions in `test/proof_bundle.test.ts` |
| `npm run typecheck` in `sdk/typescript` | PASS |
| `bash scripts/check-schema-hashes.sh` | PASS: 8 schema hashes match |
| `bash scripts/check-fixture-hashes.sh` | PASS: 10 fixture hashes match |
| `bash scripts/check-adr-frozen-blocks.sh` | PASS: 13 Accepted ADR Decision sections match |
| `bash scripts/check-policy.sh` | PASS: all policy invariant checks passed |
| `jq empty docs/validation/full_software_audit_20260518.json` | PASS |
