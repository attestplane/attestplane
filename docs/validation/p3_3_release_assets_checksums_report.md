# P3.3 Release Assets + Checksums — Alpha Dry-Run Report

- **Date**: 2026-05-18
- **Branch**: `feat/p3-3-release-assets-checksums-20260518`
- **Base commit**: `544283f153a11e3c455b62d680de50a029537903` (`main`, P3.2 merged)
- **Verdict**: `P3.3ReleaseAssetsChecksumsReadyForPR`
- **Release target**: `v0.0.3-alpha`
- **Frozen tag target**: `9bde6338df008afe58d561b0ba66eaaf75e298ad` (untouched)

## Scope

P3.3 establishes the alpha-grade release-asset hygiene flow for v0.0.3-alpha:
local artefact build, SHA-256 checksum manifest, upload-plan documentation,
and a dry-run gate. **No upload, no publish, no tag movement, no GitHub
Release modification.** The branch is a hygiene baseline that becomes
executable only when founder authorizes a future upload step.

## Tag / Main / Build Split

| Surface | Value |
|---|---|
| `v0.0.3-alpha` annotated tag | `9bde6338df008afe58d561b0ba66eaaf75e298ad` (frozen) |
| `main` HEAD at P3.3 start | `544283f153a11e3c455b62d680de50a029537903` |
| `main` HEAD that produced the PyPI / npm registry packages | `51c4e6ac9bc08b6bdd4da9289bbf50b26f8d0457` |
| `main` HEAD that produced the P3.3 dry-run local artefacts | `544283f1…` (same as base commit) |

The local dry-run artefacts in this branch are **not byte-identical** to
the published registry artefacts; they are local-build evidence under
`main@544283f1`, while the registry artefacts were built and published
from `main@51c4e6a` via OIDC trusted-publishing workflows.

## Artifacts Built (locally, dry-run)

| Artifact | Path | Size | SHA-256 |
|---|---|---|---|
| Python wheel | `sdk/python/dist/attestplane-0.0.3a0-py3-none-any.whl` | 153,372 bytes | `623cd39e9ac4819f3a88a78715c4da7426882a371635c0c899249608a1d78e7d` |
| Python sdist | `sdk/python/dist/attestplane-0.0.3a0.tar.gz` | 207,215 bytes | `e37a78d0252eae0d831b9740dfce40d3972484ad47700070e907e2cfa74ff2db` |
| npm tarball | `sdk/typescript/attestplane-attestplane-0.0.3-alpha.tgz` | 110,826 bytes | `471d37afcd2c1cf1038de5d860df54bd8ea55e72f935a713562de718901c9e53` |

Build tools:
- Python: `python -m build` (hatchling), `twine check` PASSED for both
  wheel and sdist.
- TypeScript: `npm ci` + `npm run build` + `npm pack` (114 files).

## Checksums Generated

- `release/artifacts/v0.0.3-alpha/checksums.sha256` (text, 3 lines + headers)
- Format: compatible with `shasum -a 256 -c` from repo root.
- Each line corresponds to an artefact in the manifest.

## Artifact Manifest

`release/artifacts/v0.0.3-alpha/artifact-manifest.json` — schema
`p3_3_release_asset_dry_run_manifest.v1`. Fields:

- `release`, `github_release_url`, `frozen_tag_target`, `main_build_commit`,
  `tag_main_split_explanation`
- `artifacts[]` with `kind`, `version`, `sha256`, `size_bytes`,
  `build_source`, `build_tool`, `twine_check`, `registry_status`
- `hygiene_scan` with `forbidden_patterns_checked`, `result`,
  `files_scanned`
- `safety` block of negative invariants
- `safe_claims` and `no_go_claims`

## Upload Plan (documentation only)

`release/artifacts/v0.0.3-alpha/upload-plan.md` contains the future
`gh release upload v0.0.3-alpha ...` command sequence. It is **not
executed in this branch**. Execution requires explicit founder
authorization and a fresh release-steward checklist run.

## Hygiene Scan Result

Patterns scanned (case-insensitive): `.env`, `credentials`, `token`,
`secret`, `node_modules`, `__pycache__`, `.DS_Store`, `.git`,
`private_key`, `id_rsa`, `id_ed25519`, `pypirc`, `.npmrc`.

Result: **clean** — no forbidden entries in any of the 3 artefacts.

File counts: sdist 128, wheel 54, npm tarball 113.

## New Gate Script

`scripts/check-release-assets-dry-run.sh` (~150 LOC) — runs the full
local build, twine check, hygiene scan, SHA-256 cross-check, upload-plan
non-execution proof (GitHub Release assets must remain `[]`), tag-freeze
proof, claim scan, JSON validity, and `git diff --check`.

## Release Surface Invariants (verified post-build)

- `v0.0.3-alpha^{}` == `9bde6338…` (tag NOT moved)
- GitHub Release `v0.0.3-alpha`: `isPrerelease: true`, `assets: []` (unchanged)
- PyPI `attestplane==0.0.3a0`: published earlier, unchanged in P3.3
- npm `@attestplane/attestplane@0.0.3-alpha`: published earlier, unchanged
- npm dist-tags: `latest: 0.0.1-alpha.1` (not touched), `alpha: 0.0.3-alpha`
- No publish workflow triggered in P3.3.

## Safe Claims

- Release-asset dry-run hygiene flow exists and is reproducible.
- SHA-256 checksums generated for 3 artefacts; manifest and `checksums.sha256`
  agree byte-for-byte with on-disk artefacts.
- Artefact manifest is valid JSON, schema-versioned, and machine-readable.
- Upload plan is documented and explicitly marked non-executed.
- Hygiene scan reports no secret/credential/private-key/env leakage.
- Tag/main split is documented (tag at `9bde6338…`, build at `544283f1…`).
- No upload performed; GitHub Release assets remain empty.
- No PyPI publish in this branch; no npm publish in this branch.
- No tag movement; no retag; no force push.
- npm `latest` dist-tag not touched.

## No-Go Claims

- NOT production-ready.
- NOT compliance-ready.
- NOT certification-ready.
- NOT SLSA Level 3 attestation.
- NOT certified provenance.
- NOT production-grade supply-chain security control.
- Checksums are **integrity** metadata, not cryptographic **signing**;
  they do not provide non-repudiation.
- Local dry-run artefacts are NOT byte-identical to the published
  registry artefacts (different `main` commits, different
  `SOURCE_DATE_EPOCH`, different build host).
- Not a substitute for cosign / Sigstore signatures.
- Not a legal / compliance attestation by itself.

## Remaining P3.3 Limitations

- Local dry-run artefacts are not bit-identical to PyPI / npm
  registry artefacts. A reproducible-build dual-runner gate that
  produces byte-identical artefacts across main + registry build
  is out of P3.3 scope; that work is tracked separately in the
  Sprint-2 G5 dual-runner reproducible-build workflow.
- No cosign signature on the checksums manifest; signing is deferred.
- No `actions/attest-build-provenance` SLSA L3 attestation in this
  dry-run; that is a workflow-level concern handled by `provenance.yml`
  on real release events.
- The upload command is documented but not executed; future execution
  requires founder authorization and a fresh safety checklist.

## Readiness Recommendation

`P3.3ReleaseAssetsChecksumsReadyForPR` — the hygiene flow is complete,
the manifest and checksums are reproducible, the gate is fail-closed,
and the release surface is provably untouched. Ready to merge to `main`
as alpha foundation. Future upload execution is a separate, founder-
authorized step.
