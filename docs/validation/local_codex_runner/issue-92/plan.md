# Issue 92 Implementation Plan

Plan ID: `1c6c43895e7a304f`

## Scope

Confirm whether the `v1.5.0` to `v1.5.9` stable-release range contains real
non-release-prep work, and record whether the stable release train should publish
instead of skipping the cadence cycle.

This runner phase uses only local repository files, local command output, and the
issue text. The project-level Opus consultation requirement is not executed in this
phase because the runner prompt explicitly forbids external advisory services.

## Current Local Findings

- Local tags `v1.5.0` through `v1.5.9` exist.
- The local tag-to-tag probe `git log --no-merges --pretty=tformat:'%h %s'
  v1.5.0..v1.5.9` shows multiple non-release-prep commits, including:
  - `fix: consult opus for stable planning`
  - `fix: make stable train git proxy strategy explicit`
  - `ci: ignore transient scorecard link failures`
  - `fix: reload planned issues from github`
  - `fix: include open issues in release planning`
  - `fix: fan out daily architecture plans`
  - `fix: generate daily architecture audit plans`
  - `Add structured autodev train events`
  - `Unify release planning schema and fanout`
- `git diff --stat v1.5.0..v1.5.9` shows real repository changes in release
  planning automation, stable train logic, SDK package versions, and tests, not only
  generated release artifact files.
- `git diff --check v1.5.0..v1.5.9` produced no output locally.
- `docs/runbooks/autodev-train.md` documents the cadence limiter: skip when all
  commits since the latest stable tag match `chore(release): prepare vX.Y.Z`, and
  proceed when at least one non-release-prep subject exists.
- `docs/release-notes/v1.5.9.draft.md` currently records
  `fix: consult opus for stable planning` as the v1.5.9 change.

## Implementation Approach

1. Record the exact local evidence.
   - Create a local evidence report for Issue #92 under
     `docs/validation/local_codex_runner/issue-92/`.
   - Include the exact commands, exit status, and relevant output needed to prove the
     `v1.5.0..v1.5.9` range contains real non-release-prep work.
   - Keep the output focused on commit subjects, diff summary, and whitespace check
     results. Do not print or inspect credentials or external account state.

2. Classify the boundary against the cadence limiter.
   - Apply the release-prep subject regex documented in `docs/runbooks/autodev-train.md`
     and implemented in `scripts/release/stable_auto_train.py`.
   - List non-release-prep commits separately from `chore(release): prepare ...`
     commits.
   - State that the release train should publish rather than skip if the evidence still
     shows at least one non-release-prep commit in the relevant range.

3. Reconcile the issue validation range.
   - Run the issue-provided root-to-HEAD commands exactly and record them as requested.
   - Also run the more precise tag-to-tag commands for `v1.5.0..v1.5.9`, because the
     acceptance criteria specifically names the release boundary from `v1.5.0` to
     `v1.5.9`.
   - If the two ranges support different conclusions, treat the tag-to-tag boundary as
     the release decision evidence and document the discrepancy.

4. Record idle-cadence follow-up risk.
   - If any residual risk remains, draft a local follow-up issue note under
     `docs/validation/local_codex_runner/issue-92/` with a title, labels, problem
     statement, acceptance criteria, and validation commands.
   - Because this local runner phase is not allowed to use GitHub or external tools,
     do not create or close remote GitHub issues from this task. The local follow-up
     draft is the handoff artifact for the issue closer or a later authorized runner.
   - If no residual risk remains, record that conclusion explicitly in the evidence
     and review notes instead of inventing a follow-up.

5. Keep release artifacts immutable unless a later phase explicitly requires docs text.
   - Prefer storing the confirmation in validation evidence.
   - Do not modify prepared artifact manifests, checksums, upload plans, package
     versions, release workflows, or release gates.
   - Only consider a small update to `docs/release-notes/v1.5.9.draft.md` if the next
     phase determines the release-note itself must carry the real-change confirmation.

## Files Likely To Change

- `docs/validation/local_codex_runner/issue-92/plan.md` for this planning phase.
- `docs/validation/local_codex_runner/issue-92/code.md` in the implementation phase,
  summarizing evidence files created and any release-note decision.
- `docs/validation/local_codex_runner/issue-92/test.md` in the validation phase,
  containing command output and exit statuses.
- `docs/validation/local_codex_runner/issue-92/review.md` in the review phase,
  confirming acceptance criteria and safety boundaries.
- `docs/validation/local_codex_runner/issue-92/v1.5.9-real-change-boundary.md` as the
  main local evidence report.
- `docs/validation/local_codex_runner/issue-92/idle-cadence-follow-up.md` only if a
  remaining idle-cadence risk must be handed off before close.
- `docs/release-notes/v1.5.9.draft.md` only if validation evidence alone is judged
  insufficient for the release-note boundary record.

Files not expected to change:

- `release/artifacts/v1.5.9/artifact-manifest.json`
- `release/artifacts/v1.5.9/checksums.sha256`
- `release/artifacts/v1.5.9/upload-plan.md`
- `.github/workflows/release-cd.yml`
- package version files under `sdk/python/` or `sdk/typescript/`
- release gate scripts

## Tests And Local Gates

Issue-required commands:

```bash
git log --no-merges --pretty=tformat:%s $(git rev-list --max-parents=0 HEAD)..HEAD
git diff --stat $(git rev-list --max-parents=0 HEAD)..HEAD
git diff --check $(git rev-list --max-parents=0 HEAD)..HEAD
```

Boundary-specific commands:

```bash
git tag --list 'v1.5.*' | sort -V
git log --no-merges --pretty=tformat:'%h %s' v1.5.0..v1.5.9
git log --no-merges --pretty=tformat:%s v1.5.0..v1.5.9
git diff --stat v1.5.0..v1.5.9
git diff --check v1.5.0..v1.5.9
```

Cadence-classification check:

```bash
python scripts/dev/real_commit_stats.py v1.5.0..v1.5.9
```

Targeted release-train checks if implementation touches release automation or release
notes:

```bash
python -m pytest sdk/python/tests/test_stable_auto_train_queue.py sdk/python/tests/test_architecture_audit_trigger.py
python -m pytest sdk/python/tests/test_plan_schema.py sdk/python/tests/test_plan_to_issues.py
```

No full package publication gate is required for validation-evidence-only changes. If a
future phase changes release-train code, release workflows, package versions, artifact
manifests, or checksums, run the nearest local release gate before review and record the
result.

## Risk Classification

P0 release-integrity task, medium process risk and low code risk.

The likely implementation is evidence-only, so runtime risk is low. The process risk is
medium because the conclusion affects whether a suffix-free stable release should publish
or skip, and because a false positive could turn idle cadence into registry movement. The
mitigation is to use tag-to-tag local git evidence, keep release artifacts immutable, and
avoid any publish, tag, merge, push, or gate-weakening operation.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-92/plan.md`
- `docs/validation/local_codex_runner/issue-92/v1.5.9-real-change-boundary.md`
- `docs/validation/local_codex_runner/issue-92/code.md`
- `docs/validation/local_codex_runner/issue-92/test.md`
- `docs/validation/local_codex_runner/issue-92/review.md`
- `docs/validation/local_codex_runner/issue-92/idle-cadence-follow-up.md`, only if
  remaining idle-cadence risk exists.

## Safety Confirmation

This task will not merge branches, create tags, move tags, publish npm packages,
publish PyPI packages, push to PyPI, push to any remote, or weaken release gates. It will
not lower P0/P1 severity, remove failing tests to manufacture a pass, loosen release
gates, loosen claim-safety policy, or read/log credentials files such as ChatGPT
cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
