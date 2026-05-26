#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Poll open GitHub issues for local Codex repair."""

from __future__ import annotations

import argparse
import json

from scripts.local_codex_runner.config import add_common_args, load_config, overrides_from_args
from scripts.local_codex_runner.github_cli import GitHubCLI
from scripts.local_codex_runner.models import candidate_fetch_limit, processable_issues


def poll_queue(args: argparse.Namespace) -> list[dict[str, object]]:
    config = load_config(args.config, overrides_from_args(args))
    gh = GitHubCLI(dry_run=config.dry_run)
    issues = gh.list_issues(config.repo or "", None, candidate_fetch_limit(config.max_issues_per_run))
    include = set(args.include_label or [])
    exclude = set(args.exclude_label or [])
    if not getattr(args, "retry_needs_human", False):
        exclude.add(config.needs_human_label)
    queue = processable_issues(
        issues,
        approved_label=config.approved_label,
        pr_opened_label=config.pr_opened_label,
        needs_human_label=config.needs_human_label,
        max_issues_per_run=config.max_issues_per_run,
        include_labels=include or None,
        exclude_labels=exclude or None,
    )
    return [
        {
            "body": issue.body,
            "category": issue.category,
            "dedup_key": issue.dedup_key,
            "labels": issue.labels,
            "number": issue.number,
            "severity": issue.severity,
            "title": issue.title,
            "url": issue.url,
        }
        for issue in queue
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument("--retry-needs-human", action="store_true")
    args = parser.parse_args()
    print(json.dumps(poll_queue(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
