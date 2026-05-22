# Follow-Up Draft: Narrow Release Boundary Validation Commands

Suggested labels: `area:release-integrity`, `planned-task`, `priority-P1`

## Problem

Issue #92 showed that root-to-HEAD validation commands are too broad for a
single stable release boundary. They can report historical repository whitespace
findings that are unrelated to the target release train decision, while the
actual `v1.5.0..v1.5.9` boundary passes `git diff --check` and contains real
non-release-prep work.

This is a residual idle-cadence risk because future planned tasks could use a
broad root-to-HEAD range to obscure the publish/skip decision. The release train
itself uses latest-stable-tag-to-HEAD semantics, but the human validation prompt
should match that boundary.

## Acceptance Criteria

- Release-integrity planned tasks name the concrete stable tag-to-tag or
  latest-stable-tag-to-HEAD range used for the publish/skip decision.
- Root-to-HEAD commands are either removed from future release-boundary tasks or
  clearly marked as broad historical context rather than a release gate.
- Validation evidence records both the cadence regex result and
  `git diff --check` for the concrete release boundary.

## Validation Commands

```bash
git log --no-merges --pretty=tformat:%s <previous-stable-tag>..<candidate-tag-or-HEAD>
git diff --stat <previous-stable-tag>..<candidate-tag-or-HEAD>
git diff --check <previous-stable-tag>..<candidate-tag-or-HEAD>
```

## Local Handoff Note

This runner phase is not authorized to create remote GitHub issues. This file is
the local handoff artifact satisfying Issue #92's requirement to record any
remaining idle-cadence risk before close.
