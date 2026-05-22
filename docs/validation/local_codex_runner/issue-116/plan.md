# Issue 116 Implementation Plan

Plan ID: `30bdd396c08f49ea`

## Scope

Validate the v1.6.2 Opus runner network and interpreter changes end-to-end
without editing workflow or runner code. The required validation is one green
architecture-audit dry-run with the proxy-enabled runner environment and one
green dry-run with the proxy disabled, proving the explicit strategy from
`8415001` while exercising:

- `28127b7 ci: proxy architecture audit runner network`
- `b000b56 ci: use local python on opus runner`
- `0cf4660 ci: run architecture planning on opus runner`

This runner phase used only local repository files, local command output, and
the issue text. The project-level Opus consultation requirement is not executed
in this phase because the runner prompt explicitly forbids external advisory
services.

## Current Local Findings

- `.github/workflows/architecture-audit.yml` is present and runs on
  `[self-hosted, macOS, ARM64, opus-plan]`.
- The workflow currently sets `ARCHITECTURE_AUDIT_PYTHON=python3.11` and proxy
  variables `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY` at workflow
  scope.
- The workflow has a "Use local Python on Opus runner" step that prepends
  `/opt/homebrew/bin` to `GITHUB_PATH` and runs
  `"$ARCHITECTURE_AUDIT_PYTHON" --version`, but it does not currently print
  `which python` in the local workflow file.
- The local workflow dispatch input is named `milestone_tag`; the issue-required
  command uses `-f milestone=v1.6.2`. The execution phase must verify the active
  remote workflow input before dispatching and record any mismatch without
  changing workflow files in this task.
- No local `.github/workflows/opus-*` files are present in this checkout.
- No local `scripts/ci/opus_runner_selftest.sh` file is present in this
  checkout; the implementation phase must record this as a local blocker if it
  remains absent rather than inventing a replacement script inside this task.

## Implementation Approach

1. Confirm the checkout and workflow surface.
   - Record the current commit, branch, and `git status --short`.
   - Re-check that no workflow edits are needed or permitted for this issue.
   - Inspect `.github/workflows/architecture-audit.yml` and record the runner
     labels, `ARCHITECTURE_AUDIT_PYTHON`, proxy env keys, and dispatch input
     name in the evidence.

2. Run the local runner selftest if available.
   - Execute `bash scripts/ci/opus_runner_selftest.sh` exactly if the file
     exists in the execution checkout.
   - Preserve the output needed for acceptance: `which python`,
     `python --version`, the configured audit Python command, and proxy env
     state.
   - If the script is still absent, record the exact `No such file or
     directory` failure in evidence and do not create a new script under this
     verification-only task.

3. Dispatch the proxy-enabled architecture audit dry-run.
   - Use the issue-required command as the starting point:
     `gh workflow run architecture-audit.yml -f milestone=v1.6.2 --ref main`.
   - If GitHub rejects the input because the active workflow expects
     `milestone_tag`, retry with the active workflow input only after recording
     the mismatch in evidence.
   - Watch the dispatched run with `gh run watch --exit-status`.
   - Capture the run URL, run ID, conclusion, runner label evidence, interpreter
     resolution, and proxy env evidence from logs or artifacts.

4. Dispatch the proxy-disabled architecture audit dry-run.
   - Use the repository-supported strategy for disabling proxy behavior if it
     is already available in the active workflow, runner environment, or issue
     #110 instructions.
   - Do not edit `.github/workflows/architecture-audit.yml` to add a temporary
     input, bypass, or fallback.
   - Watch the run with `gh run watch --exit-status`.
   - Capture the run URL, run ID, conclusion, interpreter resolution, and proxy
     env evidence showing the proxy-disabled path.

5. Update issue evidence only after green runs.
   - Update #110 with both green run links and the key audit-log excerpts
     instead of opening a duplicate hardening task.
   - Close #86 only if the v1.6.2 reproduction is clean and the maintainer's
     issue workflow permits closure from this task.
   - If either dry-run fails, leave #86 open and route any required hardening
     through #110, preserving single-threaded ownership.

6. Keep this task verification-only.
   - Do not edit workflow files, runner bootstrap scripts, or `scripts/ci`
     files.
   - Do not commit, merge, tag, publish, or push.
   - Do not weaken release gates, claim-safety policy, or P0/P1 severity.

## Files Likely To Change

Verification-only evidence files:

- `docs/validation/local_codex_runner/issue-116/plan.md`
- `docs/validation/local_codex_runner/issue-116/test.md` in the execution
  phase, with local command outputs and remote run-watch summaries
- `docs/validation/local_codex_runner/issue-116/code.md` in the execution
  phase, explicitly stating that no source or workflow files changed
- `docs/validation/local_codex_runner/issue-116/review.md` if a later review
  phase runs

GitHub issue state expected to change after successful validation:

- Issue #110 comment updated with the green run links and audit-log evidence
- Issue #86 closed only if v1.6.2 reproduces clean

Source files expected not to change:

- `.github/workflows/architecture-audit.yml`
- `.github/workflows/architecture-audit*.yml`
- `.github/workflows/opus-*`
- runner bootstrap scripts
- `scripts/ci/opus_*`
- package metadata, release gates, SDK code, verifier code, schemas, and release
  artifacts

## Tests And Local Gates

Issue-required validation commands:

```bash
gh workflow run architecture-audit.yml -f milestone=v1.6.2 --ref main
gh run watch --exit-status
bash scripts/ci/opus_runner_selftest.sh
```

Local preflight commands:

```bash
git status --short
rg -n "ARCHITECTURE_AUDIT_PYTHON|HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|milestone_tag|milestone" .github/workflows/architecture-audit.yml
rg --files .github/workflows scripts | rg "architecture-audit|opus|scripts/ci"
```

If the active workflow still uses `milestone_tag`, record the rejected
`milestone` dispatch and the successful `milestone_tag` retry, without claiming
the issue-required spelling passed. If `scripts/ci/opus_runner_selftest.sh`
remains absent, record the exact failure and use workflow log evidence for
interpreter and proxy verification.

No full product gate is required because this issue is verification-only and
must not edit code. If any source file is accidentally modified, stop and
restore only the accidental local change made during this task, then rerun the
local evidence checks before closure.

## Risk Classification

P1, medium validation risk.

The risk is not product runtime behavior; the task is verification-only. The
medium risk comes from external execution dependencies: self-hosted runner
availability, GitHub Actions dispatch behavior, proxy state, and the visible
local mismatch between the issue command (`milestone`) and the workflow input
name (`milestone_tag`). There is also local evidence that the required
`scripts/ci/opus_runner_selftest.sh` script is absent in this checkout. These
risks should be handled by recording exact failures and routing any hardening
through #110, not by editing workflows in issue #116.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-116/plan.md` for this planning
  phase.
- `docs/validation/local_codex_runner/issue-116/test.md` in the validation
  phase, including:
  - local preflight command outputs,
  - selftest output or missing-file blocker,
  - both workflow dispatch commands,
  - both `gh run watch --exit-status` results,
  - run URLs and run IDs,
  - interpreter evidence (`which python`, `python --version`, and/or
    `ARCHITECTURE_AUDIT_PYTHON --version`),
  - proxy env evidence for enabled and disabled runs.
- `docs/validation/local_codex_runner/issue-116/code.md` in the execution
  phase, confirming no workflow, runner, CI script, package, release, SDK,
  verifier, schema, or gate files changed.
- `docs/validation/local_codex_runner/issue-116/review.md` if a later review
  phase runs, confirming evidence completeness and that hardening ownership
  remains with #110.

## Safety Confirmation

This task will not merge branches, create tags, move tags, publish npm
packages, publish PyPI packages, push to PyPI, push to any remote, or weaken
release gates. It will not lower P0/P1 severity, remove failing tests to
manufacture a pass, loosen release gates, loosen claim-safety policy, or
read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI
tokens, private keys, `.pypirc`, or `.npmrc`.
