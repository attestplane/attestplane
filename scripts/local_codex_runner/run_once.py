#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Run one bounded local Codex runner poll cycle."""

from __future__ import annotations

import argparse
import json

from scripts.local_codex_runner.config import add_common_args, load_config, overrides_from_args
from scripts.local_codex_runner.github_cli import GitHubCLI
from scripts.local_codex_runner.models import should_process_issue
from scripts.local_codex_runner.run_issue import run_issue


def run_once(args: argparse.Namespace) -> dict[str, object]:
    config = load_config(args.config, overrides_from_args(args))
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
    return {"processed": len(results), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()
    print(json.dumps(run_once(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

