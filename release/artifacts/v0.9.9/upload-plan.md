# v0.9.9 Release-Asset Upload Plan

This plan documents artifacts prepared for the suffix-free stable release path.

## Prepared Files

```text
sdk/python/dist/attestplane-0.9.9-py3-none-any.whl
sdk/python/dist/attestplane-0.9.9.tar.gz
sdk/typescript/attestplane-attestplane-0.9.9.tgz
release/artifacts/v0.9.9/checksums.sha256
release/artifacts/v0.9.9/artifact-manifest.json
```

## Release Commands

```bash
git tag -a v0.9.9 -m "v0.9.9"
git push origin main
git push origin v0.9.9
gh workflow run release-cd.yml -f release_tag=v0.9.9 -f channel=latest -f dry_run=false --ref main
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
