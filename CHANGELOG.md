# Changelog

All notable changes to Attestplane are recorded here.

The format follows [Keep a Changelog 1.1](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning 2.0](https://semver.org/).

Each release links to its GitHub Release page where the wheel, sdist, npm
tarball, and CycloneDX SBOM are attached. Hashes published in the release
notes are the authoritative reference for supply-chain verification.

## [Unreleased]

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
- Attestplane CLI.

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
