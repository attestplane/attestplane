# Follow-Up Draft: Clarify Release Boundary Validation Scope

Suggested labels: `area:release-integrity`, `priority-P1`, `planned-task`

## Title

Clarify idle-cadence validation scope for stable release boundary reviews

## Problem

Issue #96 asked whether `v1.5.0..v1.5.10` contained real human work, but
also listed validation commands that inspect
`$(git rev-list --max-parents=0 HEAD)..HEAD`. That root-to-HEAD range is
repository-lifetime scope, not the stable release boundary.

In the local Issue #96 validation run, focused `v1.5.0..v1.5.10`
validation passed:

```text
60 files changed, 3606 insertions(+), 87 deletions(-)
git diff --check v1.5.0..v1.5.10: exit 0
```

The root-to-HEAD `git diff --check` command failed on historical
whitespace and EOF findings outside the focused v1.5.10 boundary.

## Risk

Future release-integrity tasks may confuse repository-lifetime hygiene
with the specific stable-train publish/skip boundary. That can lead to
either:

- false release blocks caused by unrelated historical diff-check noise; or
- broad unrelated cleanup in a P0 release-boundary task to manufacture a
  passing root-to-HEAD result.

Both outcomes weaken the clarity of the release decision.

## Proposed Acceptance Criteria

1. Stable release-boundary review templates name the exact tag range used
   for the publish-versus-skip decision.
2. Root-to-HEAD commands, when still useful, are labeled as repository
   hygiene checks rather than release-boundary checks.
3. The template states that unrelated historical `git diff --check`
   findings should be recorded as residual risk or follow-up work, not
   fixed inside a scoped release-boundary task unless explicitly planned.
4. The cadence limiter documentation links the validation template back
   to the release-prep regex and `commits_since_tag_have_real_work(...)`.

## Local Evidence Source

`docs/validation/local_codex_runner/issue-96/test.md`
