<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Observability Events

Release automation emits newline-delimited JSON events when `--emit-events` is
enabled. Events are additive: downstream consumers should ignore event types
they do not recognize.

## `planned_issue_refetch`

Emitted for the planned-task refetch point introduced by the base refetch
observability scaffold.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `planned_issue_refetch`. |
| `milestone` | string | Release milestone associated with the run. |
| `requested_count` | integer | Number of planned-task issues requested for refetch. |
| `refetched_count` | integer | Number of planned-task issues returned by the refetch. |
| `latency_ms` | integer | Refetch latency in milliseconds. |
| `ok` | boolean | Whether the refetch completed successfully. |

## `planned_issue_post_create_fetch`

Emitted when `scripts.release.plan_to_issues` performs the post-creation GitHub
issue refetch after creating planned-task issues.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `planned_issue_post_create_fetch`. |
| `milestone` | string | Release milestone associated with the run. |
| `created_count` | integer | Number of planned-task issues attempted in the create pass. |
| `refetched_count` | integer | Number of planned-task issues returned by the post-create refetch. |
| `latency_ms` | integer | Post-create refetch latency in milliseconds. |
| `ok` | boolean | `true` when the post-create refetch succeeds; `false` when it fails or returns no matching issues. |

## `publication_status`

Emitted when `scripts.release.stable_auto_train` probes whether a stable tag is
already visible across package registries and GitHub Releases.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `publication_status`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `tag` | string | Stable tag being probed. |
| `python_visible` | boolean | Whether the Python package version is visible. |
| `npm_visible` | boolean | Whether the npm package version is visible. |
| `npm_latest` | boolean | Whether the npm `latest` dist-tag points at the stable version. |
| `github_release` | boolean | Whether the GitHub Release exists for the tag. |
| `complete` | boolean | Whether all required publication surfaces are complete. |

## `push_ci_wait_start`

Emitted when the stable train starts waiting for post-push CI workflows for the
current HEAD commit.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `push_ci_wait_start`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `head_sha` | string | Commit SHA whose push CI workflows are being tracked. |

## `push_ci_probe_retry`

Emitted when the stable train cannot probe push CI state and retries the GitHub
Actions query.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `push_ci_probe_retry`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `head_sha` | string | Commit SHA whose push CI workflows are being tracked. |
| `error` | string | Probe error that triggered the retry. |

## `push_ci_failed`

Emitted when one or more required push CI workflows fail for the current HEAD
commit.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `push_ci_failed`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `head_sha` | string | Commit SHA whose push CI workflows failed. |
| `details` | string | Human-readable workflow failure summary. |

## `push_ci_passed`

Emitted when all required push CI workflows pass for the current HEAD commit.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `push_ci_passed`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `head_sha` | string | Commit SHA whose push CI workflows passed. |

## `push_ci_waiting`

Emitted when the stable train is still waiting on required push CI workflows.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `push_ci_waiting`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `head_sha` | string | Commit SHA whose push CI workflows are still pending. |
| `summary` | string | Current missing and pending workflow summary. |

## `release_cd_wait_start`

Emitted when the stable train starts waiting for the delegated `release-cd`
workflow for a stable tag.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `release_cd_wait_start`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `target_tag` | string | Stable tag whose `release-cd` workflow is being tracked. |

## `release_cd_failed_but_complete`

Emitted when `release-cd` reports failure but the registries and GitHub Release
already show a complete publication state.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `release_cd_failed_but_complete`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `target_tag` | string | Stable tag whose delegated release completed despite workflow failure. |

## `cadence_skipped`

Emitted when the stable train skips a cadence cycle because no release-worthy
work has landed since the previous stable tag.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `cadence_skipped`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `previous_tag` | string | Most recent stable tag before the skipped target. |
| `target_tag` | string | Candidate stable tag that was skipped. |
| `force_cadence` | boolean | Whether the skip decision considered cadence forcing enabled. |
| `reason` | string | Machine-readable skip reason. |

## `product_delta_skipped`

Emitted when the stable train skips a target because only support or ignored
files changed since the previous stable tag.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `product_delta_skipped`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `previous_tag` | string | Most recent stable tag before the skipped target. |
| `target_tag` | string | Candidate stable tag that was skipped. |
| `reason` | string | Machine-readable delta classification reason. |
| `product_files` | list | Product implementation files counted toward the release decision. |
| `product_support_files` | list | Product-adjacent support files counted toward the release decision. |
| `support_only_files` | list | Support-only files that changed without product implementation delta. |
| `ignored_files` | list | Ignored files excluded from the release decision. |

## `cycle_prepare`

Emitted when the stable train begins preparing a new stable cycle from the
previous stable tag.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `cycle_prepare`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `previous_tag` | string | Most recent stable tag before the target cycle. |
| `target_tag` | string | Stable tag being prepared. |
| `channel` | string | Release channel chosen for the target. |
| `publish` | boolean | Whether the cycle intends to publish after local preparation. |
| `wait` | boolean | Whether the cycle will wait for delegated workflows to finish. |
| `dry_run` | boolean | Whether the cycle is only simulating the preparation steps. |

## `cycle_prepared_local`

Emitted when the stable train finishes local cycle preparation but skips
publishing.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `cycle_prepared_local`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `target_tag` | string | Stable tag prepared locally. |
| `publish` | boolean | Whether publication remained enabled for the cycle. |

## `cycle_failed`

Emitted when a continuous stable-train cycle fails and the runner will sleep
before retrying.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `cycle_failed`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `error` | string | Failure message captured for the cycle. |
| `poll_seconds` | integer | Sleep interval before the next retry. |

## `cycle_finished`

Emitted when a continuous stable-train cycle completes successfully and the
runner will sleep before the next poll.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `event` | string | Always `cycle_finished`. |
| `ts` | string | UTC timestamp for the event emission. |
| `train` | string | Always `autodev-train`. |
| `result` | string | Stable tag completed by the cycle. |
| `poll_seconds` | integer | Sleep interval before the next poll. |
