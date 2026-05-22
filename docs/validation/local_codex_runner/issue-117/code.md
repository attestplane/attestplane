# Issue 117 Code Evidence

Plan ID: `4df79212ea68aec1`

## Scope Implemented

This implementation adds structured local observability for the planned-task
post-creation refetch path in `scripts.release.plan_to_issues`.

Changed files:

- `scripts/observability/__init__.py`
- `scripts/observability/events.py`
- `scripts/release/plan_to_issues.py`
- `tests/observability/test_events.py`
- `docs/observability/events.md`
- `docs/validation/local_codex_runner/issue-117/code.md`
- `docs/validation/local_codex_runner/issue-117/test.md`

## #111 Scaffold Status

The local checkout did not contain tracked #111 scaffold files named in the
issue plan:

- `scripts/observability/events.py`
- `tests/observability/test_events.py`
- `docs/observability/events.md`

Only `__pycache__` directories were present under `scripts/observability/` and
`tests/observability/`. To satisfy this issue's local validation commands
without external services, this implementation creates the smallest compatible
event scaffold and includes both:

- base `planned_issue_refetch` required-field schema
- additive `planned_issue_post_create_fetch` required-field schema

## Behavior

`create_issues(...)` now accepts optional observability arguments:

- `milestone`
- `emit_events`
- `event_stream`

When issue creation completes and the post-create `fetch_uploaded_issues(...)`
call runs, it emits:

```json
{
  "event": "planned_issue_post_create_fetch",
  "milestone": "v1.6.2",
  "created_count": 1,
  "refetched_count": 1,
  "latency_ms": 0,
  "ok": true
}
```

If the post-create fetch raises or returns no matching issues, the event is
emitted with `ok: false` and the existing blocking behavior is preserved.

The CLI also accepts the issue-required additive flags:

- `--dry-run`
- `--emit-events`
- `--milestone`

The dry-run path emits the event shape for local observability validation
without invoking `gh` or requiring network access.

## Release Boundaries

No publish, tag, merge, remote push, release gate weakening, release workflow,
package metadata, artifact manifest, checksum, or claim-safety files were
modified.
