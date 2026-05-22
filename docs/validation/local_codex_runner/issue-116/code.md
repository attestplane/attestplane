# Issue 116 Code Evidence

Plan ID: `30bdd396c08f49ea`

## Source Changes

One test fixture was changed for Issue #116:

- `tests/local_codex_runner/test_git_ops.py`

The fixture now stubs both `git status --porcelain` and
`git status --porcelain --untracked-files=all`, matching the actual
`GitOps.commit_all()` path that removes transient runner prompt/log evidence
before staging a commit.

No workflow, runner bootstrap, CI script, package, release, SDK, verifier,
schema, or gate files were changed for Issue #116.

The remaining changes are evidence files under:

```text
docs/validation/local_codex_runner/issue-116/
```

## Scope Guard

The following files were intentionally not modified:

- `.github/workflows/architecture-audit.yml`
- `.github/workflows/architecture-audit*.yml`
- `.github/workflows/opus-*`
- runner bootstrap scripts
- `scripts/ci/opus_*`
- package metadata
- release gates
- SDK code
- verifier code
- schemas
- release artifacts

## Validation Outcome

The remote validation remains blocked, not green. The required v1.6.2 remote
dry-runs were not dispatched successfully from this local runner because:

- `scripts/ci/opus_runner_selftest.sh` is absent in this checkout.
- `gh auth status` reports an invalid active GitHub token.
- proxy-enabled GitHub API access fails with `proxyconnect tcp:
  dial tcp 127.0.0.1:7897: connect: operation not permitted`.
- proxy-disabled GitHub API access fails with `error connecting to
  api.github.com`.
- `gh workflow run ...` crashes in the installed GitHub CLI while resolving the
  workflow.

The exact command outputs are recorded in `test.md`.

The local gate failure from the runner phase was fixed. The gate now passes:

```text
$ sdk/python/.venv/bin/python -m compileall scripts && sdk/python/.venv/bin/pytest -q
1227 passed in 118.36s (0:01:58)
```
