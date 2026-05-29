---
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
---

# ADR-VERSIONING-001. SemVer policy with PR release-impact labels

- **Date**: 2026-05-30
- **Status**: Proposed
- **Deciders**: @merchloubna70-dot
- **Related**: [release train](../../scripts/release/stable_auto_train.py),
  [ADR-0017](0017-github-actions-release-cd.md)

## Context

Attestplane uses Semantic Versioning 2.0.0 to communicate compatibility risk
for SDK consumers, release automation, and downstream integrators. The release
train already has an existing minor-bump mechanism in
`scripts/release/stable_auto_train.py` via `PATCH_ROLLOVER = 10`, which
advances the stable sequence after patch numbers roll over. This ADR defines
the human-reviewed PR release-impact labels that should match the same
compatibility policy.

## Decision

Classify PR impact using SemVer 2.0.0 as follows:

| Change type | SemVer class | Counts as |
| --- | --- | --- |
| Backward-compatible bug fix, typo fix, internal refactor with no public surface change | Patch | `release:patch` |
| New public API field, method, SDK surface, exit code, or schema field | Minor | `release:minor` |
| Breaking API change, removed field or method, or changed field semantics | Major | `release:major` |
| Docs-only, tests-only, or other non-runtime-change PRs | None | `release:none` |

Use these PR labels exactly:

- `release:major`
- `release:minor`
- `release:patch`
- `release:none`

Labeling rule:

- New public API fields or methods are minor.
- Breaking changes are major.
- Bug fixes are patch.
- Docs/tests only are none.

Examples:

- A new SDK field, a new exit code, or a new schema field is a minor bump.
- A changed field semantic, such as altering meaning, validation, or
  compatibility expectations for an existing field, is a major bump.

## Consequences

Release-impact labels become a lightweight review contract for PRs and release
planning. Maintainers can map labels directly to versioning intent before a
release train advances.

The policy keeps minor vs major decisions explicit for public API growth and
compatibility breaks, while leaving docs and tests out of release-impact
churn.

`PATCH_ROLLOVER = 10` in `scripts/release/stable_auto_train.py` remains the
current release-train mechanism for stable version progression; this ADR
documents the compatibility meaning that PR labels should reflect.

## Alternatives considered

1. **No PR labels at all.** Rejected because release impact would remain
   implicit and harder to review consistently.
2. **Label only major vs non-major.** Rejected because patch and minor changes
   need separate signals for release planning.
3. **Infer impact only from code paths at release time.** Rejected because PR
   review needs an explicit declaration before merge.

## Compliance and audit notes

This ADR is about versioning policy, not a compliance claim. It does not alter
existing audit chains or evidence records. The label set is intended to make
release-impact review explicit and auditable.
