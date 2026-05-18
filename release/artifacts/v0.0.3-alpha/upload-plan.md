# v0.0.3-alpha Release-Asset Upload Plan (Documentation Only)

This document describes the **future** GitHub Release asset upload sequence
for v0.0.3-alpha. It is **not** executed in the P3.3 branch. Execution
requires explicit founder authorization.

## Status of This Document

- Command sequence below is **documentation only**.
- Not executed in P3.3.
- No GitHub Release asset upload occurred during the generation of this
  plan.
- Future execution must be paired with a fresh release-steward checklist
  and tag-frozen safety check.

## Pre-Upload Safety Checklist (must all be true before running)

- `git rev-parse v0.0.3-alpha^{}` returns
  `9bde6338df008afe58d561b0ba66eaaf75e298ad` (tag still frozen).
- `release/artifacts/v0.0.3-alpha/artifact-manifest.json` is current and
  the listed SHA-256 values match the on-disk artefacts.
- `release/artifacts/v0.0.3-alpha/checksums.sha256` is current and
  `shasum -a 256 -c` (from repo root with the listed paths present)
  returns OK.
- `gh release view v0.0.3-alpha --json assets -q '.assets'` returns
  `[]` (i.e. no assets have been uploaded out-of-band).
- `npm view @attestplane/attestplane dist-tags` shows
  `latest: 0.0.1-alpha.1` (unchanged) and `alpha: 0.0.3-alpha`.
- Working tree is clean and `main` matches `origin/main`.

## Reproducible Local Build (must succeed before upload)

```bash
# Python — twine check must pass; sha256 must equal the manifest entry
cd sdk/python
rm -rf dist build
.venv/bin/python -m build
.venv/bin/twine check dist/*

# TypeScript — npm pack must produce the same shasum as the manifest entry
cd ../typescript
npm ci && npm run build && npm test
rm -f *.tgz
npm pack

cd ../..
shasum -a 256 -c release/artifacts/v0.0.3-alpha/checksums.sha256
```

## Upload Command Sequence (Documentation Only — DO NOT execute in P3.3)

```bash
# IMPORTANT: this command is documentation only. Do not execute it as part
# of P3.3 review or merge. Executing it modifies the public v0.0.3-alpha
# GitHub Release and is irreversible (assets can be deleted but not
# unpublished from caches/CDNs).

gh release upload v0.0.3-alpha \
  sdk/python/dist/attestplane-0.0.3a0.tar.gz \
  sdk/python/dist/attestplane-0.0.3a0-py3-none-any.whl \
  sdk/typescript/attestplane-attestplane-0.0.3-alpha.tgz \
  release/artifacts/v0.0.3-alpha/checksums.sha256 \
  release/artifacts/v0.0.3-alpha/artifact-manifest.json
```

## Post-Upload Verification (when uploading is authorized)

```bash
# Confirm GitHub Release now lists the 5 expected assets
gh release view v0.0.3-alpha --json assets \
  -q '.assets[] | "\(.name) \(.size) \(.digest)"'

# Download each asset and re-verify the local sha256 manifest
mkdir -p /tmp/v003-verify && cd /tmp/v003-verify
gh release download v0.0.3-alpha
shasum -a 256 -c <(grep -v '^#' \
  /Users/macworkers/Projects/attestplane/release/artifacts/v0.0.3-alpha/checksums.sha256 \
  | awk '{print $1"  "$2}' \
  | sed 's|.*/||')
```

## No-Go Claims (preserved even after a future upload)

- Uploading these assets does NOT make v0.0.3-alpha production-ready.
- SHA-256 checksums are integrity metadata, not cryptographic signing; they do not provide non-repudiation.
- This plan is NOT a SLSA L3 attestation and does NOT establish any SLSA level.
- This plan does NOT provide a certified provenance attestation.
- This plan is NOT a substitute for cosign or Sigstore signatures.
- This plan does NOT constitute a legal or compliance attestation.

## Out-of-Scope for v0.0.3-alpha (deferred, not in this plan)

- cosign signing of the GitHub Release assets is deferred.
- SLSA L3 attestation via actions/attest-build-provenance is deferred.
- Per-asset eIDAS qualified-timestamp anchoring is deferred.
- npm `latest` dist-tag promotion is deferred (no production-ready claim attaches).
- Any PyPI / npm version bump is deferred.
