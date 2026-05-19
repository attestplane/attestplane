# v0.0.8-alpha Release-Asset Upload Plan

This plan documents artifacts prepared by the local alpha release train.

## Prepared Files

```text
sdk/python/dist/attestplane-0.0.8a0-py3-none-any.whl
sdk/python/dist/attestplane-0.0.8a0.tar.gz
sdk/typescript/attestplane-attestplane-0.0.8-alpha.tgz
release/artifacts/v0.0.8-alpha/checksums.sha256
release/artifacts/v0.0.8-alpha/artifact-manifest.json
```

## Release Commands

```bash
git tag -a v0.0.8-alpha -m "v0.0.8-alpha"
git push origin v0.0.8-alpha
gh release create v0.0.8-alpha --prerelease --title "v0.0.8-alpha" --notes-file docs/release-notes/v0.0.8-alpha.draft.md ...
gh workflow run publish-python.yml -f target=pypi --ref main
gh workflow run publish-typescript.yml -f tag=alpha -f dry_run=false --ref main
```

## Explicit Non-Actions in Release Prep

- Force push: not performed.
- npm `latest` dist-tag change: not performed.
- Deploy: not performed.
- Workflow dispatch: not performed during prep.

## Claim Boundary

This alpha candidate is limited to the alpha package artifacts listed
above. Legal, compliance, certification, provenance-attestation,
and supply-chain assurance categories remain out of scope unless
backed by separate verified artifacts.
