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

- No automatic merge.
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

## Known Limitations

- Codex CLI flags may change; `codex_command_template` can override the default
  command shape.
- CI log capture depends on `gh pr checks`; the fallback evidence may contain
  failed check links rather than full logs.
- Claim-safety and P0 repairs still require human review before merge.
- Local Codex and GitHub login state must be maintained by the user.
- Fork PR permissions may require repo-specific adjustments.

