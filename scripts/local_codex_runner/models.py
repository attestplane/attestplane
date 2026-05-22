#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Data models for the local Codex runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

DEFAULT_CANDIDATE_FETCH_FLOOR = 20
DEFAULT_CANDIDATE_FETCH_MULTIPLIER = 10
DEFAULT_CANDIDATE_FETCH_CEILING = 100


class RunnerStatus(StrEnum):
    SUCCESS = "SUCCESS"
    LOCAL_FAILED = "LOCAL_FAILED"
    REVIEW_BLOCKED = "REVIEW_BLOCKED"
    CI_FAILED = "CI_FAILED"
    DRY_RUN = "DRY_RUN"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class IssueTask:
    number: int
    title: str
    body: str
    url: str
    labels: list[str]
    severity: str | None = None
    category: str | None = None
    dedup_key: str | None = None

    @classmethod
    def from_gh_json(cls, data: dict[str, Any]) -> "IssueTask":
        labels = [str(label.get("name", label)) for label in data.get("labels", []) if label.get("name", label)]
        return cls(
            number=int(data["number"]),
            title=str(data.get("title", "")),
            body=str(data.get("body", "")),
            url=str(data.get("url", "")),
            labels=labels,
            severity=first_label_value(labels, "severity:"),
            category=first_label_value(labels, "category:") or infer_category(labels),
            dedup_key=f"issue:{data['number']}",
        )


@dataclass
class RunnerResult:
    issue_number: int
    branch: str | None
    pr_url: str | None
    status: RunnerStatus
    plan_path: str | None
    evidence_dir: str
    commands_run: list[str] = field(default_factory=list)
    local_test_summary: str | None = None
    ci_summary: str | None = None
    residual_risks: list[str] = field(default_factory=list)
    started_at_utc: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at_utc: str | None = None

    def finish(self, status: RunnerStatus | None = None) -> "RunnerResult":
        if status is not None:
            self.status = status
        self.finished_at_utc = datetime.now(UTC).isoformat()
        return self

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass
class State:
    processed_issue_ids: list[int] = field(default_factory=list)
    active_issue_ids: list[int] = field(default_factory=list)
    branch_mappings: dict[str, str] = field(default_factory=dict)
    retry_counts: dict[str, int] = field(default_factory=dict)
    last_result: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "State":
        return cls(
            processed_issue_ids=sorted(int(item) for item in data.get("processed_issue_ids", [])),
            active_issue_ids=sorted(int(item) for item in data.get("active_issue_ids", [])),
            branch_mappings={str(key): str(value) for key, value in sorted(data.get("branch_mappings", {}).items())},
            retry_counts={str(key): int(value) for key, value in sorted(data.get("retry_counts", {}).items())},
            last_result=data.get("last_result"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_issue_ids": sorted(set(self.active_issue_ids)),
            "branch_mappings": dict(sorted(self.branch_mappings.items())),
            "last_result": self.last_result,
            "processed_issue_ids": sorted(set(self.processed_issue_ids)),
            "retry_counts": dict(sorted(self.retry_counts.items())),
        }

    def mark_active(self, issue_number: int, branch: str) -> None:
        if issue_number not in self.active_issue_ids:
            self.active_issue_ids.append(issue_number)
        self.branch_mappings[str(issue_number)] = branch

    def mark_finished(self, issue_number: int, result: RunnerResult) -> None:
        self.active_issue_ids = [item for item in self.active_issue_ids if item != issue_number]
        if issue_number not in self.processed_issue_ids:
            self.processed_issue_ids.append(issue_number)
        self.last_result = result.to_dict()

    def prune_issue(self, issue_number: int) -> bool:
        """Remove stale active/branch state for an issue that no longer needs work."""
        before_active = list(self.active_issue_ids)
        before_branch = dict(self.branch_mappings)
        self.active_issue_ids = [item for item in self.active_issue_ids if item != issue_number]
        self.branch_mappings.pop(str(issue_number), None)
        return before_active != self.active_issue_ids or before_branch != self.branch_mappings

    def increment_retry(self, key: str) -> int:
        self.retry_counts[key] = self.retry_counts.get(key, 0) + 1
        return self.retry_counts[key]


def first_label_value(labels: list[str], prefix: str) -> str | None:
    for label in labels:
        if label.startswith(prefix):
            return label.removeprefix(prefix)
    return None


def issue_priority_rank(task: IssueTask) -> int:
    """Return a stable queue rank where lower numbers are more urgent."""
    candidates = list(task.labels)
    if task.title.startswith("[") and "]" in task.title:
        candidates.append(task.title[1 : task.title.index("]")])
    for candidate in candidates:
        normalized = candidate.lower().replace("_", "-")
        if normalized in {"priority-p0", "priority:p0", "p0"}:
            return 0
        if normalized in {"priority-p1", "priority:p1", "p1"}:
            return 1
        if normalized in {"priority-p2", "priority:p2", "p2"}:
            return 2
        if normalized in {"priority-p3", "priority:p3", "p3"}:
            return 3
    return 99


def infer_category(labels: list[str]) -> str | None:
    known = ("claim-safety", "verifier", "test-gap", "docs", "release-blocker", "feature-gap")
    for label in labels:
        if label in known:
            return label
    return None


def should_process_issue(
    task: IssueTask,
    *,
    approved_label: str,
    pr_opened_label: str,
    needs_human_label: str,
    include_labels: set[str] | None = None,
    exclude_labels: set[str] | None = None,
) -> bool:
    labels = set(task.labels)
    if approved_label not in labels:
        return False
    if pr_opened_label in labels or needs_human_label in labels:
        return False
    if include_labels and not labels.intersection(include_labels):
        return False
    return not (exclude_labels and labels.intersection(exclude_labels))


def candidate_fetch_limit(max_issues_per_run: int) -> int:
    """Fetch a candidate pool larger than the per-cycle processing limit.

    GitHub issue queries are label-only. The runner must filter out already-opened
    PRs and human-blocked issues locally, so fetching only the per-cycle limit can
    starve ready issues behind an ineligible queue head.
    """
    if max_issues_per_run < 1:
        return DEFAULT_CANDIDATE_FETCH_FLOOR
    return min(
        DEFAULT_CANDIDATE_FETCH_CEILING,
        max(DEFAULT_CANDIDATE_FETCH_FLOOR, max_issues_per_run * DEFAULT_CANDIDATE_FETCH_MULTIPLIER),
    )


def processable_issues(
    issues: list[IssueTask],
    *,
    approved_label: str,
    pr_opened_label: str,
    needs_human_label: str,
    max_issues_per_run: int,
    include_labels: set[str] | None = None,
    exclude_labels: set[str] | None = None,
) -> list[IssueTask]:
    queue = [
        (index, issue)
        for index, issue in enumerate(issues)
        if should_process_issue(
            issue,
            approved_label=approved_label,
            pr_opened_label=pr_opened_label,
            needs_human_label=needs_human_label,
            include_labels=include_labels,
            exclude_labels=exclude_labels,
        )
    ]
    queue.sort(key=lambda item: (issue_priority_rank(item[1]), item[0]))
    return [issue for _, issue in queue[: max(0, max_issues_per_run)]]
