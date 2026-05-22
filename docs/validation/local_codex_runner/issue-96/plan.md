# Issue 96 Implementation Plan

Plan ID: `9c2ebb04228d4d8e`

## Scope

Confirm whether the `v1.5.0..v1.5.10` stable-train range contains real
non-release-prep work, decide whether the release train should publish instead
of skipping the cadence cycle, and record any remaining idle-cadence risk as a
follow-up before closing the task.

This runner phase used only local repository files, local command output, and
the issue text. The project-level Opus consultation requirement is not executed
in this phase because the runner prompt explicitly forbids external advisory
services.

## Current Local Findings

- Local tags `v1.5.0` through `v1.5.10` exist.
- The focused range `v1.5.0..v1.5.10` contains multiple non-release-prep
  subjects, including `test: cover opus planning levels`,
  `fix: consult opus for stable planning`,
  `fix: make stable train git proxy strategy explicit`,
  `ci: ignore transient scorecard link failures`,
  `fix: reload planned issues from github`,
  `fix: include open issues in release planning`,
  `fix: fan out daily architecture plans`,
  `fix: generate daily architecture audit plans`,
  `fix: make release planning scripts importable in CI`,
  `fix: satisfy markdownlint and plan parser test`,
  `Add structured autodev train events`,
  `Unify release planning schema and fanout`,
  `Unify plan issuance across release tiers`,
  `ci: auto-accept major architecture plans`,
  `ci: convert accepted plans into task issues`, and
  `fix(release): skip idle cadence before remote probe`.
- `git diff --stat v1.5.0..v1.5.10` shows a real code, workflow, runbook,
  release-note, artifact, and test delta: 60 files changed, 3606 insertions,
  and 87 deletions.
- `git diff --check v1.5.0..v1.5.10` exits cleanly.
- The issue-required root-to-HEAD `git diff --check $(git rev-list
  --max-parents=0 HEAD)..HEAD` currently reports historical whitespace and EOF
  findings outside the `v1.5.0..v1.5.10` decision boundary. The implementation
  phase should record this exactly and must not remove or hide unrelated
  historical failures to manufacture a pass.
- `docs/runbooks/autodev-train.md` documents the stable train cadence limiter:
  it skips only when every non-merge subject since the previous stable tag
  matches `^chore\(release\): prepare v\d+\.\d+\.\d+(-\S+)?$`, or when the
  range is empty.
- `scripts/release/stable_auto_train.py` implements that same policy in
  `commits_since_tag_have_real_work(...)` and emits
  `cadence_skipped` only when no real work is present.
- `docs/release-notes/v1.5.10.draft.md` already lists the visible v1.5.10
  change as `test: cover opus planning levels` and preserves claim boundaries.

## Implementation Approach

1. Capture the real-change boundary evidence.
   - Create `docs/validation/local_codex_runner/issue-96/code.md` with the
     local evidence used to classify `v1.5.0..v1.5.10`.
   - Include the exact focused tag-range commands and summarize their results:
     commit subjects, diff stat, and clean focused `git diff --check`.
   - Identify which subjects are release-prep noise and which subjects count
     as real work under the runbook and implementation regex.

2. Confirm publish-versus-skip decision.
   - State that the train should publish rather than skip for `v1.5.10`
     because the tag range includes non-release-prep work.
   - Tie the decision to the local runbook and
     `commits_since_tag_have_real_work(...)` behavior.
   - Do not alter `scripts/release/stable_auto_train.py`,
     `.github/workflows/release-cd.yml`, or release gates unless the
     implementation phase uncovers a direct contradiction between docs and
     code. No contradiction is currently visible.

3. Record residual idle-cadence risk.
   - Add a local follow-up draft under
     `docs/validation/local_codex_runner/issue-96/followup_idle_cadence.md`.
   - The follow-up should be issue-ready text, but this local runner phase must
     not call GitHub, push, or create the remote issue.
   - The residual risk should focus on the historical root-to-HEAD
     `git diff --check` noise and any ambiguity between validating
     root-to-HEAD versus the actual release boundary `v1.5.0..v1.5.10`.

4. Update validation evidence.
   - Create `docs/validation/local_codex_runner/issue-96/test.md` with exact
     command outputs or concise excerpts for the issue-required commands and
     the focused tag-range commands.
   - Record that the root-to-HEAD `git diff --check` has pre-existing
     historical findings if it still fails, without editing unrelated files.
   - Record that the focused `v1.5.0..v1.5.10` check passes.

5. Keep release surfaces immutable for this task.
   - Do not move tags, create tags, merge, publish, dispatch `release-cd`, or
     mutate registry state.
   - Do not edit package versions, artifact manifests, checksums, release CD
     policy, or release gates.
   - Do not edit `docs/release-notes/v1.5.10.draft.md` unless the
     implementation phase finds the existing release-note statement is false.

## Files Likely To Change

- `docs/validation/local_codex_runner/issue-96/plan.md` for this planning
  phase.
- `docs/validation/local_codex_runner/issue-96/code.md` in the implementation
  phase, recording the real-change boundary and publish-versus-skip decision.
- `docs/validation/local_codex_runner/issue-96/test.md` in the validation
  phase, recording exact local command outputs and any known pre-existing
  root-to-HEAD diff-check findings.
- `docs/validation/local_codex_runner/issue-96/followup_idle_cadence.md` with
  the local follow-up issue draft required before closure.
- `docs/validation/local_codex_runner/issue-96/review.md` only if a later local
  review phase is run.

Files that should normally remain unchanged:

- `scripts/release/stable_auto_train.py`
- `.github/workflows/release-cd.yml`
- `docs/runbooks/autodev-train.md`
- `docs/runbooks/github-cd-release.md`
- `docs/release-notes/v1.5.10.draft.md`
- `sdk/python/pyproject.toml`
- `sdk/typescript/package.json`
- `release/artifacts/v1.5.10/artifact-manifest.json`
- `release/artifacts/v1.5.10/checksums.sha256`

## Tests And Local Gates

Issue-required validation commands:

```bash
git log --no-merges --pretty=tformat:%s $(git rev-list --max-parents=0 HEAD)..HEAD
git diff --stat $(git rev-list --max-parents=0 HEAD)..HEAD
git diff --check $(git rev-list --max-parents=0 HEAD)..HEAD
```

Focused release-boundary checks:

```bash
git log --no-merges --pretty=tformat:%s v1.5.0..v1.5.10
git diff --stat v1.5.0..v1.5.10
git diff --check v1.5.0..v1.5.10
```

Policy and implementation cross-checks:

```bash
rg -n "real work|idle cadence|stable: no real work|FORCE_CADENCE|release-prep" \
  docs/runbooks/autodev-train.md scripts/release/stable_auto_train.py
rg -n "v1\\.5\\.10|cover opus planning levels" docs/release-notes/v1.5.10.draft.md
```

No full product gate is required for evidence-only documentation. If the
implementation phase touches release automation, release CD policy, package
versions, artifact manifests, checksums, SDK code, or tests, stop and run the
nearest local release gate before closure rather than weakening any gate.

## Risk Classification

P0 release-integrity task, low implementation risk.

The intended change is evidence-only and should not alter runtime code,
release automation, package metadata, or registry state. The main risk is
boundary confusion: the issue title asks for `v1.5.0..v1.5.10`, while the
listed validation commands inspect root-to-HEAD and currently surface
unrelated historical `git diff --check` findings. The mitigation is to record
both command families separately, preserve the issue-required command results,
and base the publish-versus-skip decision on the actual release boundary.

There is a secondary release-governance risk if a later phase tries to "fix"
the historical root-to-HEAD findings by editing unrelated old files. That
should not happen in this task. Any remaining idle-cadence or validation-scope
risk should be recorded as a follow-up draft, not hidden by broad cleanup.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-96/plan.md` for this planning
  phase.
- `docs/validation/local_codex_runner/issue-96/code.md` with release-boundary
  classification, publish-versus-skip conclusion, and local references to the
  cadence limiter docs/code.
- `docs/validation/local_codex_runner/issue-96/test.md` with exact local
  validation outputs, including the distinction between root-to-HEAD and
  `v1.5.0..v1.5.10`.
- `docs/validation/local_codex_runner/issue-96/followup_idle_cadence.md` with
  the follow-up issue draft required by acceptance criterion 3.
- `docs/validation/local_codex_runner/issue-96/review.md` if a later review
  phase is run.

## Safety Confirmation

This task will not merge branches, create tags, move tags, publish npm
packages, publish PyPI packages, push to PyPI, push to any remote, dispatch
GitHub `release-cd`, or weaken release gates. It will not lower P0/P1
severity, remove failing tests to manufacture a pass, loosen release gates,
loosen claim-safety policy, or read/log credentials files such as ChatGPT
cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
