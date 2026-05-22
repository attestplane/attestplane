# Issue 117 Implementation Plan

Plan ID: `4df79212ea68aec1`

## Scope

Emit an additive structured observability event for the post-creation GitHub
issue refetch in `scripts/release/plan_to_issues.py`. The target event is
`planned_issue_post_create_fetch` with required fields:

```json
{
  "event": "planned_issue_post_create_fetch",
  "milestone": "v1.6.2",
  "created_count": 0,
  "refetched_count": 0,
  "latency_ms": 0,
  "ok": true
}
```

This runner phase used only local repository files, local command output, and
the issue text. The project-level Opus consultation requirement is not executed
in this phase because the runner prompt explicitly forbids external advisory
services.

## Current Local Findings

- `scripts/release/plan_to_issues.py` contains the relevant post-creation
  refetch path: `create_issues(...)` calls `create_issue(...)` for each parsed
  task, then calls `fetch_uploaded_issues(...)`, and raises if no uploaded
  planned-task issues are fetched back from GitHub.
- The tracked checkout does not currently contain
  `scripts/observability/events.py`, `tests/observability/test_events.py`, or
  `docs/observability/events.md`. Only `__pycache__` files exist under
  `scripts/observability/` and `tests/observability/`.
- The local `plan_to_issues.py` CLI currently requires `--plan-file` and
  `--source-issue`; it does not currently expose the issue-required
  `--dry-run`, `--emit-events`, or `--milestone` flags.
- No tracked local text references `planned_issue_refetch` or
  `planned_issue_post_create_fetch` outside this issue's runner prompt.
- Because the issue explicitly says this extends #111, implementation must
  first confirm that #111's `planned_issue_refetch` schema scaffolding has
  landed in the working tree. If it remains absent, this task should be marked
  blocked by #111 rather than inventing an incompatible parallel schema.

## Implementation Approach

1. Confirm or restore the #111 observability scaffold.
   - Re-check for `scripts/observability/events.py`,
     `tests/observability/test_events.py`, and
     `docs/observability/events.md` at implementation time.
   - If `planned_issue_refetch` exists, extend only that schema/event registry
     with `planned_issue_post_create_fetch`.
   - If the scaffold is still absent, stop before code changes and record the
     blocker in implementation evidence. Do not lower this P1 task's severity in
     local evidence; only maintainers should apply the rollout note that says it
     may wait on #111 and be reprioritized.

2. Add the new event type using the same emitter/parser path as #111.
   - Add `planned_issue_post_create_fetch` to the existing event type enum,
     required-field map, or parser schema used for `planned_issue_refetch`.
   - Require `milestone`, `created_count`, `refetched_count`, `latency_ms`, and
     `ok`.
   - Keep the event additive so downstream consumers that ignore unknown event
     types continue to work.
   - Avoid introducing a new observability framework or changing unrelated
     event payloads.

3. Instrument the post-creation refetch.
   - Wrap the `fetch_uploaded_issues(...)` call inside `create_issues(...)` with
     latency measurement using the repository's existing pattern if #111 added
     one, otherwise `time.perf_counter()` is the likely local primitive.
   - Emit `created_count` as the number of planned tasks attempted/created in
     that create pass.
   - Emit `refetched_count` as `len(uploaded)` after the post-creation fetch.
   - Emit `ok: true` when the refetch returns at least one matching issue and no
     exception is raised.
   - Emit `ok: false` before re-raising or returning failure if the refetch
     path raises or returns no uploaded issues.
   - Preserve the existing runtime behavior: this observability task should not
     make a failed post-creation refetch pass.

4. Wire the issue-required CLI surface only as far as needed for observability.
   - If #111 added `--emit-events`, reuse that path and ensure the new event is
     emitted when the post-creation refetch runs.
   - If `--dry-run` and `--milestone` are part of the #111 branch, keep changes
     scoped to passing the milestone value into the event payload.
   - Do not change the existing `--plan-file`, `--source-issue`, `--create`, or
     `--json` behavior except where required to propagate event context.

5. Document the new event.
   - Add a `planned_issue_post_create_fetch` section or row beside
     `planned_issue_refetch` in `docs/observability/events.md`.
   - Document required fields, field meanings, types, and that the event is
     additive.
   - State that downstream consumers should ignore unknown event types.

6. Add focused parser/emitter coverage.
   - Add a test named so `pytest tests/observability/test_events.py -k
     "post_create_fetch"` selects it.
   - Assert the parser accepts a complete `planned_issue_post_create_fetch`
     payload and rejects payloads missing each required field.
   - Add a focused release-script test if the existing test suite has a
     `plan_to_issues` harness after #111 lands; otherwise keep the direct parser
     test as the acceptance-required test.

## Files Likely To Change

- `scripts/release/plan_to_issues.py`
- `scripts/observability/events.py` if #111's scaffold has landed, or the
  equivalent tracked event emitter/parser module if it was renamed
- `tests/observability/test_events.py`
- `docs/observability/events.md`
- Possibly a focused release-script test file if #111 added one for
  `plan_to_issues` event emission
- Later evidence files under
  `docs/validation/local_codex_runner/issue-117/`

## Tests And Local Gates

Issue-required validation commands:

```bash
pytest tests/observability/test_events.py -k "post_create_fetch"
python -m scripts.release.plan_to_issues --dry-run --emit-events --milestone v1.6.2 | jq 'select(.event=="planned_issue_post_create_fetch")'
markdownlint docs/observability/events.md
```

Additional targeted checks after implementation:

```bash
python -m compileall scripts
pytest tests/observability/test_events.py -q
pytest tests -q
```

Local gate before closure:

```bash
run_gate attestplane
```

If `run_gate attestplane`, `markdownlint`, or the issue-required
`plan_to_issues` flags are unavailable in the local checkout, record the exact
failure in `docs/validation/local_codex_runner/issue-117/test.md` and run the
closest available local checks without claiming the unavailable command passed.

## Risk Classification

P1, medium implementation risk.

The event itself is additive and low behavioral risk, but the current local
checkout appears to be missing the #111 schema scaffold that this task is
supposed to extend. The main risk is merge churn or a duplicated event schema if
implementation proceeds before #111 lands. The second risk is accidentally
changing `create_issues(...)` failure semantics while adding `ok: false`
observability. Mitigate by extending only the existing #111 event scaffolding,
keeping post-creation refetch failures blocking, and covering the required
fields in parser tests.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-117/plan.md` for this planning
  phase.
- `docs/validation/local_codex_runner/issue-117/code.md` in the implementation
  phase, listing exact source, test, and docs files changed plus whether #111
  was present or blocked this task.
- `docs/validation/local_codex_runner/issue-117/test.md` in the validation
  phase, with exact outputs for the required pytest, `plan_to_issues`/`jq`, and
  markdownlint commands or documented local blockers.
- `docs/validation/local_codex_runner/issue-117/review.md` if a later review
  phase runs, confirming additive behavior, required fields, and release-gate
  preservation.

## Safety Confirmation

This task will not merge branches, create tags, move tags, publish npm
packages, publish PyPI packages, push to PyPI, push to any remote, or weaken
release gates. It will not lower P0/P1 severity, remove failing tests to
manufacture a pass, loosen release gates, loosen claim-safety policy, or
read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI
tokens, private keys, `.pypirc`, or `.npmrc`.
