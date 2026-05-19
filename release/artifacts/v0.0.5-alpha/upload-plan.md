# v0.0.5-alpha Release-Asset Upload Plan

This plan documents the exact artifacts prepared for the `v0.0.5-alpha`
release. The founder has explicitly authorized the release step for the
available package platforms.

## Preconditions

- `main` contains the v0.0.5-alpha release-prep commit.
- `release/artifacts/v0.0.5-alpha/artifact-manifest.json` validates with `jq`.
- `release/artifacts/v0.0.5-alpha/checksums.sha256` matches local artifacts.
- Python artifacts pass `twine check`.
- TypeScript package passes `npm run build`, `npm test`, and `npm pack`.
- No forbidden positive release claims are present.
- GitHub Release is created as a prerelease.
- PyPI publishes `attestplane==0.0.5a0`.
- npm publishes `@attestplane/attestplane@0.0.5-alpha` with the `alpha` tag only.

## Prepared Files

```text
sdk/python/dist/attestplane-0.0.5a0-py3-none-any.whl
sdk/python/dist/attestplane-0.0.5a0.tar.gz
sdk/typescript/attestplane-attestplane-0.0.5-alpha.tgz
release/artifacts/v0.0.5-alpha/attestplane-python-sbom.cdx.json
release/artifacts/v0.0.5-alpha/attestplane-python-sbom.cdx.xml
release/artifacts/v0.0.5-alpha/attestplane-typescript-sbom.cdx.json
release/artifacts/v0.0.5-alpha/checksums.sha256
release/artifacts/v0.0.5-alpha/artifact-manifest.json
```

## Local Verification

```bash
scripts/check-release-assets-prep.sh
shasum -a 256 -c release/artifacts/v0.0.5-alpha/checksums.sha256
```

## Release Commands

```bash
git tag -a v0.0.5-alpha -m "v0.0.5-alpha"
git push origin v0.0.5-alpha
gh release create v0.0.5-alpha --prerelease --title "v0.0.5-alpha" \
  --notes-file docs/release-notes/v0.0.5-alpha.draft.md \
  sdk/python/dist/attestplane-0.0.5a0.tar.gz \
  sdk/python/dist/attestplane-0.0.5a0-py3-none-any.whl \
  sdk/typescript/attestplane-attestplane-0.0.5-alpha.tgz \
  release/artifacts/v0.0.5-alpha/attestplane-python-sbom.cdx.json \
  release/artifacts/v0.0.5-alpha/attestplane-python-sbom.cdx.xml \
  release/artifacts/v0.0.5-alpha/attestplane-typescript-sbom.cdx.json \
  release/artifacts/v0.0.5-alpha/checksums.sha256 \
  release/artifacts/v0.0.5-alpha/artifact-manifest.json
gh workflow run publish-python.yml -f target=pypi --ref main
gh workflow run publish-typescript.yml -f tag=alpha -f dry_run=false --ref main
```

## Explicit Non-Actions in Release Prep

- Force push: not performed.
- npm `latest` dist-tag change: not performed.
- Deploy: not performed.

## Claim Boundary

Uploading or publishing these artifacts does not change the alpha boundary.
They remain substrate artifacts only, with no operational readiness claim, no
regulatory certification claim, no legal advice claim, and no expansion of the
current narrow verifier scope.
