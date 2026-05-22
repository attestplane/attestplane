# Issue 117 Test Evidence

Plan ID: `4df79212ea68aec1`

## Required Validation

Command:

```bash
pytest tests/observability/test_events.py -k "post_create_fetch"
```

Result: PASS

```text
collected 10 items
tests/observability/test_events.py ..........                            [100%]
10 passed in 0.01s
```

Command:

```bash
python -m scripts.release.plan_to_issues --dry-run --emit-events --milestone v1.6.2 | jq 'select(.event=="planned_issue_post_create_fetch")'
```

Result: PASS

```json
{
  "created_count": 0,
  "event": "planned_issue_post_create_fetch",
  "latency_ms": 0,
  "milestone": "v1.6.2",
  "ok": true,
  "refetched_count": 0
}
```

Command:

```bash
markdownlint docs/observability/events.md
```

Result: BLOCKED by local runner tool availability.

```text
zsh:1: command not found: markdownlint
```

## Additional Local Checks

Command:

```bash
python -m compileall scripts/observability scripts/release/plan_to_issues.py
```

Result: PASS

```text
Listing 'scripts/observability'...
```

Command:

```bash
pytest tests/observability/test_events.py -q
```

Result: PASS

```text
..........                                                               [100%]
10 passed in 0.01s
```

Command:

```bash
run_gate attestplane
```

Result: BLOCKED by local gate helper project mapping.

```text
[run_gate] project dir not found: /Users/macworkers/attestplane
```
