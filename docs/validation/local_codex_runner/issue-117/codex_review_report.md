# Codex Review Report: Issue #117

Status: **WARN**

## Findings

No blocking findings.

Non-blocking warning: `scripts/release/plan_to_issues.py` emits
`planned_issue_post_create_fetch` with `ok: true` whenever the post-create
refetch returns at least one issue. If `created_count` is greater than
`refetched_count` but `refetched_count` is non-zero, the mismatch is visible in
the counts but not reflected in `ok`. This preserves the existing
non-blocking partial-refetch behavior, so it is not a hard red-line failure for
Issue #117.

## Checklist

- Review used only local repository files, local command output, and the
  provided issue text: yes.
- Diff weakened any release gate: no. The empty-refetch path still raises
  `RuntimeError` after emitting the event when enabled.
- Lowered severity: no.
- Leaked or logged secrets: no.
- Modified publish/tag logic: no.
- Deleted key tests: no.
- Implemented behavior without tests or evidence: no. New observability tests
  cover parser validation, event emission, successful post-create refetch
  emission, and empty-refetch failure emission.
- Introduced uncertain external dependencies: no.
- Avoided merge, tag, package publish, and PyPI push: yes.

## Local Validation

- `sdk/python/.venv/bin/pytest tests/observability/test_events.py -q`: PASS,
  `10 passed in 0.09s`.
- `sdk/python/.venv/bin/python -m compileall scripts/observability scripts/release/plan_to_issues.py`:
  PASS.
- `sdk/python/.venv/bin/python -m scripts.release.plan_to_issues --dry-run --emit-events --milestone v1.6.2`:
  PASS, emitted:

```json
{"created_count": 0, "event": "planned_issue_post_create_fetch", "latency_ms": 0, "milestone": "v1.6.2", "ok": true, "refetched_count": 0}
```

## Residual Risks

- The narrow validation did not run the full release gate or exercise live
  GitHub CLI issue creation/refetch.
- Partial post-create refetch cardinality is not explicitly tested; counts
  expose the condition, but `ok` remains true for any non-empty refetch.
- The dry-run evidence command emits the event shape without a plan file and
  without exercising `parse_plan`.

## Red-Line Result

No merge, tag, package publish, or PyPI push was performed.
