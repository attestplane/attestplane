# v0.8.5-rc.2 Release-Asset Upload Plan

This plan documents artifacts prepared for the RC release path.

## Prepared Files

```text
sdk/python/dist/attestplane-0.8.5rc2-py3-none-any.whl
sdk/python/dist/attestplane-0.8.5rc2.tar.gz
sdk/typescript/attestplane-attestplane-0.8.5-rc.2.tgz
release/artifacts/v0.8.5-rc.2/checksums.sha256
release/artifacts/v0.8.5-rc.2/artifact-manifest.json
```

## Release Commands

```bash
git tag -a v0.8.5-rc.2 -m "v0.8.5-rc.2"
git push origin main
git push origin v0.8.5-rc.2
gh workflow run release-cd.yml -f release_tag=v0.8.5-rc.2 -f channel=rc -f dry_run=false --ref main
```

## Explicit Non-Actions in Release Prep

- Force push: not performed.
- npm `latest` dist-tag change: not performed during RC prep.
- Deploy: not performed.
- Workflow dispatch: not performed during local prep.
- Registry publication: not performed during local prep.

## Claim Boundary

This RC candidate is limited to the package artifacts listed above. Legal,
compliance, certification, provenance-attestation, and supply-chain assurance
categories remain out of scope unless backed by separate verified artifacts.
