# P2.5 Release Provenance Pipeline Validation

Date: 2026-05-18

## 1. Scope

This P2.5 hardening step adds an alpha-safe release artifact hygiene pipeline:

- release artifact manifest;
- checksum helper;
- manifest checker;
- optional cosign keyless signing dry-run helper;
- optional GitHub Release asset upload dry-run helper;
- manual workflow guardrails; and
- validation tests.

It does not tag, release, publish PyPI/npm artifacts, upload GitHub Release
assets, or modify `v0.0.2-alpha`.

## 2. Existing Release Supply-Chain Posture

Existing supply-chain workflows include CodeQL, OSV Scanner, OSSF Scorecard,
CycloneDX SBOM generation, reproducible Python wheel checks, npm provenance
publish support, Python trusted-publishing support, and previous signing /
provenance workflow scaffolding.

P2.5 does not treat those workflows as production-grade supply-chain security
or completed SLSA L3. It adds a local/manual gate that records artifact state
and keeps upload/signing behavior opt-in.

## 3. Artifact Manifest Added

Added:

- `release/artifacts/v0.0.2-alpha.manifest.json`
- `release/artifacts/README.md`

The manifest records:

- release: `v0.0.2-alpha`;
- tag target: `c8dabc964e9a2ba84453bb5150f14a9262ea8681`;
- status: `alpha_prerelease`;
- GitHub source archive as a published remote-generated asset;
- Python sdist, Python wheel, npm package, and validation evidence pack as not
  separately published for v0.0.2-alpha;
- `slsa_level_claimed: null`; and
- explicit no-go supply-chain claims.

## 4. Checksum Helper

Added:

- `scripts/release/generate_checksums.py`

The helper generates deterministic SHA-256 JSON or `sha256sum` output for local
files. It performs no network I/O and does not modify manifests.

## 5. Manifest Checker

Added:

- `scripts/release/check_release_artifact_manifest.py`
- `scripts/check-release-provenance.sh`

The checker validates schema version, release/tag/target commit metadata,
artifact boolean fields, checksum/signature requirements, deterministic JSON,
and forbidden supply-chain overclaims.

## 6. Optional Signing / Upload Dry-Run

Added:

- `scripts/release/sign_assets_cosign_keyless.sh`
- `scripts/release/upload_github_release_assets.sh`

Both scripts default to dry-run behavior. Signing requires `--execute`; upload
requires `--execute`. Missing `cosign` or `gh` is a graceful skip unless an
explicit require flag is used.

## 7. Workflow Integration

Updated:

- `.github/workflows/sign-release.yml`
- `.github/workflows/provenance.yml`

Both workflows are now manual. They do not run on `release: published`.
Signing/upload behavior remains dry-run unless explicitly requested through a
workflow input.

## 8. Claims Boundary

No release claim is upgraded. This gate does not claim:

- SLSA L3 completed;
- production-grade supply-chain security;
- certified provenance;
- default signed release assets;
- PyPI/npm publication; or
- complete provenance pipeline.

## 9. Commands Run

Full command results are recorded in
`p2_release_provenance_pipeline_20260518.json`. Summary:

- `ask_opus.sh architect ...` PASS: advisory review completed; dry-run and explicit-execute guardrails preserved.
- `scripts/check-release-provenance.sh` PASS.
- `scripts/check-fault-injection.sh` PASS: active=50, covered=50, roadmap/language-specific=1.
- `scripts/check-public-api.sh` PASS: python=127 symbols, typescript=193 exports, allowlist=138 asymmetries.
- `sdk/python/.venv/bin/pytest` PASS: 780 passed.
- `cd sdk/python && .venv/bin/ruff check src tests` PASS.
- `cd sdk/python && .venv/bin/mypy` PASS.
- `cd sdk/typescript && npm test` PASS: 502 passed.
- `cd sdk/typescript && npm run typecheck` PASS.
- `cd sdk/typescript && npm run lint` PASS: zero warnings.
- Schema, fixture, ADR, policy, and cross-SDK gates PASS.
- JSON validation and `git diff --check` PASS.
- Updated workflow YAML parsed successfully with Ruby's YAML parser.

## 10. Remaining P2/P3

- Decide when release asset signatures become required.
- Decide whether SBOMs should be uploaded as GitHub Release assets.
- Decide whether GitHub Artifact Attestations should become a blocking release
  gate.
- Add manifest entries with concrete checksums when future releases attach
  Python/npm artifacts.

## Validation Result

Status: PASS
