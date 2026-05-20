# v0.8.0-beta.0 Release-Asset Upload Plan

This plan documents artifacts prepared for the public beta prerelease.

## Prepared Files

```text
sdk/python/dist/attestplane-0.8.0b0-py3-none-any.whl
sdk/python/dist/attestplane-0.8.0b0.tar.gz
sdk/typescript/attestplane-attestplane-0.8.0-beta.0.tgz
release/artifacts/v0.8.0-beta.0/checksums.sha256
release/artifacts/v0.8.0-beta.0/artifact-manifest.json
```

## Release Commands

```bash
git tag -a v0.8.0-beta.0 -m "v0.8.0-beta.0"
git -c http.version=HTTP/1.1 push origin main v0.8.0-beta.0
gh release create v0.8.0-beta.0 --prerelease --title "v0.8.0-beta.0" --notes-file docs/release-notes/v0.8.0-beta.0.draft.md ...
gh workflow run publish-python.yml -f target=pypi --ref v0.8.0-beta.0
gh workflow run publish-typescript.yml -f tag=beta -f dry_run=false --ref v0.8.0-beta.0
```

## Explicit Non-Actions in Release Prep

- Force push: not performed.
- npm `latest` dist-tag change: not performed.
- npm `beta` dist-tag is the prerelease channel for this beta cut.
- Deploy: not performed.
- Workflow dispatch: not performed during prep.

## Claim Boundary

This beta prerelease is limited to the package artifacts listed above. It is
not GA, not production-ready, and not a legal or compliance certification.
