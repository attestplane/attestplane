# P3 Release Roadmap

Baseline: `v0.0.3-alpha` GitHub prerelease.

Status: planning only. This roadmap does not create a release, move a tag, upload release assets, publish PyPI/npm packages, or upgrade Attestplane's alpha release claims.

Attestplane remains an alpha-grade dual-SDK tamper-evident evidence substrate. It is not production-ready, not compliance-ready, and not a certification system. CLI `attestplane verify` remains `chain_report_only` until a separately implemented and validated CLI ProofBundle verifier changes that scope.

## Roadmap Gates

Every P3 item must produce:

- implementation evidence in code, tests, fixtures, and validation docs;
- Python and TypeScript parity evidence when the item is cross-SDK;
- release-claim audit evidence that no production, compliance, certification, full-verifier, default signed/anchored, runtime governance, AIOS runtime, SLSA L3, database-grade, or destructive-repair claim was introduced prematurely;
- machine-readable validation JSON under `docs/validation/`;
- stable local gate command or CI job;
- clear pass/fail exit criteria.

## P3.1 CLI ProofBundle Verifier

**Goal**

Add an explicit CLI path that verifies ProofBundle evidence beyond the current `chain_report_only` CLI behavior. The CLI must distinguish full bundle checks from chain/report checks and report exact verification scope in both text and JSON output.

**Non-goals**

- Do not silently upgrade existing `attestplane verify` semantics without a clear scope flag or output field.
- Do not claim compliance certification or legal/regulatory readiness.
- Do not treat schema-shape validation as full evidence verification.
- Do not perform network, KMS, TSA, or external service calls from the core verification path.
- Do not mutate input bundles or storage.

**Required evidence**

- Python CLI tests for valid ProofBundle verification, malformed bundle rejection, unsupported `schema_version`, unsupported `proof_type`, missing required metadata, mismatched `chain_head`, invalid `policy_trace_refs`, embedded report mismatch, and read-only behavior.
- TypeScript verifier parity tests for the same ProofBundle fixtures where the TS SDK exposes matching verifier predicates.
- Shared positive and negative ProofBundle fixtures consumed by both SDKs.
- CLI JSON output fields such as `verification_scope`, `full_proof_bundle_verification`, `signature_verification_performed`, `anchor_verification_performed`, and `compliance_certification`.
- Documentation that clearly separates `chain_report_only` from full ProofBundle verifier mode.

**Gates**

- `sdk/python/.venv/bin/pytest sdk/python/tests/cli sdk/python/tests/test_proof_bundle*.py`
- `cd sdk/typescript && npm test -- proof_bundle`
- `scripts/check-fault-injection.sh`
- `scripts/check-public-api.sh`
- `bash scripts/check-policy.sh`
- new `scripts/check-cli-proofbundle-verifier.sh`
- `jq empty docs/validation/p3_cli_proofbundle_verifier_*.json`

**Risks**

- Users may confuse partial CLI chain checks with full ProofBundle verification.
- Bundle verifier may verify individual fields but miss cross-field closure.
- Python and TypeScript may diverge in fail-closed behavior.
- Existing release claims may accidentally imply that all verifier paths are complete.

**Exit criteria**

- CLI offers an explicit full ProofBundle verification mode or command.
- Default `attestplane verify` scope remains clear and machine-readable.
- All malformed, missing, unknown, inconsistent, and tampered bundle cases fail closed.
- Python and TypeScript shared fixtures agree on pass/fail outcomes.
- Documentation and release notes contain no full-verifier claim beyond the implemented CLI mode.

## P3.2 Signed and Anchored Verification

**Goal**

Add explicit signed and anchored verification paths that verify signatures and anchor evidence when requested, while preserving sidecar boundaries and keeping default CLI behavior honest.

**Non-goals**

- Do not make signing or anchoring mandatory for every bundle.
- Do not claim default signed verification or default anchored verification unless the default path actually performs those checks.
- Do not introduce long-lived private keys into the repository.
- Do not call live TSA, transparency log, KMS, or network services in deterministic core tests.
- Do not claim SLSA L3, certified provenance, or production-grade supply-chain security.

**Required evidence**

- Deterministic signing verifier fixtures for valid signature, missing signature, malformed envelope, wrong key, unsupported algorithm, expired or untrusted trust root, and mismatched signed payload.
- Deterministic anchor verifier fixtures for valid anchor, missing required anchor, empty anchor list, stale anchor, malformed anchor evidence, mismatched hash, and unsupported anchor proof type.
- Explicit trust-root fixture policy and no-secret test data review.
- CLI output that states whether signature verification and anchor verification were performed, skipped, not applicable, or failed.
- Read-only verifier tests for signed and anchored paths.

**Gates**

- `sdk/python/.venv/bin/pytest sdk/python/tests/signing sdk/python/tests/anchoring`
- `cd sdk/typescript && npm test -- signing anchoring`
- new `scripts/check-signed-anchor-verification.sh`
- `scripts/check-fault-injection.sh`
- `bash scripts/check-policy.sh`
- `jq empty docs/validation/p3_signed_anchored_verification_*.json`

**Risks**

- Verification status may be interpreted as stronger than the performed checks.
- Trust-root handling can become environment-dependent.
- Anchoring tests can become flaky if they depend on live services.
- Signature and anchor verification may become entangled with core substrate append behavior.

**Exit criteria**

- Signed verification and anchored verification are opt-in, explicit, deterministic, and fail closed.
- Missing evidence never produces a successful signed or anchored verification result.
- CLI and SDK JSON outputs distinguish `verified`, `failed`, `not_performed`, and `not_applicable`.
- No sidecar verifier path causes core `append()` to perform external I/O.

## P3.3 Release Assets and Checksums

**Goal**

Create a repeatable release asset hygiene flow for GitHub Release assets, source archives, checksum files, optional keyless signatures, and validation evidence packs.

**Non-goals**

- Do not upload release assets without explicit release-operator authorization.
- Do not publish PyPI/npm packages as part of this item.
- Do not claim SLSA L3, certified provenance, or production-grade supply-chain security.
- Do not require long-lived signing keys.
- Do not mutate existing tags or historical manifests.

**Required evidence**

- `release/artifacts/v0.0.3-alpha.manifest.json` style manifest for each release candidate.
- Deterministic checksum generation for local artifacts.
- Dry-run and execute modes for GitHub Release asset upload scripts.
- Optional keyless signing dry-run evidence when `cosign` is available.
- Validation docs that list every asset, checksum status, signature status, and whether the asset was uploaded.

**Gates**

- `scripts/check-release-provenance.sh`
- `python scripts/release/generate_checksums.py --help`
- `scripts/release/sign_assets_cosign_keyless.sh --dry-run`
- `scripts/release/upload_github_release_assets.sh --dry-run`
- `jq empty release/artifacts/*.json docs/validation/p3_release_assets_*.json`
- `bash scripts/check-policy.sh`

**Risks**

- GitHub-generated source archives may not have stable local checksums before release.
- Asset upload scripts could overwrite assets if clobber protection fails.
- Operators may mistake checksum hygiene for a certified provenance pipeline.
- Release manifests may drift from actual GitHub Release assets.

**Exit criteria**

- Every uploaded asset has an explicit manifest entry and checksum status.
- Upload scripts are dry-run by default and require explicit execution flags.
- No asset upload occurs in PR or default push workflows.
- Release docs explicitly say the pipeline is release hygiene, not a SLSA L3 or certified provenance claim.

## P3.4 npm and PyPI Publish Readiness

**Goal**

Prepare npm and PyPI/TestPyPI prerelease publishing readiness with trusted publishing/provenance checks, package metadata audits, and dry-run gates.

**Non-goals**

- Do not publish npm or PyPI packages without explicit release-operator authorization.
- Do not repoint npm `latest` for alpha releases unless explicitly authorized.
- Do not claim stable package readiness.
- Do not embed credentials or long-lived tokens in the repository.
- Do not publish packages whose README or metadata expands product claims.

**Required evidence**

- npm package dry-run output and package tarball content audit.
- Python sdist/wheel dry-run output and metadata audit.
- Trusted publishing readiness notes for GitHub OIDC, npm provenance, TestPyPI/PyPI environments, and required manual approvals.
- Package README claim scan.
- Versioning policy for alpha prereleases and dist-tags.

**Gates**

- `cd sdk/typescript && npm pack --dry-run`
- `cd sdk/typescript && npm publish --dry-run --provenance --tag alpha`
- `cd sdk/python && .venv/bin/python -m build --sdist --wheel`
- `cd sdk/python && .venv/bin/twine check dist/*`
- new `scripts/check-package-publish-readiness.sh`
- `bash scripts/check-policy.sh`
- `jq empty docs/validation/p3_package_publish_readiness_*.json`

**Risks**

- npm version may already exist, requiring a new prerelease version instead of unpublishing.
- Registry metadata can carry over stronger claims than repository docs.
- Trusted publishing setup may pass locally but fail in GitHub environment configuration.
- Accidental `latest` tag changes can make alpha packages look stable.

**Exit criteria**

- npm and PyPI dry-run package contents are audited and reproducible.
- Package metadata and READMEs contain only alpha-safe claims.
- Trusted publishing or token fallback policy is documented without exposing secrets.
- Publish remains blocked until a separate explicit release authorization.

## P3.5 Storage Backend Future Policy

**Goal**

Define future storage backend policy for JSONL, possible SQLite/Postgres backends, migration compatibility, repair modes, and backend capability reporting without expanding current storage claims.

**Non-goals**

- Do not implement SQLite/Postgres in this roadmap item.
- Do not claim ACID behavior, database-grade durability, or multi-writer correctness for JSONL.
- Do not enable automatic destructive repair by default.
- Do not change current JSONL record compatibility without migration evidence.
- Do not make storage backend selection an AIOS runtime concern.

**Required evidence**

- Storage backend policy document that defines capability fields, migration rules, unsupported-version behavior, repair semantics, and fixture requirements.
- Compatibility manifest update rules for new backends.
- Negative fixtures for unknown versions, corrupt records, unsupported repair operations, and unsafe concurrent semantics.
- CLI `doctor` or inspect output policy for backend capabilities.
- Public API impact assessment for any backend factory or storage export.

**Gates**

- `scripts/check-storage-compatibility.sh`
- `sdk/python/.venv/bin/pytest sdk/python/tests/storage`
- new `scripts/check-storage-backend-policy.sh`
- `scripts/check-public-api.sh`
- `scripts/check-fault-injection.sh`
- `bash scripts/check-policy.sh`
- `jq empty storage/compat/*.json docs/validation/p3_storage_backend_policy_*.json`

**Risks**

- Users may infer production durability from backend names.
- Migration code could become destructive by default.
- Backend-specific behavior may break hash-chain compatibility.
- Python-only storage backend features may create TypeScript parity ambiguity.

**Exit criteria**

- Future backend additions require compatibility manifest entries and negative fixtures.
- Any repair/truncate path is explicit opt-in and tested.
- JSONL remains documented as alpha opt-in and single-writer only.
- No storage documentation claims ACID, database-grade, or multi-writer correctness unless implemented and separately gated.

## P3.6 AIOS Integration Boundary

**Goal**

Define the AIOS integration boundary as evidence-adapter and optional bridge semantics only, preserving Attestplane as an independent compliance substrate and preventing runtime/control-plane scope creep.

**Non-goals**

- Do not import AIOS runtime, scheduler, gateway authority, billing, secret store, worker execution, or UI read model into the public Attestplane package.
- Do not claim AIOS runtime integration.
- Do not make Attestplane a control plane.
- Do not expose private/commercial AIOS internals through public fixtures or docs.
- Do not turn schema validation into runtime governance.

**Required evidence**

- Boundary audit that greps for AIOS runtime imports, crate names, internal schemas, and execution-authority verbs.
- Adapter/bridge design document that states allowed evidence semantics and forbidden runtime semantics.
- Negative tests for forbidden verbs and execution-authority claims.
- Public docs that label any AIOS bridge as optional, external, and evidence-only.
- Release-claim scan proving no runtime governance or AIOS runtime integration claim.

**Gates**

- `bash scripts/check-policy.sh`
- new `scripts/check-aios-boundary.sh`
- `scripts/check-fault-injection.sh`
- `scripts/check-public-api.sh`
- `rg -n "AIOSAdapter|aios\\.|runtime governance|execution authority|gateway authority|scheduler" sdk docs`
- `jq empty docs/validation/p3_aios_boundary_*.json`

**Risks**

- Public adapter work may accidentally absorb commercial AIOS implementation details.
- Users may interpret evidence ingestion as runtime execution authority.
- Naming can imply a stronger integration than the code provides.
- Bridge fixtures may leak internal schema assumptions.

**Exit criteria**

- AIOS-related public surface is limited to spec, documentation, fixtures, or optional evidence bridge packages.
- No public SDK imports AIOS runtime or internal control-plane code.
- Forbidden runtime/control-plane claims are enforced by policy gates.
- Release docs preserve Attestplane's independent substrate positioning.

## P3 Release Exit Criteria

P3 can be considered complete for the next alpha only when all planned P3 items have:

- validation docs and machine-readable JSON;
- deterministic local gates;
- claim-safety scans with no positive overclaims;
- public API manifest updates if any public exports are introduced;
- cross-SDK parity or documented asymmetry decisions;
- release notes that keep the release alpha-only unless separately authorized by evidence.

