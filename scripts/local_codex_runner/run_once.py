#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Run one bounded local Codex runner poll cycle."""

from __future__ import annotations

import argparse
import glob
import json
from collections import deque
from pathlib import Path
from types import SimpleNamespace

from scripts.local_codex_runner.advance_queue import advance_queue
from scripts.local_codex_runner.config import RunnerConfig, add_common_args, load_config, overrides_from_args
from scripts.local_codex_runner.git_ops import GitOps
from scripts.local_codex_runner.github_cli import GitHubCLI, RunnerCommandError
from scripts.local_codex_runner.models import IssueTask, candidate_fetch_limit, processable_issues, task_has_product_delta
from scripts.local_codex_runner.needs_human import recover_needs_human_for_labels
from scripts.local_codex_runner.run_issue import run_issue
from scripts.local_codex_runner.state_store import load_state, save_state


def run_once(args: argparse.Namespace) -> dict[str, object]:
    config = load_config(args.config, overrides_from_args(args))
    gh = GitHubCLI(dry_run=config.dry_run)
    product_delta_idle = product_delta_idle_summary(config)
    cleanup_summary: dict[str, object] | None = cleanup_stale_state(config, gh) if config.cleanup_stale_state else None
    include = set(config.lane_include_labels).union(args.include_label or [])
    exclude = set(config.lane_exclude_labels).union(args.exclude_label or [])
    needs_human_summary = recover_needs_human_for_labels(
        config,
        gh,
        include_labels=include or None,
        exclude_labels=exclude or None,
    )
    transient_cleanup = [] if config.dry_run else GitOps(config.workdir_path()).remove_transient_evidence()
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
            product_delta_idle=product_delta_idle["active"],
        )
        advance_summary = advance_queue(advance_args)
    product_delta_recovery = ensure_product_delta_idle_recovery_task(config, gh, product_delta_idle)
    external_errors: list[dict[str, object]] = []
    try:
        issues = gh.list_issues(
            config.repo or "",
            config.approved_label,
            candidate_fetch_limit(config.max_issues_per_run),
        )
    except RunnerCommandError as exc:
        external_errors.append({"stage": "list_issues", "error": str(exc)})
        issues = []
    results = []
    for issue in processable_issues(
        issues,
        approved_label=config.approved_label,
        pr_opened_label=config.pr_opened_label,
        needs_human_label=config.needs_human_label,
            max_issues_per_run=config.max_issues_per_run,
            include_labels=include or None,
            exclude_labels=exclude or None,
            require_product_delta=bool(product_delta_idle["active"]),
    ):
        result = run_issue(config, issue.number, include, exclude)
        results.append(result.to_dict())
    return {
        "advance": advance_summary,
        "cleanup": cleanup_summary,
        "lane": lane_summary(config),
        "needs_human_recovery": needs_human_summary,
        "product_delta_recovery": product_delta_recovery,
        "external_errors": external_errors,
        "processed": len(results),
        "product_delta_idle": product_delta_idle,
        "results": results,
        "transient_cleanup": transient_cleanup,
    }


def ensure_product_delta_idle_recovery_task(
    config: RunnerConfig,
    gh: GitHubCLI,
    product_delta_idle: dict[str, object],
) -> dict[str, object]:
    if not product_delta_idle.get("active"):
        return {"enabled": False, "reason": "idle_inactive"}
    if not config.product_delta_idle_create_task:
        return {"enabled": False, "reason": "disabled"}
    try:
        planned = gh.list_issues(config.repo or "", config.planned_task_label, 100)
    except RunnerCommandError as exc:
        return {"enabled": True, "action": "error", "stage": "list_planned_tasks", "error": str(exc)}
    product_tasks = [issue for issue in planned if task_has_product_delta(issue)]
    include = set(config.lane_include_labels) or None
    exclude = set(config.lane_exclude_labels) or None
    processable_product_tasks = processable_issues(
        product_tasks,
        approved_label=config.approved_label,
        pr_opened_label=config.pr_opened_label,
        needs_human_label=config.needs_human_label,
        max_issues_per_run=10,
        include_labels=include,
        exclude_labels=exclude,
        require_product_delta=True,
    )
    if processable_product_tasks:
        return {
            "enabled": True,
            "action": "kept",
            "reason": "processable_product_task_exists",
            "issue_numbers": [issue.number for issue in processable_product_tasks[:10]],
        }
    markable_product_tasks = [
        issue
        for issue in product_tasks
        if product_delta_idle_recovery_markable_issue(issue, config, include_labels=include, exclude_labels=exclude)
    ]
    if markable_product_tasks:
        issue = markable_product_tasks[0]
        try:
            gh.add_labels(config.repo or "", issue.number, [config.approved_label])
        except RunnerCommandError as exc:
            return {"enabled": True, "action": "error", "stage": "mark_product_task", "issue_number": issue.number, "error": str(exc)}
        return {
            "enabled": True,
            "action": "marked",
            "reason": "marked_existing_product_task",
            "issue_number": issue.number,
            "label": config.approved_label,
        }
    labels = product_delta_idle_recovery_labels(config)
    body = render_product_delta_idle_recovery_body(product_delta_idle)
    try:
        created = gh.create_issue(config.repo or "", config.product_delta_idle_task_title, body, labels)
    except RunnerCommandError as exc:
        return {"enabled": True, "action": "error", "stage": "create_recovery_task", "error": str(exc)}
    return {
        "enabled": True,
        "action": "created",
        "title": config.product_delta_idle_task_title,
        "labels": labels,
        "url": created,
    }


def product_delta_idle_recovery_markable_issue(
    issue: IssueTask,
    config: RunnerConfig,
    *,
    include_labels: set[str] | None,
    exclude_labels: set[str] | None,
) -> bool:
    labels = set(issue.labels)
    if config.approved_label in labels:
        return False
    if config.pr_opened_label in labels or config.needs_human_label in labels:
        return False
    if include_labels and not labels.intersection(include_labels):
        return False
    if exclude_labels and labels.intersection(exclude_labels):
        return False
    return task_has_product_delta(issue)


def product_delta_idle_recovery_labels(config: RunnerConfig) -> list[str]:
    labels = [
        config.planned_task_label,
        config.approved_label,
        "priority:P1",
        "area:verifier",
        "area:conformance",
    ]
    labels.extend(config.product_delta_idle_task_labels)
    deduped: list[str] = []
    for label in labels:
        if label not in deduped:
            deduped.append(label)
    return deduped


def render_product_delta_idle_recovery_body(product_delta_idle: dict[str, object]) -> str:
    log_path = product_delta_idle.get("log", "unknown")
    idle_events = product_delta_idle.get("consecutive_idle_events", "unknown")
    return (
        "Source planning issue: product-delta idle recovery\n\n"
        "Plan ID: `product-delta-idle-recovery`\n\n"
        "The stable train has repeatedly skipped the next release because only support/docs/release deltas are present.\n\n"
        "Scope:\n"
        "- Implement a small user-visible product behavior in the SDK, verifier, CLI, ProofBundle, canonicalization, or conformance surface.\n"
        "- Include focused tests that exercise the new behavior.\n"
        "- Do not satisfy this task with docs-only, release-only, runner-only, or support-only changes.\n\n"
        "Acceptance criteria:\n"
        "- The diff includes at least one product implementation file under `sdk/` or a verifier/CLI product surface.\n"
        "- The diff includes focused regression coverage for the behavior.\n"
        "- Local validation passes for the touched SDK/verifier/conformance path.\n\n"
        "Validation commands:\n"
        "- Run the relevant focused pytest or npm test command for the touched product path.\n"
        "- Run `bash scripts/check-public-api.sh` when public API manifests change.\n\n"
        f"Recovery evidence:\n- product_delta_idle.consecutive_idle_events: {idle_events}\n- train log: `{log_path}`\n"
    )


def product_delta_idle_summary(config: RunnerConfig) -> dict[str, object]:
    if not config.product_delta_idle_dispatch:
        return {"active": False, "reason": "disabled"}
    if not config.product_delta_idle_log_glob:
        return {"active": False, "reason": "missing_log_glob"}
    latest = latest_matching_log(config.product_delta_idle_log_glob, config.workdir_path())
    if latest is None:
        return {
            "active": False,
            "reason": "no_matching_log",
            "log_glob": config.product_delta_idle_log_glob,
        }
    lines = tail_lines(latest, config.product_delta_idle_tail_lines)
    idle_count = consecutive_product_delta_idle_events(lines)
    return {
        "active": idle_count >= config.product_delta_idle_threshold,
        "consecutive_idle_events": idle_count,
        "log": str(latest),
        "reason": "threshold_met" if idle_count >= config.product_delta_idle_threshold else "below_threshold",
        "threshold": config.product_delta_idle_threshold,
    }


def latest_matching_log(pattern: str, workdir: Path) -> Path | None:
    expanded = str(Path(pattern).expanduser())
    if not Path(expanded).is_absolute():
        expanded = str(workdir / expanded)
    matches = [Path(path) for path in glob.glob(expanded)]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def tail_lines(path: Path, limit: int) -> list[str]:
    recent: deque[str] = deque(maxlen=limit)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            recent.append(line.rstrip("\n"))
    return list(recent)


def consecutive_product_delta_idle_events(lines: list[str]) -> int:
    count = 0
    for line in reversed(lines):
        lowered = line.lower()
        if "product_delta_skipped" in lowered or "no product implementation delta since" in lowered:
            count += 1
            continue
        if any(marker in lowered for marker in ("prepared local tag", "preparing v", "cycle failed", "release-cd", "published")):
            break
    return count


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
    external_errors: list[dict[str, object]] = []
    for issue_number in tracked:
        try:
            issue_state = gh.view_issue_state(config.repo or "", issue_number)
        except RunnerCommandError as exc:
            external_errors.append({"issue": issue_number, "error": str(exc)})
            continue
        if issue_state == "CLOSED":
            if state.prune_issue(issue_number):
                pruned.append(issue_number)
        else:
            kept.append({"issue": issue_number, "state": issue_state})
    if pruned:
        save_state(state_path, state)
    return {
        "external_errors": external_errors,
        "invalid_branch_keys": invalid_branch_keys,
        "pruned_closed_issues": pruned,
        "kept": kept,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()
    print(json.dumps(run_once(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
