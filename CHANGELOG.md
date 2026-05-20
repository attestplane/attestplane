# Changelog

All notable changes to Attestplane are recorded here.

The format follows [Keep a Changelog 1.1](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0](https://semver.org/).

Each release links to its GitHub Release page where the wheel, sdist, npm
tarball, and CycloneDX SBOM are attached. Hashes published in the release
notes are the authoritative reference for supply-chain verification.

## [Unreleased]

### Preparing v0.8.5-rc.1

- Added a release-candidate compatibility policy for SDK exports,
  proof-bundle v1, verifier reason codes, canonical bytes, and
  `AP-EVD/1.0` fixture shape.
- Added ADR-0016 to freeze the public SDK and wire-format surfaces for
  the v0.8 RC line.
- Added ADR-0017 and a GitHub CD release runbook so package publication
  goes through GitHub Actions rather than local publish commands.
- Renamed the local automation programming train to `autodev-train`, keeping
  the old alpha-train wrapper as a compatibility alias, and documented that
  `release-cd` is its GitHub Actions publication stage.
- Expanded verifier conformance with tampered-report,
  schema-version-skew, and malformed policy-trace reference cases.
- Updated the npm publish workflow to support the `rc` dist-tag and to
  reject prerelease versions published with `latest`.
- Updated security support language for beta, RC, and future GA lines.

### Planned for v0.1.0 / M5 (2026-08-15)

- RFC 3161 Time-Stamp Authority anchoring per [ADR-0003](docs/adr/0003-tsa-rfc-3161-anchoring.md):
  pluggable `TSAProvider` interface, `MultiTSAProvider` composite,
  batch-tail anchoring off the `append()` critical path, sidecar
  `AnchorRecord` type (preserves the v0.0.1 chain contract).
- New verification API `verify_chain_with_anchors()` (does not overload
  the existing `verify_chain()`).
- Cross-language anchor conformance fixture
  `sdk/python/tests/conformance/anchor_vectors.json`.
- Production PyPI publication of `attestplane` (today on TestPyPI only).
- FastAPI / Express helper packages.

## [0.0.2-alpha] — release candidate

> Status: release candidate prepared on `main`; publish to TestPyPI /
> npm is gated on maintainer approval. When tagged, this section's
> heading becomes `[0.0.2-alpha] — YYYY-MM-DD`.

Second public alpha. Adds the v0.1 design surface (boundary ADR + event
taxonomy + attestation gates), the verifier library + CLI, four
substrate-level primitives (canonical-JSON spec, canonical-TEXT
primitive, hash-chain primitive — unchanged from v0.0.1, proof-bundle
builder), a JSONL storage backend, and obligation registries for EU AI
Act Article 12 and DORA Article 8. v0.0.1-alpha's hash-chain contract
is preserved bit-for-bit; all ten conformance vectors continue to
verify against the new code.

### Added — Architecture (ADRs and spec docs)

- [ADR-0004 — AIOS-to-Attestplane scope boundary](docs/adr/0004-aios-to-attestplane-boundary.md):
  ten enumerated boundary cases, twelve AIOS Q-items mapped to
  record-only events, universal rule that authority/execution stays in
  the runtime. ADR-0003's "Follow-up ADRs anticipated" renumbered
  accordingly (signing→0005, Sigstore→0006, retention→0007).
- [ADR-0005 — Event signing scheme](docs/adr/0005-event-signing-scheme.md):
  Ed25519 sidecar `SignatureRecord` (independent
  `signature_schema_version = 1`); two signing modes (segment-head
  default, per-event opt-in); `KeyProvider` abstraction with
  forbidden-verb gate (`revoke`/`rotate`/`delete`/`replace`) preserving
  ADR-0004 § 1 boundary; `TrustRoots` config + `verify_chain_with_signatures` /
  `verify_chain_full` verifier extension with plurality priority +
  coverage transitivity; five frozen `signature_vectors.json`
  cross-language conformance vectors. Strictly additive — v0.0.1-alpha
  bundles continue to verify byte-for-byte.
- [ADR-0006 § 4.1 amendment](docs/adr/0006-sigstore-rekor-redundant-anchor.md):
  formalises coexistence of `SigstoreRekorAnchor`'s submission key,
  ADR-0005 operator signing key, and Fulcio cert chain — independent
  layers in a single `ProofBundle`, with `MultiSignerProvider` and
  `MultiTSAProvider` composing freely.
- [ADR-0008 — Evidence event taxonomy v1](docs/adr/0008-evidence-event-taxonomy-v1.md):
  twelve canonical `event_type` strings, three independent version
  numbers (`chain.schema_version` / `anchor_schema_version` /
  `evidence_taxonomy_version`), substrate-stays-neutral rule.
- [`docs/spec/evidence-event-taxonomy-v1.md`](docs/spec/evidence-event-taxonomy-v1.md):
  per-event-type contract (required + optional payload fields,
  redactions, boundary anti-requirements, correlation-field guidance).
- [`docs/spec/canonical-json-v1.md`](docs/spec/canonical-json-v1.md):
  spec doc for the v0.0.1 restricted-JCS primitive, sufficient to
  reimplement in any language.
- [`docs/spec/canonical-text-v1.md`](docs/spec/canonical-text-v1.md):
  spec doc for the new text canonicalizer (NFC → lowercase →
  zero-width strip → whitespace fold → SHA-256).
- [`docs/architecture/ATTESTATION_GATES.md`](docs/architecture/ATTESTATION_GATES.md):
  five gates A1–A5 with three-tier pre-merge / nightly /
  release-blocker enforcement.
- [`schemas/v1/proof_bundle.schema.json`](schemas/v1/proof_bundle.schema.json)
  - [`schemas/v1/auditor_export.schema.json`](schemas/v1/auditor_export.schema.json):
  JSON Schemas for the v1 wire-format artifacts. Default
  `forbidden_fields` list (13 critical terms) is the redaction floor.

### Added — Python SDK (`sdk/python/src/attestplane/`)

- `adapters/` — `GenericRuntimeAdapter` ABC with 15-name
  forbidden-verb gate at class-creation time; `aios_spec.py`
  docstring-only contract stub (zero executable surface, by design).
- `event_types.py` — twelve constants, `ALL_EVENT_TYPES_V1` frozenset,
  `is_known_v1_event_type()` predicate, `EVIDENCE_TAXONOMY_VERSION = 1`.
- `obligations/` — read-only registry loader. EU AI Act Article 12
  ships 8 entries (4 `field_supported`); DORA Article 8 ships 5
  entries (1 `field_supported`). Locked `implementation_status` enum
  rejected at both schema level and loader level.
- `storage/` — `AbstractStorageBackend` ABC with 9-name
  forbidden-mutating-verb gate (ADR-0002 immutability invariant);
  `JsonlStorageBackend` reference implementation (one ChainedEvent
  per line, fsync on every append, strict-format read).
- `proof_bundle.py` — `ProofBundleBuilder`, `FrameworkMapping`,
  `build_auditor_export()`, `DEFAULT_FORBIDDEN_FIELDS`.
- `verifier.py` — `verify_proof_bundle()` and
  `verify_proof_bundle_file()`; surfaces bundle/walk disagreement as
  a distinct signal.
- `canonical_text.py` — second canonicalization primitive (text-only,
  independent of canonical-JSON).
- `cli/` — `attestplane` CLI with four subcommands (`verify`,
  `inspect`, `export`, `doctor`); each supports `--json`. Entry-point
  registered via `[project.scripts]`; `pip install attestplane`
  installs the executable.
- `signing/` (ADR-0005, optional `[signing]` extras):
  - `base.py` — `SIGNATURE_SCHEMA_VERSION`, `SignatureRecord`,
    `SigningMaterial`, `SignaturePolicy`, `KeyProvider` ABC with
    `__init_subclass__` forbidden-verb gate, `derive_key_id`, error
    hierarchy (`SigningError` / `KeyProviderError` /
    `SignatureVerificationError` / `KeyBoundaryError`).
  - `providers.py` — `InMemoryKeyProvider`, `FileKeyProvider`,
    `EnvKeyProvider`, `MultiSignerProvider`.
  - `signer.py` — hybrid sync + background-worker `Signer` (mirrors
    `Anchorer`); `_build_segment_head_payload`, `_build_per_event_payload`.
  - `trust_roots.py` — `yaml.safe_load`-only loader, 1 MB cap, strict
    schema, `key_id` cross-check.
  - `verifier_ext.py` — `verify_chain_with_signatures`,
    `verify_chain_full`, `BundleVerificationResult`,
    `SingleSignatureResult`, 5-value `SignatureStatus` enum with
    plurality priority + coverage transitivity (option a).
- `proof_bundle.py` extension — additive `signatures` field on
  `ProofBundleBuilder`, `_serialize_signature_record` /
  `deserialize_signature_record` round-trip.

### Added — TypeScript SDK (`sdk/typescript/src/`)

- `adapters.ts` — `GenericRuntimeAdapter` abstract class with
  constructor-time forbidden-verb check.
- `event_types.ts` — twelve constants + literal types + ReadonlySet
  - `EventTypeV1` discriminated union.
- `proof_bundle.ts` — TypeScript port. Builds bundle bytes that are
  byte-identical to the Python builder's output.
- `verifier.ts` — TypeScript port (async; uses `node:fs/promises`).
- `canonical_text.ts` — TypeScript port. Loads the SAME
  `text_vectors.json` as the Python SDK; CI fails on any byte drift.
- `signing/` (ADR-0005 T6, no new runtime dependencies — `node:crypto`
  primitives only):
  - `base.ts` — TypeScript mirror of Python `base.py`. Errors,
    `SignatureRecord` interface + `validateSignatureRecord`,
    `KeyProvider` abstract class with constructor-time forbidden-verb
    gate, `SigningMaterial`, `SignaturePolicy`, `deriveKeyId`.
  - `providers.ts` — `InMemoryKeyProvider` / `FileKeyProvider` /
    `EnvKeyProvider` / `MultiSignerProvider`. Ed25519 seed →
    `KeyObject` via RFC 8410 PKCS#8 wrap (the JWK seed path in the
    architect's initial recipe was rejected by Node 22 because it
    requires the public `x` field; PKCS#8 wrap is byte-equal to
    Python's `cryptography` serialisation).
  - `signer.ts` — sync-only `Signer` with `signEvent`,
    `signSegmentHead`, `buildSegmentHeadPayload`, `buildPerEventPayload`
    (background worker explicitly deferred per `adr_0005_t6_review_20260517.md`
    § 1 decision 5).
  - `trust_roots.ts` — JSON-only loader (TS opts out of YAML to keep
    `uuid` as the only runtime dep), 1 MB cap, strict schema,
    `parseTrustRoots` for non-file callers.
  - `verifier_ext.ts` — `verifyChainWithSignatures`, `verifyChainFull`,
    `BundleVerificationResult` (re-exported as
    `ChainBundleVerificationResult` to avoid collision with the
    `proof_bundle.ts` verifier result type), `STATUS_RANK`.
- `proof_bundle.ts` extension — `SerializedSignatureRecord` interface,
  `serializeSignatureRecord` / `deserializeSignatureRecord`, additive
  `ProofBundle.signatures?` field, `ProofBundleBuilder.extendSignatures`.

### Added — Conformance fixtures

- `sdk/python/tests/conformance/negative/` — five frozen broken-chain
  fixtures (`broken_chain.json`, `missing_event.json`,
  `reordered_event.json`, `duplicate_event.json`,
  `malformed_payload.json`) pinning gates A2 and A3.
- `sdk/python/tests/conformance/text_vectors.json` — 12 frozen text
  canonicalization vectors.
- `sdk/python/tests/conformance/signature_vectors.json` — 5 frozen
  event-signing vectors (ADR-0005 T7) covering segment-head + per-event
  modes, multi-signer plurality, unknown-key + tampered-payload negative
  cases. Both SDKs replay this file; cross-language drift fails CI on
  either side.

### Added — Documentation

- [`docs/policy/`](docs/policy/forbidden_claims.md): three-file
  claim-safety triad — `forbidden_claims.md`, `allowed_claims.md`,
  `claims_policy.md`. Locks the four-value `implementation_status`
  enum as the only permitted public-facing phrasing for
  obligation-registry citations.
- [`docs/architecture/aios_to_attestplane_migration_plan_20260517.md`](docs/architecture/aios_to_attestplane_migration_plan_20260517.md):
  5-bucket classification + 8-phase roadmap. Binding policy per
  ADR-0004 § 6.
- README "Designed and merged on main since v0.0.1-alpha" section
  enumerates the new architecture surface; Compliance Framework
  Mapping table updated to cite locked `implementation_status` values.

### Changed

- README anticipated-ADR numbering corrected: event signing →
  ADR-0005; Sigstore/Rekor → ADR-0006; storage backend → "anticipated
  storage-backend ADR" (no slot pre-committed). The original ADR-0004
  slot is taken by the boundary ADR.

### Compatibility

- v0.0.1-alpha hash-chain contract preserved bit-for-bit. The ten
  frozen `vectors.json` entries continue to verify against the
  v0.0.2-alpha code on every CI run.
- `ChainedEvent` shape, `event_hash` computation, `prev_hash` linkage,
  canonical-JSON byte determinism — all unchanged.
- New event_type strings from the v1 taxonomy are NOT validated at
  the canonicalization layer; any v0.0.1 chain containing arbitrary
  `event_type` strings continues to verify.

### Test counts

- Python: 256/256 passing (from 87 at v0.0.1-alpha).
- TypeScript: 150/150 passing (from 51 at v0.0.1-alpha).
- mypy --strict: clean on 19 Python source files.
- tsc build: clean.

### Out of scope for the OSS substrate

- Concrete AIOS adapter implementation: lives in the AIOS commercial
  repository per ADR-0004 § 4. `aios_spec.py` ships the docstring-only
  contract; no implementation.
- AIOS-run-to-proof-bundle example: depends on the concrete AIOS
  adapter implementation; belongs in the AIOS commercial repository.

## [0.0.1-alpha] — 2026-05-17

First public alpha release. Substrate core, in-memory only, two
language SDKs reaching cross-language byte conformance.

- **GitHub Release:** [v0.0.1-alpha](https://github.com/attestplane/attestplane/releases/tag/v0.0.1-alpha)
- **TestPyPI:** [`attestplane==0.0.1`](https://test.pypi.org/project/attestplane/0.0.1/) (sandbox)
- **npm:** [`@attestplane/attestplane@0.0.1`](https://www.npmjs.com/package/@attestplane/attestplane) (production, `alpha` dist-tag)

### Added

- **Python SDK** at `sdk/python/`: `AttestSubstrate`, `EventDraft`,
  `AuditEvent`, `ChainedEvent`, `ChainHead`, `SubjectRef`,
  `canonicalize()`, `chain_extend()`, `hash_event()`, `verify_chain()`,
  `genesis_head()`, `head_of()`. 66 tests, 98.45 % coverage.
- **TypeScript SDK** at `sdk/typescript/`: equivalent surface, 51
  tests. Identical canonical bytes verified against the Python SDK by
  13 cross-language conformance tests on every CI run.
- **Restricted-JCS canonicalization** (ADR-0002 §2): NFC strings,
  signed-int64 integers, floats forbidden, RFC 3339 microsecond UTC
  datetimes with `Z` suffix, base64url bytes without padding,
  alphabetically sorted object keys.
- **EU AI Act Article 12(2)(a) field set** built into `EventDraft`:
  `session_id`, `reference_db_ref`, `matched_input_ref`,
  `human_verifier`.
- **GDPR Article 4(5) pseudonymization typing**: the `SubjectRef`
  strong type with `scheme ∈ {sha256_salted, opaque, none}`.
- **Frozen cross-language conformance vectors**: ten
  `(EventDraft → event_hash hex)` pairs in
  `sdk/python/tests/conformance/vectors.json`. Schema version `1`;
  these hex values are a permanent external contract.
- **Hypothesis property tests** on the Python SDK
  (`tests/test_properties.py`): determinism, dict-order invariance,
  tamper detection at each position, ~1000 randomized cases per CI run.
- **ADRs accepted**: 0001 (Apache 2.0 + DCO), 0002 (substrate core),
  0003 (RFC 3161 anchoring design — code lands in v0.1).
- **Governance**: CONTRIBUTING (English + Chinese), DCO sign-off
  enforcement, CODE_OF_CONDUCT (Contributor Covenant 2.1),
  GOVERNANCE (Singapore Pte. Ltd. entity, founder + succession),
  TRADEMARK (™ policy until USPTO/EUIPO registration), SECURITY
  (vulnerability disclosure + Article 12 retention),
  CONTRIBUTORS acknowledgment list, CODEOWNERS auto-review routing.
- **Supply-chain CI**:
  - CodeQL on Python and GitHub Actions (security-extended +
    security-and-quality query packs).
  - OSSF Scorecard publishing weekly to scorecard.dev.
  - OSV-Scanner daily against the dependency graph.
  - REUSE 3.3 compliance.
  - Reproducible wheel build verification in CI (byte-identical
    across two builds under `SOURCE_DATE_EPOCH`).
  - All third-party GitHub Actions SHA-pinned to immutable commits.
  - CycloneDX SBOM artifact generated on every push to `main`.
  - Org-level 2FA enforced (no SMS); branch protection on `main`
    (no force-push, no deletion, linear history).
- **Publishing workflows** with OIDC trusted publishing (Python →
  TestPyPI + PyPI) and `--provenance` Sigstore attestation
  (TypeScript → npm).
- **First external contribution** by @nvphungdev:
  [#4 English CONTRIBUTING guide](https://github.com/attestplane/attestplane/pull/4)
  (Chinese preserved at `CONTRIBUTING_zh.md`).

### Hash algorithm

`SHA-256` for v0.0.1, per ADR-0002 §2. Any future migration to BLAKE3
or a different algorithm requires a `schema_version` bump (currently
locked at `1`) and a new conformance vector set.

### Known gaps not yet covered

In-memory storage only (no DB backend). Single-process only (no
multi-writer concurrency). No RFC 3161 anchoring (designed in
ADR-0003, code lands in v0.1). No event signing. No CLI. No FastAPI /
Express helpers. No Rust SDK. Reproducibility verified for wheels but
not for sdists — sdist drift is open and tracked.

### Supply-chain hashes

| Artifact | sha256 |
|---|---|
| `attestplane-0.0.1-py3-none-any.whl` | `fea8dd0c33d35cd331f9a214eab4b1d03d5facb59ef84316ce82f57c23443eab` |
| `attestplane-0.0.1.tar.gz` | `58e16e2b8491145f3ffc9b34d01390dd11dfeb15c96003d8aaff40ae40c726dd` |
| `attestplane-npm-0.0.1.tgz` | `0a41ba9028e5ff2be98c06c41d9c878eafa6f92260a0e707e393ebdb703d97d3` |
| `attestplane-python.cdx.json` | `120ee654f737d030d4d773b446dcdc46a46ce7155949a083d9548aae0e002f52` |
| `attestplane-python.cdx.xml` | `8be0a3597d99183e46898fb39f50b9fcb4dbb0cc4a0fd604d2e13adb5ed4a411` |

[Unreleased]: https://github.com/attestplane/attestplane/compare/v0.0.1-alpha...HEAD
[0.0.1-alpha]: https://github.com/attestplane/attestplane/releases/tag/v0.0.1-alpha
