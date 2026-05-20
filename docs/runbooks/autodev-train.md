# autodev-train Runbook

`autodev-train` is Attestplane's automation programming train: the local loop
that plans scoped work, prepares candidates, runs validation gates, diagnoses
local failures, applies safe fixes when authorized, and hands release
publication to GitHub CD.

The old name `attestplane-alpha-train` referred to the same automation during
the alpha release window. It remains a compatibility alias, but new automation
instructions and tmux sessions should use `autodev-train`.

## Scope

`autodev-train` owns local automation around:

- advisory planning and release-candidate preparation;
- focused code/doc/test edits when a local scoped failure appears;
- deterministic validation before publish;
- restartable long-running supervision; and
- handoff to GitHub Actions CD for actual package publication.

It does not own:

- force-pushes;
- merging pull requests;
- printing secrets;
- pushing release tags;
- dispatching `release-cd`;
- editing GitHub Actions workflows without human review;
- direct local `npm publish` or `twine upload`;
- moving registry dist-tags outside the documented release workflow; or
- making GA, production, legal-compliance, or certification claims.

## Entrypoint

Start a new local train session with:

```bash
scripts/release/start_autodev_train.sh
```

The wrapper starts tmux session `autodev-train` by default and writes logs under
`release/alpha-train/reports/`. The existing
`scripts/release/start_alpha_train_full_auto.sh` wrapper is kept for backwards
compatibility and delegates to `start_autodev_train.sh`.

## Stop File

The train refuses to start while this file exists:

```text
release/alpha-train/STOP
```

Removing that file is an explicit operator action. The train should not remove
it implicitly.

## GitHub CD Handoff

Package publication is handled by the `release-cd` workflow:

```text
.github/workflows/release-cd.yml
```

`autodev-train` may prepare and validate the release state, but PyPI/npm
publication must go through `release-cd`. See
[`github-cd-release.md`](github-cd-release.md) for the publication runbook.

## Permission Audit

Before using `autodev-train` for an RC or GA preparation window, inspect the
automation scripts and logs for forbidden release mutations:

```bash
rg -n "git push.*--tags|git push origin main|gh workflow run release-cd|npm publish|twine upload|dist-tag" \
  scripts/release release/alpha-train
```

Expected posture:

- no automatic release-tag push;
- no automatic `release-cd` dispatch;
- no direct local registry publication;
- no direct registry dist-tag mutation; and
- no implicit removal of `release/alpha-train/STOP`.

Findings from this audit should be recorded in release validation evidence
before dispatching a real RC or GA publication.

The 2026-05-20 audit is recorded in
[`autodev_train_permission_audit_20260520.md`](../validation/autodev_train_permission_audit_20260520.md).

## Compatibility Names

| Name | Status | Meaning |
|---|---|---|
| `autodev-train` | Canonical | Generic automation programming train name. |
| `attestplane-alpha-train` | Compatibility alias | Historical Attestplane alpha-stage session name. |
| `release-cd` | GitHub Actions CD | Registry publication workflow called after train validation. |
