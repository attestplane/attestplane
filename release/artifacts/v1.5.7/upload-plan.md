# v1.5.7 Release-Asset Upload Plan

This plan documents artifacts prepared for the suffix-free stable release path.

## Prepared Files

```text
sdk/python/dist/attestplane-1.5.7-py3-none-any.whl
sdk/python/dist/attestplane-1.5.7.tar.gz
sdk/typescript/attestplane-attestplane-1.5.7.tgz
release/artifacts/v1.5.7/checksums.sha256
release/artifacts/v1.5.7/artifact-manifest.json
```

## Release Commands

```bash
git tag -a v1.5.7 -m "v1.5.7"
git push origin main
git push origin v1.5.7
gh workflow run release-cd.yml -f release_tag=v1.5.7 -f channel=latest -f dry_run=false --ref main
```

## Explicit Non-Actions in Release Prep

- Force push: not performed.
- npm `ca` dist-tag change: not performed by stable autodev train.
- Deploy: not performed.
- Workflow dispatch: not performed during local prep.
- Registry publication: not performed during local prep.

## Claim Boundary

This stable package cut is limited to the package artifacts listed above.
Legal, compliance, certification, provenance-attestation, and supply-chain
assurance categories remain out of scope unless backed by separate verified
artifacts.
