# Local Codex Auto-Repair Runner Architecture

Attestplane keeps model execution out of GitHub Actions. CI, nightly Sentinel,
claim-safety checks, and release gates discover failures and open issues, but
large-model repair work runs on a local Mac mini through the user's authenticated
Codex CLI. This keeps GitHub Actions deterministic, avoids storing model
credentials in CI, and uses the existing ChatGPT subscription login for low-cost
local repair loops.

## Responsibilities

GitHub owns discovery, issues, labels, PRs, branch protection, CI checks, and the
evidence trail. The local runner owns polling approved issues, planning, coding,
local testing, self-review, committing to an issue branch, opening a PR, watching
CI, retrying bounded failures, and writing issue comments.

The runner never merges `main`, creates tags, publishes packages, or pushes to
PyPI. It creates PRs for human review only.

## Lane Topology

Backlog processing can run as independent lanes. Each lane is a normal
`run_once` loop with its own config, worktree, state file, and tmux session:

- P0 lane: one worker, `priority-P0` / `priority:P0`, for release integrity,
  security, and verifier work.
- P1 lane: one or two workers, `priority-P1` / `priority:P1`, for SDK, CLI, and
  regression-test work.
- P2 docs lane: one worker, `priority-P2` / `priority:P2`, for docs and release
  note work that should not block P0/P1 execution.

Lane filters are advisory queue filters, not locks. Duplicate prevention still
comes from the shared GitHub label state machine: `codex-pr-opened` and
`codex-needs-human` make an issue ineligible, and `codex-in-progress` guards
work that a lane already owns locally. Each lane must use a separate state file
so stale or failed work in one lane does not block another lane.

Every cycle may prune local state for issues that GitHub already reports as
closed. The cleanup removes stale `active_issue_ids` and branch mappings while
leaving processed history intact.

## Label State Machine

Only open issues with `auto-codex-approved` are eligible. `codex-pr-opened` and
`codex-needs-human` prevent duplicate handling. At start the runner adds
`codex-in-progress`. After PR creation it adds `codex-pr-opened` and removes
`codex-in-progress`. If CI passes, it adds `codex-ci-green`. If local or CI
retry limits are exceeded, it adds `codex-needs-human` and removes
`codex-in-progress`.

Dry-run mode records these actions in local evidence without changing GitHub.

## Stages

1. Load config and validate required `repo` and `workdir`.
2. Verify `gh auth status`.
3. Fetch an issue by number or poll approved open issues.
4. Render a plan prompt and run `codex exec` in plan-only mode.
5. Render a code prompt and run `codex exec` for scoped implementation.
6. Run local gates selected from `.local-codex-gates.yml`.
7. On local gate failure, render a bounded fix prompt and retry.
8. Run Codex self-review and the deterministic `review_guard`.
9. Commit, push branch, and create PR when not in dry-run.
10. Watch GitHub checks when enabled.
11. Write final issue comments, labels, and evidence.

## Safety Red Lines

- No automatic merge unless explicitly enabled and all merge gates pass.
- No automatic tag.
- No package publish.
- No PyPI push.
- No severity downgrade.
- No release gate weakening.
- No secret or token logging.
- No default live external tests.
- No default `danger-full-access`.
- No unapproved issue processing.

Claim-safety and P0 issues must include tests or evidence changes. Publish and
release workflow changes require explicit labels.

When multiple lanes are enabled, keep the aggregate automatic merge budget at
2-3 green PRs per cycle. Do not treat a lane's green CI result as permission to
merge around branch protection, stale checks, blocked labels, or release gates.

## Known Limitations

- Codex CLI flags may change; `codex_command_template` can override the default
  command shape.
- CI log capture depends on `gh pr checks`; the fallback evidence may contain
  failed check links rather than full logs.
- Claim-safety and P0 repairs still require human review before merge.
- Local Codex and GitHub login state must be maintained by the user.
- Fork PR permissions may require repo-specific adjustments.
