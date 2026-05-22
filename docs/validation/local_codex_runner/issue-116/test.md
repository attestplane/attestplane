# Issue 116 Validation Evidence

Validation timestamp: `2026-05-22T11:17:06Z`

Plan ID: `30bdd396c08f49ea`

## Result

Blocked. This runner phase did not produce the two required green
`architecture-audit.yml` dry-runs for v1.6.2.

No workflow, runner, CI script, package, release, SDK, verifier, schema, or gate
file was changed to manufacture a pass. The observed blockers are local runner
environment issues and an absent selftest script in this checkout.

## Checkout

```text
$ git rev-parse --abbrev-ref HEAD
codex/issue-116-p1-ci-validate-the-v1-6-2-opus-runner-network-in

$ git rev-parse HEAD
0cf4fd4ce51992408fda63049419d8c5467f2b92

$ git status --short
?? docs/validation/local_codex_runner/issue-116/
```

## Local Workflow Surface

```text
$ rg --files .github/workflows scripts | rg "architecture-audit|opus|scripts/ci"
.github/workflows/architecture-audit.yml
```

There are no local `.github/workflows/opus-*` files and no local
`scripts/ci/opus_*` files in this checkout.

Relevant `architecture-audit.yml` lines:

```text
15:      milestone_tag:
31:  group: architecture-audit-${{ github.event.workflow_run.id || inputs.milestone_tag }}
36:  ARCHITECTURE_AUDIT_PYTHON: python3.11
37:  HTTP_PROXY: http://127.0.0.1:7897
38:  HTTPS_PROXY: http://127.0.0.1:7897
39:  ALL_PROXY: http://127.0.0.1:7897
40:  NO_PROXY: 127.0.0.1,localhost
51:    runs-on: [self-hosted, macOS, ARM64, opus-plan]
62:          "$ARCHITECTURE_AUDIT_PYTHON" --version
```

The local workflow dispatch input is `milestone_tag`, not `milestone`.

## Interpreter And Proxy Evidence

Local interpreter resolution:

```text
$ which python; python --version; which python3; python3 --version; which python3.11 || true; python3.11 --version || true
/Users/macworkers/.local/bin/python
Python 3.14.4
/opt/homebrew/bin/python3
Python 3.14.4
/opt/homebrew/bin/python3.11
Python 3.11.15
```

Local proxy environment:

```text
$ env | sort | rg '^(HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|http_proxy|https_proxy|all_proxy|no_proxy)='
HTTPS_PROXY=http://127.0.0.1:7897
HTTP_PROXY=http://127.0.0.1:7897
http_proxy=http://127.0.0.1:7897
https_proxy=http://127.0.0.1:7897
```

## Required Selftest

```text
$ bash scripts/ci/opus_runner_selftest.sh
bash: scripts/ci/opus_runner_selftest.sh: No such file or directory
```

The required selftest script is absent in this checkout, so this command cannot
confirm runner interpreter or proxy behavior locally.

## GitHub CLI Preflight

```text
$ gh --version
gh version 2.67.0 (2025-02-11)
https://github.com/cli/cli/releases/tag/v2.67.0
```

```text
$ gh auth status
github.com
  X Failed to log in to github.com account merchloubna70-dot (default)
  - Active account: true
  - The token in default is invalid.
  - To re-authenticate, run: gh auth login -h github.com
  - To forget about this account, run: gh auth logout -h github.com -u merchloubna70-dot
```

Proxy-enabled API access is blocked in this runner sandbox:

```text
$ gh workflow list
could not get workflows: Get "https://api.github.com/repos/attestplane/attestplane/actions/workflows?per_page=50&page=1": proxyconnect tcp: dial tcp 127.0.0.1:7897: connect: operation not permitted
```

Proxy-disabled API access is also unavailable:

```text
$ env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy gh workflow list
error connecting to api.github.com
check your internet connection or https://githubstatus.com
```

## Required Dispatch Attempt

Issue-required command:

```text
$ gh workflow run architecture-audit.yml -f milestone=v1.6.2 --ref main
panic: runtime error: invalid memory address or nil pointer dereference
[signal SIGSEGV: segmentation violation code=0x2 addr=0x0 pc=0x101615568]

goroutine 1 [running]:
github.com/cli/cli/v2/pkg/cmd/workflow/shared.FindWorkflow(...)
	/Users/runner/work/cli/cli/pkg/cmd/workflow/shared/shared.go:139 +0x148
github.com/cli/cli/v2/pkg/cmd/workflow/shared.ResolveWorkflow(...)
	/Users/runner/work/cli/cli/pkg/cmd/workflow/shared/shared.go:207 +0x22c
github.com/cli/cli/v2/pkg/cmd/workflow/run.runRun(...)
	/Users/runner/work/cli/cli/pkg/cmd/workflow/run/run.go:273 +0x1d0
```

Retry with the local workflow's declared input name:

```text
$ gh workflow run architecture-audit.yml -f milestone_tag=v1.6.2 --ref main
panic: runtime error: invalid memory address or nil pointer dereference
[signal SIGSEGV: segmentation violation code=0x2 addr=0x0 pc=0x10517d568]

goroutine 1 [running]:
github.com/cli/cli/v2/pkg/cmd/workflow/shared.FindWorkflow(...)
	/Users/runner/work/cli/cli/pkg/cmd/workflow/shared/shared.go:139 +0x148
github.com/cli/cli/v2/pkg/cmd/workflow/shared.ResolveWorkflow(...)
	/Users/runner/work/cli/cli/pkg/cmd/workflow/shared/shared.go:207 +0x22c
github.com/cli/cli/v2/pkg/cmd/workflow/run.runRun(...)
	/Users/runner/work/cli/cli/pkg/cmd/workflow/run/run.go:273 +0x1d0
```

Proxy-disabled retry with the local input name:

```text
$ env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy gh workflow run architecture-audit.yml -f milestone_tag=v1.6.2 --ref main
panic: runtime error: invalid memory address or nil pointer dereference
[signal SIGSEGV: segmentation violation code=0x2 addr=0x0 pc=0x105a85568]

goroutine 1 [running]:
github.com/cli/cli/v2/pkg/cmd/workflow/shared.FindWorkflow(...)
	/Users/runner/work/cli/cli/pkg/cmd/workflow/shared/shared.go:139 +0x148
github.com/cli/cli/v2/pkg/cmd/workflow/shared.ResolveWorkflow(...)
	/Users/runner/work/cli/cli/pkg/cmd/workflow/shared/shared.go:207 +0x22c
github.com/cli/cli/v2/pkg/cmd/workflow/run.runRun(...)
	/Users/runner/work/cli/cli/pkg/cmd/workflow/run/run.go:273 +0x1d0
```

No run ID or run URL was created by these attempts, so
`gh run watch --exit-status` could not be run against a dispatched
architecture-audit workflow.

## Issue Updates

#110 was not updated and #86 was not closed in this phase because the required
green v1.6.2 proxy-enabled and proxy-disabled dry-run evidence was not produced.
Any hardening required to make this validation pass should remain owned by #110.

## Local Gate Fix

The initial local runner gate failed in
`tests/local_codex_runner/test_git_ops.py::test_commit_removes_transient_prompt_and_log_evidence`
because the fake git fixture did not provide output for the exact
`status --porcelain --untracked-files=all` command used by
`GitOps.status_paths()`.

The test fixture was updated to model both status commands used by
`GitOps.commit_all()`.

Focused verification:

```text
$ sdk/python/.venv/bin/pytest -q tests/local_codex_runner/test_git_ops.py
........                                                                 [100%]
8 passed in 0.09s
```

Full local gate:

```text
$ sdk/python/.venv/bin/python -m compileall scripts && sdk/python/.venv/bin/pytest -q
Listing 'scripts'...
Listing 'scripts/api'...
Listing 'scripts/conformance'...
Listing 'scripts/dev'...
Listing 'scripts/fault'...
Listing 'scripts/local_codex_runner'...
Listing 'scripts/local_codex_runner/launchd'...
Listing 'scripts/local_codex_runner/prompts'...
Listing 'scripts/observability'...
Listing 'scripts/release'...
Listing 'scripts/security'...
Listing 'scripts/storage'...
1227 passed in 118.36s (0:01:58)
```
