# autodev-train Permission Audit — 2026-05-20

This audit records the non-secret release-mutation surface visible in the
local automation scripts after the `autodev-train` rename.

## Scope

- `scripts/release/`
- `release/alpha-train/`

This is a read-only audit. It does not change the automation runtime, does not
dispatch workflows, does not create tags, and does not publish packages.

## Command

```bash
rg -n "git push.*--tags|git push origin main|gh workflow run release-cd|npm publish|twine upload|dist-tag" \
  scripts/release release/alpha-train
```

## Findings

No direct local publication command was found for:

- `twine upload`
- local `npm publish`
- `git push --tags`
- `git push origin main`
- `gh workflow run release-cd`

The legacy alpha release train still contains expected alpha-era publication
handoff text and code:

- forbidden advisory command strings include `npm publish` and `twine upload`;
- remote GitHub workflow dispatch to `publish-python.yml` and
  `publish-typescript.yml`;
- npm registry reads for `dist-tags`;
- state records that the alpha dist-tag was synced by the npm publish
  workflow.

Those hits are not changed in this audit because modifying them would affect
automation behavior. They should be revisited only when the alpha-era engine is
split from the generic `autodev-train` runtime.

## Current Boundary

For RC and GA preparation, `autodev-train` should prepare code, docs, tests,
candidate metadata, and validation evidence only. Registry publication should
continue to go through GitHub Actions `release-cd`.

The observed scripts do not dispatch `release-cd` directly.
