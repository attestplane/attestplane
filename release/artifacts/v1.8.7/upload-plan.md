# v1.8.7 Release-Asset Upload Plan

This plan documents artifacts prepared for the suffix-free stable release path.

## Prepared Files

```text
sdk/python/dist/attestplane-1.8.7-py3-none-any.whl
sdk/python/dist/attestplane-1.8.7.tar.gz
sdk/typescript/attestplane-attestplane-1.8.7.tgz
release/artifacts/v1.8.7/checksums.sha256
release/artifacts/v1.8.7/artifact-manifest.json
```

## Release Commands

```bash
gh release create v1.8.7 \
  --repo attestplane/attestplane \
  --verify-tag \
  --title "v1.8.7" \
  --notes-file docs/release-notes/v1.8.7.draft.md \
  release/artifacts/v1.8.7/artifact-manifest.json \
  release/artifacts/v1.8.7/checksums.sha256 \
  release/artifacts/v1.8.7/upload-plan.md
```
