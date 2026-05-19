# v0.0.4-alpha Release-Asset Upload Plan (Documentation Only)

This plan documents the exact artifacts prepared for a future `v0.0.4-alpha`
release. It is not executable authorization.

## Preconditions

- `main` contains the v0.0.4-alpha release-prep commit.
- `release/artifacts/v0.0.4-alpha/artifact-manifest.json` validates with `jq`.
- `release/artifacts/v0.0.4-alpha/checksums.sha256` matches local artifacts.
- Python artifacts pass `twine check`.
- TypeScript package passes `npm run build`, `npm test`, and `npm pack`.
- No forbidden positive release claims are present.
- Founder explicitly authorizes tag creation, GitHub Release creation, and
  registry publication in a separate release step.

## Prepared Files

```text
sdk/python/dist/attestplane-0.0.4a0-py3-none-any.whl
sdk/python/dist/attestplane-0.0.4a0.tar.gz
sdk/typescript/attestplane-attestplane-0.0.4-alpha.tgz
release/artifacts/v0.0.4-alpha/checksums.sha256
release/artifacts/v0.0.4-alpha/artifact-manifest.json
```

## Local Verification

```bash
scripts/check-release-assets-prep.sh
shasum -a 256 -c release/artifacts/v0.0.4-alpha/checksums.sha256
```

## Deferred Release Commands

These commands are intentionally not run as part of release prep:

```bash
git tag -a v0.0.4-alpha -m "v0.0.4-alpha"
git push origin v0.0.4-alpha
gh release create v0.0.4-alpha --prerelease --title "v0.0.4-alpha" \
  --notes-file docs/release-notes/v0.0.4-alpha.draft.md \
  sdk/python/dist/attestplane-0.0.4a0.tar.gz \
  sdk/python/dist/attestplane-0.0.4a0-py3-none-any.whl \
  sdk/typescript/attestplane-attestplane-0.0.4-alpha.tgz \
  release/artifacts/v0.0.4-alpha/checksums.sha256 \
  release/artifacts/v0.0.4-alpha/artifact-manifest.json
python -m twine upload sdk/python/dist/attestplane-0.0.4a0*
npm publish sdk/typescript/attestplane-attestplane-0.0.4-alpha.tgz --tag alpha
```

## Explicit Non-Actions in Release Prep

- Tag creation: not performed.
- GitHub Release create/edit/upload: not performed.
- PyPI publish: not performed.
- npm publish: not performed.
- npm `latest` dist-tag change: not performed.
- Deploy: not performed.
- Workflow dispatch: not performed.

## Claim Boundary

Uploading or publishing these artifacts would not change the alpha boundary.
They remain substrate artifacts only, with no operational readiness claim, no
regulatory certification claim, and no expansion of the current narrow verifier
scope.
