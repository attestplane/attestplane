#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Run one bounded local Codex runner poll cycle."""

from __future__ import annotations

import argparse
import json
from types import SimpleNamespace

from scripts.local_codex_runner.advance_queue import advance_queue
from scripts.local_codex_runner.config import RunnerConfig, add_common_args, load_config, overrides_from_args
from scripts.local_codex_runner.git_ops import GitOps
from scripts.local_codex_runner.github_cli import GitHubCLI
from scripts.local_codex_runner.models import candidate_fetch_limit, processable_issues
from scripts.local_codex_runner.needs_human import recover_needs_human_for_labels
from scripts.local_codex_runner.run_issue import run_issue
from scripts.local_codex_runner.state_store import load_state, save_state


def run_once(args: argparse.Namespace) -> dict[str, object]:
    config = load_config(args.config, overrides_from_args(args))
    gh = GitHubCLI(dry_run=config.dry_run)
    transient_cleanup = [] if config.dry_run else GitOps(config.workdir_path()).remove_transient_evidence()
    cleanup_summary: dict[str, object] | None = cleanup_stale_state(config, gh) if config.cleanup_stale_state else None
    include = set(config.lane_include_labels).union(args.include_label or [])
    exclude = set(config.lane_exclude_labels).union(args.exclude_label or [])
    needs_human_summary = recover_needs_human_for_labels(
        config,
        gh,
        include_labels=include or None,
        exclude_labels=exclude or None,
    )
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
            include_label=[],
            exclude_label=[],
            comment=False,
        )
        advance_summary = advance_queue(advance_args)
    issues = gh.list_issues(config.repo or "", config.approved_label, candidate_fetch_limit(config.max_issues_per_run))
    results = []
    for issue in processable_issues(
        issues,
        approved_label=config.approved_label,
        pr_opened_label=config.pr_opened_label,
        needs_human_label=config.needs_human_label,
        max_issues_per_run=config.max_issues_per_run,
        include_labels=include or None,
        exclude_labels=exclude or None,
    ):
        result = run_issue(config, issue.number, include, exclude)
        results.append(result.to_dict())
    return {
        "advance": advance_summary,
        "cleanup": cleanup_summary,
        "lane": lane_summary(config),
        "needs_human_recovery": needs_human_summary,
        "processed": len(results),
        "results": results,
        "transient_cleanup": transient_cleanup,
    }


def lane_summary(config: RunnerConfig) -> dict[str, object] | None:
    if not config.lane_name:
        return None
    return {
        "include_labels": sorted(config.lane_include_labels),
        "exclude_labels": sorted(config.lane_exclude_labels),
        "name": config.lane_name,
        "slot": config.lane_slot,
    }


def cleanup_stale_state(config: RunnerConfig, gh: GitHubCLI) -> dict[str, object]:
    """Prune stale local state for issues that GitHub already closed."""
    state_path = config.state_file()
    state = load_state(state_path)
    invalid_branch_keys = sorted(key for key in state.branch_mappings if not key.isdigit())
    tracked = sorted(set(state.active_issue_ids).union(int(key) for key in state.branch_mappings if key.isdigit()))
    pruned: list[int] = []
    kept: list[dict[str, object]] = []
    for issue_number in tracked:
        issue_state = gh.view_issue_state(config.repo or "", issue_number)
        if issue_state == "CLOSED":
            if state.prune_issue(issue_number):
                pruned.append(issue_number)
        else:
            kept.append({"issue": issue_number, "state": issue_state})
    if pruned:
        save_state(state_path, state)
    return {"invalid_branch_keys": invalid_branch_keys, "pruned_closed_issues": pruned, "kept": kept}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()
    print(json.dumps(run_once(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
