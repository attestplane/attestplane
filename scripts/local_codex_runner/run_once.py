#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Run one bounded local Codex runner poll cycle."""

from __future__ import annotations

import argparse
import json
from types import SimpleNamespace

from scripts.local_codex_runner.advance_queue import advance_queue
from scripts.local_codex_runner.config import add_common_args, load_config, overrides_from_args
from scripts.local_codex_runner.github_cli import GitHubCLI
from scripts.local_codex_runner.models import should_process_issue
from scripts.local_codex_runner.run_issue import run_issue


def run_once(args: argparse.Namespace) -> dict[str, object]:
    config = load_config(args.config, overrides_from_args(args))
    advance_summary: dict[str, object] | None = None
    if config.auto_advance_before_consume:
        advance_args = SimpleNamespace(
            config=args.config,
            repo=config.repo,
            workdir=config.workdir,
            dry_run=config.dry_run,
            max_local_fix_rounds=config.max_local_fix_rounds,
            max_ci_fix_rounds=config.max_ci_fix_rounds,
            create_pr=config.create_pr,
            watch_ci=config.watch_ci,
            allow_dirty=config.allow_dirty,
            mode="all",
            pr_limit=20,
            issue_limit=50,
            comment=False,
        )
        advance_summary = advance_queue(advance_args)
    gh = GitHubCLI(dry_run=config.dry_run)
    issues = gh.list_issues(config.repo or "", config.approved_label, config.max_issues_per_run)
    include = set(args.include_label or [])
    exclude = set(args.exclude_label or [])
    results = []
    for issue in issues:
        if not should_process_issue(
            issue,
            approved_label=config.approved_label,
            pr_opened_label=config.pr_opened_label,
            needs_human_label=config.needs_human_label,
            include_labels=include or None,
            exclude_labels=exclude or None,
        ):
            continue
        result = run_issue(config, issue.number, include, exclude)
        results.append(result.to_dict())
    return {"advance": advance_summary, "processed": len(results), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()
    print(json.dumps(run_once(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
