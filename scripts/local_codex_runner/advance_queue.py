#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Advance blocked local Codex work without weakening release gates."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from scripts.local_codex_runner.config import (
    RunnerConfig,
    add_common_args,
    load_config,
    overrides_from_args,
)
from scripts.local_codex_runner.github_cli import CheckStatus, GitHubCLI
from scripts.local_codex_runner.models import IssueTask

DEPENDENCY_LINE_RE = re.compile(r"(?im)^\s*(?:depends\s+on|depends-on|dependencies)\s*:\s*(?P<refs>.+)$")
ISSUE_REF_RE = re.compile(r"#(?P<number>[1-9][0-9]*)")
SOURCE_PLANNING_RE = re.compile(r"(?im)^\s*Source planning issue:\s*#(?P<number>[1-9][0-9]*)\s*$")
ISSUE_RANGE_RE = re.compile(r"\bIssues?\s+(?P<start>[1-9][0-9]*)\s*[–-]\s*(?P<end>[1-9][0-9]*)\b")
ISSUE_ORDINAL_RE = re.compile(r"\bIssue\s+(?P<ordinal>[1-9][0-9]*)\b")
EXTENDS_RE = re.compile(r"\bextends?\s+#(?P<number>[1-9][0-9]*)\b", re.IGNORECASE)


@dataclass(frozen=True)
class PullRequestState:
    number: int
    title: str
    url: str
    base_branch: str
    author: str
    labels: list[str]
    is_draft: bool
    merge_state_status: str
    review_decision: str | None
    checks: list[CheckStatus] = field(default_factory=list)


@dataclass(frozen=True)
class AdvanceDecision:
    action: Literal["skip", "comment", "merge", "unlock"]
    target_type: Literal["pr", "issue"]
    target_number: int
    reason: str
    waiting_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_dependencies(body: str) -> list[int]:
    """Return explicitly declared issue dependencies from a planned-task body."""

    dependencies: set[int] = set()
    for match in DEPENDENCY_LINE_RE.finditer(body):
        dependencies.update(int(ref.group("number")) for ref in ISSUE_REF_RE.finditer(match.group("refs")))
    return sorted(dependencies)


def source_planning_issue(body: str) -> int | None:
    match = SOURCE_PLANNING_RE.search(body)
    return int(match.group("number")) if match else None


def infer_dependencies_from_siblings(issue: IssueTask, siblings: list[IssueTask]) -> list[int]:
    """Infer plan-local dependencies from generated issue prose.

    The plan-to-issues workflow emits "Issue 1", "Issue 3", and "Issues 1-3"
    prose in acceptance criteria. Those are plan-local ordinals, not GitHub
    issue numbers, so map them to same-source planned-task siblings by issue
    number order. This is intentionally narrow and only applies when all tasks
    share the same "Source planning issue" header.
    """

    by_ordinal = {index: sibling.number for index, sibling in enumerate(sorted(siblings, key=lambda item: item.number), start=1)}
    inferred: set[int] = set()
    for match in ISSUE_RANGE_RE.finditer(issue.body):
        start = int(match.group("start"))
        end = int(match.group("end"))
        for ordinal in range(min(start, end), max(start, end) + 1):
            if ordinal in by_ordinal:
                inferred.add(by_ordinal[ordinal])
    for match in ISSUE_ORDINAL_RE.finditer(issue.body):
        ordinal = int(match.group("ordinal"))
        if ordinal in by_ordinal:
            inferred.add(by_ordinal[ordinal])
    inferred.update(int(match.group("number")) for match in EXTENDS_RE.finditer(issue.body))
    inferred.discard(issue.number)
    return sorted(inferred)


def dependencies_for_issue(issue: IssueTask, siblings: list[IssueTask]) -> list[int]:
    return sorted(set(parse_dependencies(issue.body)).union(infer_dependencies_from_siblings(issue, siblings)))


def decide_pr_action(pr: PullRequestState, config: RunnerConfig) -> AdvanceDecision:
    labels = set(pr.labels)
    waiting_on: list[str] = []
    blocking_labels = sorted(labels.intersection(config.blocking_pr_labels))
    if pr.base_branch != config.base_branch:
        waiting_on.append(f"base:{pr.base_branch}")
    if pr.is_draft:
        waiting_on.append("draft")
    if config.auto_merge_ready_label not in labels:
        waiting_on.append(f"label:{config.auto_merge_ready_label}")
    if blocking_labels:
        waiting_on.extend(f"blocking-label:{label}" for label in blocking_labels)
    if config.allowed_pr_authors and pr.author not in set(config.allowed_pr_authors):
        waiting_on.append(f"author:{pr.author}")
    if pr.merge_state_status.lower() != "clean":
        waiting_on.append(f"merge-state:{pr.merge_state_status}")
    if pr.review_decision in {"CHANGES_REQUESTED", "REVIEW_REQUIRED"}:
        waiting_on.append(f"review:{pr.review_decision}")

    check_buckets = {check.bucket for check in pr.checks}
    if not pr.checks:
        waiting_on.append("checks:missing")
    elif check_buckets.intersection({"fail", "cancel", "pending"}):
        waiting_on.append("checks:not-green")

    if waiting_on:
        return AdvanceDecision("comment", "pr", pr.number, "waiting_for_merge_requirements", sorted(waiting_on))
    if not config.allow_auto_merge:
        return AdvanceDecision("skip", "pr", pr.number, "auto_merge_disabled")
    return AdvanceDecision("merge", "pr", pr.number, "all_merge_requirements_satisfied")


def decide_dependency_unlock(
    issue: IssueTask,
    dependency_states: dict[int, str],
    config: RunnerConfig,
    dependencies: list[int] | None = None,
) -> AdvanceDecision:
    labels = set(issue.labels)
    if config.approved_label in labels:
        return AdvanceDecision("skip", "issue", issue.number, "already_approved")
    dependencies = dependencies if dependencies is not None else parse_dependencies(issue.body)
    if not dependencies:
        return AdvanceDecision("skip", "issue", issue.number, "no_explicit_dependencies")

    waiting_on = [f"issue:{number}:{dependency_states.get(number, 'UNKNOWN')}" for number in dependencies if dependency_states.get(number) != "CLOSED"]
    if waiting_on:
        return AdvanceDecision("comment", "issue", issue.number, "waiting_for_dependencies", waiting_on)
    if not config.allow_dependency_unlock:
        return AdvanceDecision("skip", "issue", issue.number, "dependency_unlock_disabled")
    return AdvanceDecision("unlock", "issue", issue.number, "dependencies_satisfied")


def pr_state_from_gh_json(data: dict[str, Any], checks: list[CheckStatus]) -> PullRequestState:
    author = data.get("author") or {}
    return PullRequestState(
        number=int(data["number"]),
        title=str(data.get("title", "")),
        url=str(data.get("url", "")),
        base_branch=str(data.get("baseRefName", "")),
        author=str(author.get("login", author.get("name", ""))),
        labels=[str(label.get("name", label)) for label in data.get("labels", []) if label.get("name", label)],
        is_draft=bool(data.get("isDraft", False)),
        merge_state_status=str(data.get("mergeStateStatus", "")),
        review_decision=data.get("reviewDecision"),
        checks=checks,
    )


def raw_labels(data: dict[str, Any]) -> set[str]:
    return {str(label.get("name", label)) for label in data.get("labels", []) if label.get("name", label)}


def matches_label_filters(data: dict[str, Any], include: list[str], exclude: list[str]) -> bool:
    labels = raw_labels(data)
    return all(label in labels for label in include) and not labels.intersection(exclude)


def advance_queue(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(args.config, overrides_from_args(args))
    gh = GitHubCLI(dry_run=config.dry_run)
    decisions: list[AdvanceDecision] = []
    writes = 0

    if args.mode in {"all", "prs"}:
        pr_fetch_limit = max(args.pr_limit, 50) if args.include_label or args.exclude_label else args.pr_limit
        raw_prs = [
            raw_pr
            for raw_pr in gh.list_pull_requests(config.repo or "", config.base_branch, limit=pr_fetch_limit)
            if matches_label_filters(raw_pr, args.include_label, args.exclude_label)
        ][: args.pr_limit]
        for raw_pr in raw_prs:
            pr_number = str(raw_pr["number"])
            pr = pr_state_from_gh_json(raw_pr, gh.pr_checks(config.repo or "", pr_number))
            decision = decide_pr_action(pr, config)
            decisions.append(decision)
            if decision.action == "merge" and writes < config.max_pr_merges_per_run:
                gh.merge_pr(config.repo or "", decision.target_number)
                writes += 1
            elif decision.action == "comment" and args.comment:
                gh.comment_pr(config.repo or "", decision.target_number, render_decision_comment(decision))

    if args.mode in {"all", "deps"}:
        issues = gh.list_issues(config.repo or "", config.planned_task_label, args.issue_limit)
        sibling_issues = gh.list_issues(config.repo or "", config.planned_task_label, args.issue_limit, state="all")
        siblings_by_source: dict[int | None, list[IssueTask]] = {}
        for issue in sibling_issues:
            siblings_by_source.setdefault(source_planning_issue(issue.body), []).append(issue)
        issue_dependencies = {
            issue.number: dependencies_for_issue(issue, siblings_by_source.get(source_planning_issue(issue.body), [issue])) for issue in issues
        }
        dependency_numbers = sorted({number for dependencies in issue_dependencies.values() for number in dependencies})
        dependency_states = {number: gh.view_issue_state(config.repo or "", number) for number in dependency_numbers}
        for issue in issues:
            decision = decide_dependency_unlock(issue, dependency_states, config, issue_dependencies[issue.number])
            decisions.append(decision)
            if decision.action == "unlock" and writes < config.max_dependency_unlocks_per_run:
                gh.add_labels(config.repo or "", decision.target_number, [config.approved_label])
                if config.waiting_deps_label in issue.labels:
                    gh.remove_labels(config.repo or "", decision.target_number, [config.waiting_deps_label])
                writes += 1
            elif decision.action == "comment" and args.comment:
                gh.add_labels(config.repo or "", decision.target_number, [config.waiting_deps_label])
                gh.comment_issue(config.repo or "", decision.target_number, render_decision_comment(decision))

    return {
        "commands_run": gh.commands_run,
        "decisions": [decision.to_dict() for decision in decisions],
        "dry_run": config.dry_run,
        "writes": writes,
    }


def render_decision_comment(decision: AdvanceDecision) -> str:
    waiting = "\n".join(f"- {item}" for item in decision.waiting_on) or "- none"
    return f"Local Codex queue advance decision: `{decision.reason}`.\n\nWaiting on:\n{waiting}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument("--mode", choices=["all", "prs", "deps"], default="all")
    parser.add_argument("--pr-limit", type=int, default=20)
    parser.add_argument("--issue-limit", type=int, default=50)
    parser.add_argument("--comment", action="store_true", help="write waiting-state comments/labels when not dry-run")
    args = parser.parse_args()
    print(json.dumps(advance_queue(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
