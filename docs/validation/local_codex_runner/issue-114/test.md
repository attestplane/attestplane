# Issue 114 Local Validation Transcript

Plan ID: `fcb4bf04f6b37833`

Audit timestamp: `2026-05-22T12:56:45Z`

## Required Commands

```bash
git log --oneline v1.6.1..v1.6.2
```

```text
fa2ee99 chore(release): prepare v1.6.2
f181c6d fix: fetch opus planned issues after creation
```

```bash
git diff --stat v1.6.1..v1.6.2
```

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
 sdk/typescript/package-lock.json                |  4 +-
 sdk/typescript/package.json                     |  2 +-
 sdk/typescript/src/index_version.ts             |  2 +-
 13 files changed, 200 insertions(+), 12 deletions(-)
```

```bash
python -m scripts.release.audit_boundary --from v1.6.1 --to v1.6.2
```

Exit code: `1`

```text
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named scripts.release.audit_boundary
```

## Additional Local Checks

```bash
git log --format='%H %P %s' v1.6.1..v1.6.2
```

```text
fa2ee99f9f893615ff9ae378342e7b882fa61c78 f181c6d4af6d6b792e53b17c8d5426cb2c9d805f chore(release): prepare v1.6.2
f181c6d4af6d6b792e53b17c8d5426cb2c9d805f f2a55d4baea9d27bfac2ea40fd835c0f3e237048 fix: fetch opus planned issues after creation
```

```bash
git show --name-status --oneline f181c6d
```

```text
f181c6d fix: fetch opus planned issues after creation
M  scripts/release/plan_to_issues.py
M  sdk/python/tests/test_plan_to_issues.py
```

```bash
git show --name-status --oneline fa2ee99
```

```text
fa2ee99 chore(release): prepare v1.6.2
A  docs/release-notes/v1.6.2.draft.md
A  release/artifacts/v1.6.2/artifact-manifest.json
A  release/artifacts/v1.6.2/checksums.sha256
A  release/artifacts/v1.6.2/upload-plan.md
M  sdk/python/pyproject.toml
M  sdk/python/src/attestplane/__init__.py
M  sdk/python/tests/test_import_surface.py
M  sdk/python/uv.lock
M  sdk/typescript/package-lock.json
M  sdk/typescript/package.json
M  sdk/typescript/src/index_version.ts
```

```bash
git diff --stat v1.6.1..v1.6.2 -- ':!CHANGELOG.md' ':!**/package*.json' ':!**/version*'
```

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

```bash
git diff --name-status v1.6.1..v1.6.2 -- ':!CHANGELOG.md' ':!**/package*.json' ':!**/version*'
```

```text
A  docs/release-notes/v1.6.2.draft.md
A  release/artifacts/v1.6.2/artifact-manifest.json
A  release/artifacts/v1.6.2/checksums.sha256
A  release/artifacts/v1.6.2/upload-plan.md
M  scripts/release/plan_to_issues.py
M  sdk/python/pyproject.toml
M  sdk/python/src/attestplane/__init__.py
M  sdk/python/tests/test_import_surface.py
M  sdk/python/tests/test_plan_to_issues.py
M  sdk/python/uv.lock
M  sdk/typescript/src/index_version.ts
```

```bash
git diff --name-status v1.6.1..v1.6.2 -- CHANGELOG.md tools/release-notes
```

```text

```

Result: no local diff in `CHANGELOG.md` or `tools/release-notes`.

## Focused Diff Findings

`f181c6d` changes `scripts/release/plan_to_issues.py` to:

- append `Plan ID: ...` to generated planned-task bodies when absent,
- treat existing legacy issues without a plan ID as reusable when source and
  title match,
- fetch uploaded issues after create using both plan IDs and task titles.

`f181c6d` also adds test coverage in
`sdk/python/tests/test_plan_to_issues.py` for the legacy issue reuse and
post-create fetch behavior.

`fa2ee99` changes only release-prep metadata:

- package/version strings from `1.6.1` to `1.6.2`,
- `docs/release-notes/v1.6.2.draft.md`,
- `release/artifacts/v1.6.2/artifact-manifest.json`,
- `release/artifacts/v1.6.2/checksums.sha256`,
- `release/artifacts/v1.6.2/upload-plan.md`.

`release/artifacts/v1.6.2/artifact-manifest.json` records
`source_state.target_commit` as
`f181c6d4af6d6b792e53b17c8d5426cb2c9d805f`.

## Markdown Lint Fix Validation

```bash
/Users/macworkers/.npm/_npx/3c2a9ea6c4b6e0a2/node_modules/.bin/markdownlint-cli2 'docs/validation/local_codex_runner/issue-114/*.md' '!.github/**'
```

```text
markdownlint-cli2 v0.22.1 (markdownlint v0.40.0)
Finding: docs/validation/local_codex_runner/issue-114/*.md !.github/**
Linting: 7 file(s)
Summary: 0 error(s)
```

```bash
git ls-files '*.md' ':(exclude).github/**' > /tmp/attestplane-md-files.txt
printf '%s\n' docs/validation/local_codex_runner/issue-114/03_fix_ci_round_1.prompt.md >> /tmp/attestplane-md-files.txt
/Users/macworkers/.npm/_npx/3c2a9ea6c4b6e0a2/node_modules/.bin/markdownlint-cli2 $(cat /tmp/attestplane-md-files.txt)
```

```text
markdownlint-cli2 v0.22.1 (markdownlint v0.40.0)
Linting: 608 file(s)
Summary: 0 error(s)
```

The raw local CI glob also traversed ignored dependency installs under
`sdk/python/.venv/` and `sdk/typescript/node_modules/`, which are not tracked
repository files. `git check-ignore -v` confirmed both sample dependency
README paths are ignored, and `git ls-files` confirmed zero tracked markdown
files under those dependency directories.
