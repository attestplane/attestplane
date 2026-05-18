# Release Provenance Pipeline

## Purpose

This document describes Attestplane's alpha-safe release artifact hygiene
pipeline. The pipeline is designed to make release assets easier to inventory,
hash, optionally sign, and review without changing the project's release
posture.

## What This Pipeline Does

- Records release artifact expectations in `release/artifacts/*.manifest.json`.
- Validates artifact manifests with `scripts/release/check_release_artifact_manifest.py`.
- Generates deterministic SHA-256 checksum reports with
  `scripts/release/generate_checksums.py`.
- Provides dry-run local gates through `scripts/check-release-provenance.sh`.
- Provides optional dry-run helpers for cosign keyless signing and GitHub
  Release asset upload.
- Documents npm provenance and TestPyPI/PyPI trusted-publishing readiness.

## What This Pipeline Does Not Claim

This pipeline does not claim:

- production-grade supply-chain security;
- SLSA L3 completion;
- certified provenance;
- compliance readiness;
- release asset signing by default;
- GitHub Release asset upload by default; or
- PyPI/npm publication.

The in-toto / DSSE SDK helpers remain deterministic shape helpers. They are not
a complete release provenance pipeline.

## Artifact Manifest

Release manifests live under `release/artifacts/`.

For v0.0.2-alpha, `release/artifacts/v0.0.2-alpha.manifest.json` is a
post-release hygiene baseline. It records that the GitHub source archive is a
published generated asset, while Python sdists, wheels, npm package tarballs,
and separate validation bundles were not published as release assets.

## Checksums

Generate checksums locally:

```bash
python scripts/release/generate_checksums.py --base dist dist/*
```

The helper performs local file hashing only. It does not contact GitHub, PyPI,
npm, Sigstore, or any transparency log.

## Optional Cosign Keyless Signing

Dry-run signing:

```bash
bash scripts/release/sign_assets_cosign_keyless.sh dist/*
```

Execute mode requires explicit `--execute`:

```bash
bash scripts/release/sign_assets_cosign_keyless.sh --execute --require-cosign dist/*
```

The script uses cosign keyless signing when executed. It does not use or create
long-lived signing keys. Local execute mode is additionally refused unless
`ATTESTPLANE_ALLOW_LOCAL_SIGN=1` is set, so normal local runs stay dry-run.

## GitHub Release Asset Upload Dry-Run

Dry-run upload:

```bash
bash scripts/release/upload_github_release_assets.sh --tag v0.0.2-alpha dist/*
```

Execute mode requires explicit `--execute`. The script does not create a
GitHub Release and does not modify tags.

## npm Provenance Readiness

The TypeScript publish workflow uses `npm publish --provenance` when a future
maintainer explicitly runs a real publish path. This P2.5 gate does not publish
to npm.

## TestPyPI / PyPI Trusted Publishing Readiness

The Python publish workflow is configured around OIDC trusted publishing. This
P2.5 gate does not publish to TestPyPI or PyPI.

## Manual Workflows

The release signing and provenance workflows are manual dry-run first:

- `.github/workflows/sign-release.yml`
- `.github/workflows/provenance.yml`

They do not run automatically on release publication after this P2.5 hardening
step.

## Future Roadmap

- Add a release asset pack generation step once Python and npm artifacts are
  intentionally attached to a GitHub Release.
- Decide when cosign keyless signatures should become required.
- Decide when GitHub Artifact Attestations should become a blocking release
  gate.
- Decide whether SBOMs should be uploaded as first-class GitHub Release assets.
