# v0.4.5-alpha Release-Asset Upload Plan

This plan documents artifacts prepared by the local alpha release train.

## Prepared Files

```text
sdk/python/dist/attestplane-0.4.5a0-py3-none-any.whl
sdk/python/dist/attestplane-0.4.5a0.tar.gz
sdk/typescript/attestplane-attestplane-0.4.5-alpha.tgz
release/artifacts/v0.4.5-alpha/checksums.sha256
release/artifacts/v0.4.5-alpha/artifact-manifest.json
```

## Release Commands

```bash
git tag -a v0.4.5-alpha -m "v0.4.5-alpha"
git -c http.version=HTTP/1.1 push origin v0.4.5-alpha
gh release create v0.4.5-alpha --prerelease --title "v0.4.5-alpha" --notes-file docs/release-notes/v0.4.5-alpha.draft.md ...
gh workflow run publish-python.yml -f target=pypi --ref main
gh workflow run publish-typescript.yml -f tag=alpha -f dry_run=false --ref main
gh workflow run manage-npm.yml -f action=dist-tag-set-latest-to-version -f version=0.4.5-alpha --ref main
```

## Explicit Non-Actions in Release Prep

- Force push: not performed.
- npm `latest` dist-tag change: not performed during prep.
- npm `latest` dist-tag is synchronized only after npm alpha publish succeeds.
- Deploy: not performed.
- Workflow dispatch: not performed during prep.

## Claim Boundary

This alpha candidate is limited to the alpha package artifacts listed
above. Legal, compliance, certification, provenance-attestation,
and supply-chain assurance categories remain out of scope unless
backed by separate verified artifacts.
