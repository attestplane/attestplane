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
