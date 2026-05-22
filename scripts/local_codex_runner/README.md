# Local Codex Auto-Repair Runner

This directory contains the local-only Attestplane auto-repair runner. GitHub CI
and Sentinel jobs discover failures and open issues; this runner polls approved
issues from a local Mac mini and uses the local Codex CLI to produce a branch and
PR for human review.

The runner defaults to `dry_run: true`. In dry-run mode it reads eligible issues,
renders prompts, writes evidence, and records planned actions, but does not write
GitHub labels, commit, push, open PRs, merge, tag, publish packages, or push PyPI.
When dry-run is explicitly disabled, local commits are created with DCO sign-off
and only on issue branches, never on `main`.

## Setup

```bash
cp .local-codex-runner.example.yml .local-codex-runner.yml
cp .local-codex-gates.example.yml .local-codex-gates.yml
```

Edit `repo` and `workdir`. Do not add tokens, cookies, ChatGPT login data, or
private keys to either file. Authentication is provided by local `gh auth login`
and the user's existing Codex CLI login.

## Manual Dry Run

```bash
python -m scripts.local_codex_runner.run_issue \
  --config .local-codex-runner.yml \
  --issue-number 123 \
  --dry-run
```

## One Poll Cycle

```bash
python -m scripts.local_codex_runner.run_once --config .local-codex-runner.yml
```

Only open issues with `auto-codex-approved` are eligible. Issues with
`codex-pr-opened` or `codex-needs-human` are skipped by default.

## Label State Machine

- Eligible: open issue with `auto-codex-approved`.
- Start: add `codex-in-progress`.
- PR opened: add `codex-pr-opened`, remove `codex-in-progress`.
- CI pass: add `codex-ci-green`.
- Failure after retries: add `codex-needs-human`, remove `codex-in-progress`.
- Dry-run: print and record planned label actions without changing GitHub.

If an issue has `codex-in-progress` but local state does not map it to the
current run, the runner treats it as unsafe to duplicate work and skips or marks
it for human recovery depending on the orchestrator path.

## Queue Advance

The queue advance command handles two states that otherwise leave the stable
train correctly idle:

- open Codex PRs that are green but not merged;
- planned-task issues blocked on explicit dependencies.

It is safe-by-default. PRs are never merged unless `allow_auto_merge: true`,
`allowed_pr_authors` is non-empty, the PR has `auto-merge-ready`, checks are
green, the merge state is clean, the base branch matches, and no blocking label
is present. Planned-task issues are never approved unless
`allow_dependency_unlock: true` and their `Depends on: #N` dependencies are
closed. For existing plan-to-issues output, the dependency unlocker also maps
same-plan prose such as `Issue 1`, `Issues 1-3`, and `extends #115` to concrete
issue numbers in dry-run output before taking any write action.

```bash
python -m scripts.local_codex_runner.advance_queue \
  --config .local-codex-runner.yml \
  --mode all
```

Set `auto_advance_before_consume: true` to run queue advance before each
`run_once` poll. Keep `allow_auto_merge: false` until branch protection,
required checks, and reviewer policy have been verified in dry-run output.

## Safety Boundaries

- No automatic merge without `allow_auto_merge`, an author whitelist, clean
  merge state, green checks, and `auto-merge-ready`.
- No tag creation or tag movement.
- No package publish.
- No PyPI push.
- No default live external tests.
- No default `danger-full-access` sandbox.
- No processing without `auto-codex-approved`.
- No severity downgrade.
- No release gate weakening.
- No secret, token, cookie, private key, `.pypirc`, `.npmrc`, or credential
  logging.

## launchd

A template lives at:

```text
scripts/local_codex_runner/launchd/com.attestplane.local-codex-runner.plist.example
```

Install manually after editing paths:

```bash
cp scripts/local_codex_runner/launchd/com.attestplane.local-codex-runner.plist.example \
  ~/Library/LaunchAgents/com.attestplane.local-codex-runner.plist
launchctl load ~/Library/LaunchAgents/com.attestplane.local-codex-runner.plist
launchctl unload ~/Library/LaunchAgents/com.attestplane.local-codex-runner.plist
```
