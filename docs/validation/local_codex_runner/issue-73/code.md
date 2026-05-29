<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Issue 73 Code Evidence

Plan ID: `fe23fa36d63771bf`

## Summary

Expanded regression coverage for the real `v1.8.3..v1.8.4` release-prep range.

- Updated `sdk/python/tests/test_release_gate.py` to use the current mixed release-prep fixture and assert the classifier sees the real range as `product_support_delta`, not metadata-only noise.
- Added a stable auto-train regression in `sdk/python/tests/test_stable_auto_train_queue.py` that mirrors the real `v1.8.3..v1.8.4` commit subjects and proves the range contains real work alongside release-prep commits.

## Files Changed

- `sdk/python/tests/test_release_gate.py`
- `sdk/python/tests/test_stable_auto_train_queue.py`
- `docs/validation/local_codex_runner/issue-73/code.md`
- `docs/validation/local_codex_runner/issue-73/test.md`
- `docs/validation/local_codex_runner/issue-73/gate_report.md`
- `docs/validation/local_codex_runner/issue-73/gate_report.json`

## Release-Prep Range Confirmation

The local `v1.8.3..v1.8.4` range contains release-prep metadata plus real local-runner and release-gate work:

```text
a04510c chore(release): prepare v1.8.4
2aa7222 Fix release gate tests and stabilize README link
1e8cc4e chore(release): prepare v1.8.4
288fde1 Relax product support gating in release training
41184bd Relax product support gating in release training
6b6c021 local runner: remove recovery gating from live queue
c6dd118 local runner: consume open issues directly
```

Representative files from `git diff --name-status v1.8.3..v1.8.4` include:

```text
M  scripts/local_codex_runner/git_ops.py
M  scripts/local_codex_runner/github_cli.py
M  scripts/local_codex_runner/models.py
M  scripts/local_codex_runner/poll_issues.py
M  scripts/local_codex_runner/run_issue.py
M  scripts/local_codex_runner/run_once.py
M  scripts/release/release_gate.py
M  sdk/python/tests/test_import_surface.py
M  sdk/python/tests/test_release_gate.py
A  tests/local_codex_runner/test_github_cli.py
A  tests/local_codex_runner/test_models.py
A  tests/local_codex_runner/test_run_issue_flow.py
```

Conclusion: the release-prep diff is not only train-generated metadata. The
range includes real local runner and release-gate test/support updates alongside
release notes, release artifacts, and package metadata.
