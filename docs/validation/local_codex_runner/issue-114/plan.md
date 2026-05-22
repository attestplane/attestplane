# Issue 114 Implementation Plan

Plan ID: `fcb4bf04f6b37833`

## Scope

Confirm the `v1.6.2` real-change boundary as a read-only release-integrity
audit. The acceptance target is to verify that the only behavioral commit
between `v1.6.1` and `v1.6.2` is
`f181c6d fix: fetch opus planned issues after creation`, and that
`fa2ee99 chore(release): prepare v1.6.2` is release-prep metadata matching the
published version bump, package manifests, lockfiles, artifact manifest, and
generated release-note/changelog metadata.

This runner phase uses only local repository files, local command output, and
the issue text. The project-level Opus consultation requirement is not executed
in this phase because the runner prompt explicitly forbids external advisory
services.

## Current Local Findings

- Local tags `v1.6.1` and `v1.6.2` are present.
- `git log --oneline v1.6.1..v1.6.2` currently returns exactly two commits:
  `fa2ee99 chore(release): prepare v1.6.2` and
  `f181c6d fix: fetch opus planned issues after creation`.
- `v1.6.2` resolves to annotated tag target
  `fa2ee99f9f893615ff9ae378342e7b882fa61c78`.
- `git show --name-status f181c6d` shows code/test changes limited to
  `scripts/release/plan_to_issues.py` and
  `sdk/python/tests/test_plan_to_issues.py`.
- `git show --name-status fa2ee99` shows release-prep additions/updates:
  `docs/release-notes/v1.6.2.draft.md`,
  `release/artifacts/v1.6.2/*`, Python package version files and lockfile,
  TypeScript package manifests/lockfile, and TypeScript version source.
- `release/artifacts/v1.6.2/artifact-manifest.json` records
  `target_commit` as
  `f181c6d4af6d6b792e53b17c8d5426cb2c9d805f` and explicit non-actions for
  publish/deploy/workflow dispatch during local prep.
- The issue-required command
  `python -m scripts.release.audit_boundary --from v1.6.1 --to v1.6.2`
  currently fails locally because `scripts.release.audit_boundary` is not
  present in this checkout. The audit phase must record that exact blocker and
  use equivalent local git evidence without claiming that command passed.

## Implementation Approach

1. Capture the commit boundary.
   - Run and save `git log --oneline v1.6.1..v1.6.2`.
   - Record the full SHAs and subjects for `f181c6d` and `fa2ee99`.
   - Confirm there are no additional commits in the tag range.
   - Confirm `v1.6.2` points at `fa2ee99` and `v1.6.1` points at its local
     release-prep commit.

2. Classify the real change.
   - Inspect `git show --name-status f181c6d` and the focused diff for
     `scripts/release/plan_to_issues.py` plus
     `sdk/python/tests/test_plan_to_issues.py`.
   - Confirm the functional change is the planned issue post-create refetch.
   - Verify any test changes in the commit cover that same behavior rather than
     adding unrelated product or release behavior.

3. Classify the release-prep commit.
   - Inspect `git show --name-status fa2ee99`.
   - Confirm version bumps align to `1.6.2` in Python metadata, Python package
     source, Python tests, TypeScript package manifests, TypeScript lockfile,
     and TypeScript version source.
   - Confirm generated release metadata is limited to
     `docs/release-notes/v1.6.2.draft.md` and
     `release/artifacts/v1.6.2/*`.
   - Confirm `release/artifacts/v1.6.2/artifact-manifest.json` names
     `f181c6d4af6d6b792e53b17c8d5426cb2c9d805f` as the target commit and does
     not claim publish, deploy, force-push, npm `ca` movement, production
     readiness, compliance certification, certified provenance, or SLSA L3.

4. Produce the required diff summaries.
   - Run `git diff --stat v1.6.1..v1.6.2`.
   - Run
     `git diff v1.6.1..v1.6.2 -- ':!CHANGELOG.md' ':!**/package*.json' ':!**/version*'`
     and summarize the remaining files by category.
   - Also run the same command with `--stat` for a concise note suitable for
     release-integrity evidence.
   - If any unexpected non-release-prep or non-`f181c6d` behavior appears,
     stop closure and record escalation to a new
     `priority-P0 area:release-integrity` task.

5. Handle the absent audit helper without weakening acceptance.
   - Run
     `python -m scripts.release.audit_boundary --from v1.6.1 --to v1.6.2`.
   - Record the exact local failure if the module remains absent.
   - Do not create or modify release tooling in this read-only audit task just
     to manufacture a pass.
   - Use local git outputs as the substitute evidence and mark the helper as an
     unavailable validation command, not as passed.

6. Write local release-integrity evidence.
   - Add a concise release-integrity note in the issue-local evidence files
     containing the SHA list, classification, no-anomaly conclusion if the
     evidence supports it, the required diff summary, and the unavailable
     `audit_boundary` command result.
   - Because this runner phase forbids external tools and uses local files
     only, do not post to GitHub from this phase. If a later authorized phase
     needs the planning-issue comment, reuse the local note content verbatim.

## Files Likely To Change

- `docs/validation/local_codex_runner/issue-114/plan.md` for this planning
  phase.
- `docs/validation/local_codex_runner/issue-114/code.md` in the audit/execution
  phase, containing the release-integrity note body, SHA list, classification,
  and anomaly decision.
- `docs/validation/local_codex_runner/issue-114/test.md` in the validation
  phase, containing command transcripts or summarized command outputs.
- `docs/validation/local_codex_runner/issue-114/gate_report.md` and
  `docs/validation/local_codex_runner/issue-114/gate_report.json` if the local
  runner requires structured gate evidence.

No source files, package manifests, lockfiles, changelog entries, release
notes, release artifact manifests, tags, or release-gate implementation files
are expected to change for this read-only audit.

## Tests And Local Gates

Issue-required validation commands:

```bash
git log --oneline v1.6.1..v1.6.2
git diff --stat v1.6.1..v1.6.2
python -m scripts.release.audit_boundary --from v1.6.1 --to v1.6.2
```

Additional local read-only audit commands:

```bash
git show --no-patch --format='%H%n%s%n%D' v1.6.1
git show --no-patch --format='%H%n%s%n%D' v1.6.2
git show --name-status --oneline f181c6d
git show --name-status --oneline fa2ee99
git diff --stat v1.6.1..v1.6.2 -- ':!CHANGELOG.md' ':!**/package*.json' ':!**/version*'
git diff --name-status v1.6.1..v1.6.2 -- ':!CHANGELOG.md' ':!**/package*.json' ':!**/version*'
git diff v1.6.1..v1.6.2 -- scripts/release/plan_to_issues.py sdk/python/tests/test_plan_to_issues.py
git diff v1.6.1..v1.6.2 -- release/artifacts/v1.6.2 docs/release-notes/v1.6.2.draft.md
```

No full product test suite is required because this task should not edit
runtime code. If any implementation file, release script, package metadata,
release artifact, changelog, or release gate is modified unexpectedly, stop and
rerun the nearest local release gate before closure.

## Risk Classification

P0 release-integrity audit, medium verification risk, low implementation risk.

The task has P0 severity because it validates a shipped stable release
boundary. The planned local work is read-only and should not alter behavior.
The main risk is a false no-anomaly conclusion if release-prep metadata hides a
behavioral change. Mitigate by inspecting both commits separately, comparing
excluded and non-excluded diff summaries, verifying artifact manifest target
commit metadata, and escalating any hidden behavioral change outside
`f181c6d` instead of closing the task.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-114/plan.md` for this planning
  phase.
- `docs/validation/local_codex_runner/issue-114/code.md` for the local
  release-integrity note, SHA list, commit classifications, no-anomaly or
  anomaly decision, and GitHub-posting limitation if external posting remains
  disallowed.
- `docs/validation/local_codex_runner/issue-114/test.md` for exact local
  outputs of the required validation commands and additional read-only git
  checks.
- `docs/validation/local_codex_runner/issue-114/gate_report.md` and
  `docs/validation/local_codex_runner/issue-114/gate_report.json` if the runner
  expects gate-shaped evidence for this planned task.
- `docs/validation/local_codex_runner/issue-114/review.md` if a later local
  review phase runs, confirming that no source or release metadata was changed
  and that any unavailable command was recorded honestly.

## Safety Confirmation

This task will not merge branches, create tags, move tags, publish npm
packages, publish PyPI packages, push to PyPI, push to any remote, post to
GitHub without explicit authorization, or weaken release gates. It will not
lower P0/P1 severity, remove failing tests to manufacture a pass, loosen
release gates, loosen claim-safety policy, or read/log credentials files such
as ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or
`.npmrc`.
