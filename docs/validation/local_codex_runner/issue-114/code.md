# Issue 114 Release-Integrity Note

Plan ID: `fcb4bf04f6b37833`

Audit timestamp: `2026-05-22T12:56:45Z`

Runner limitation: this phase used only local repository files and local command
output. It did not post to GitHub because the runner prompt forbids external
tools and services.

## Boundary Decision

No anomalies found in the local `v1.6.1..v1.6.2` release boundary.

The tag range contains exactly two commits:

```text
fa2ee99f9f893615ff9ae378342e7b882fa61c78 chore(release): prepare v1.6.2
f181c6d4af6d6b792e53b17c8d5426cb2c9d805f fix: fetch opus planned issues after creation
```

Classification:

- `f181c6d4af6d6b792e53b17c8d5426cb2c9d805f` is the only real behavioral
  change shipped after `v1.6.1`. Its diff is limited to
  `scripts/release/plan_to_issues.py` and
  `sdk/python/tests/test_plan_to_issues.py`.
- `fa2ee99f9f893615ff9ae378342e7b882fa61c78` is release-prep metadata for
  `v1.6.2`. It bumps Python and TypeScript package versions from `1.6.1` to
  `1.6.2`, updates the matching lockfiles/version tests, and adds
  `docs/release-notes/v1.6.2.draft.md` plus `release/artifacts/v1.6.2/*`.

## Release-Prep Metadata Check

`fa2ee99` matches the local published/prepared metadata boundary:

- Python package metadata: `sdk/python/pyproject.toml`,
  `sdk/python/src/attestplane/__init__.py`, `sdk/python/uv.lock`, and
  `sdk/python/tests/test_import_surface.py` all move to `1.6.2`.
- TypeScript package metadata: `sdk/typescript/package.json`,
  `sdk/typescript/package-lock.json`, and
  `sdk/typescript/src/index_version.ts` all move to `1.6.2`.
- Release artifacts are added under `release/artifacts/v1.6.2/`.
- `release/artifacts/v1.6.2/artifact-manifest.json` records
  `source_state.target_commit` as
  `f181c6d4af6d6b792e53b17c8d5426cb2c9d805f`.
- The manifest records non-actions for deploy, force push, npm `ca` movement,
  release publish, and workflow dispatch during prep.
- The manifest records non-claims for certified provenance, compliance
  certification, production readiness, and SLSA L3.

`CHANGELOG.md` and `tools/release-notes` have no local diff in
`v1.6.1..v1.6.2`; the generated release-note metadata present in this boundary
is `docs/release-notes/v1.6.2.draft.md`.

## Required Diff Summary

Command:

```bash
git diff v1.6.1..v1.6.2 -- ':!CHANGELOG.md' ':!**/package*.json' ':!**/version*'
```

Summary from the matching `--stat` command:

```text
 docs/release-notes/v1.6.2.draft.md              | 35 ++++++++++++++++
 release/artifacts/v1.6.2/artifact-manifest.json | 50 ++++++++++++++++++++++
 release/artifacts/v1.6.2/checksums.sha256       |  3 ++
 release/artifacts/v1.6.2/upload-plan.md         | 37 +++++++++++++++++
 scripts/release/plan_to_issues.py               | 16 +++++--
 sdk/python/pyproject.toml                       |  2 +-
 sdk/python/src/attestplane/__init__.py          |  2 +-
 sdk/python/tests/test_import_surface.py         |  2 +-
 sdk/python/tests/test_plan_to_issues.py         | 55 +++++++++++++++++++++++++
 sdk/python/uv.lock                              |  2 +-
 sdk/typescript/src/index_version.ts             |  2 +-
 11 files changed, 197 insertions(+), 9 deletions(-)
```

Interpretation:

- Non-release real change: `scripts/release/plan_to_issues.py` and
  `sdk/python/tests/test_plan_to_issues.py`, both from `f181c6d`.
- Release metadata/artifact note changes: `docs/release-notes/v1.6.2.draft.md`
  and `release/artifacts/v1.6.2/*`, both from `fa2ee99`.
- Version-source and lock metadata: Python package files plus
  `sdk/typescript/src/index_version.ts`, from `fa2ee99`.
- Excluded package-manifest files are limited to
  `sdk/typescript/package.json` and `sdk/typescript/package-lock.json`, both
  version-only `1.6.1` to `1.6.2` updates.

## Validation Exception

The issue-required helper command was run and failed because the module is not
present in this checkout:

```text
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named scripts.release.audit_boundary
```

This task did not add or modify release tooling to manufacture a pass. The
boundary decision above is based on the local git evidence recorded in
`test.md`.

