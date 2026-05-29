#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Maintain the latest OpenSSF Scorecard summary and regression issue.

This is intentionally monitor-only. It records the latest normalized summary,
compares it to the prior baseline, and opens or updates an issue when the
regression is meaningful. It never blocks release publishing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.security.scorecard_diff import (  # noqa: E402
    DEFAULT_MEANINGFUL_DROP,
    ScorecardDiff,
    ScorecardSummary,
    compare_summaries,
    load_summary,
)

DEFAULT_ISSUE_TITLE = "[P2][security] OpenSSF Scorecard regression monitoring"
DEFAULT_ISSUE_LABELS = (
    "type:security",
    "scorecard-regression",
    "monitor-only",
    "priority:P2",
)
REGRESSION_LABEL = "scorecard-regression"


def run_gh(args: list[str]) -> str:
    completed = subprocess.run(
        ["gh", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def repo_name_with_owner() -> str:
    return run_gh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])


def ensure_labels(repo: str, labels: tuple[str, ...]) -> None:
    for label in labels:
        try:
            run_gh(
                [
                    "label",
                    "create",
                    label,
                    "--repo",
                    repo,
                    "--color",
                    "0E8A16",
                    "--description",
                    f"Scorecard monitor label: {label}",
                ]
            )
        except subprocess.CalledProcessError as exc:
            if "already exists" not in (exc.stderr or "").lower():
                raise


def list_open_issues(repo: str, label: str) -> list[dict[str, object]]:
    raw = run_gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--label",
            label,
            "--json",
            "number,title,url,labels,body",
            "--limit",
            "100",
        ]
    )
    payload = json.loads(raw or "[]")
    return [dict(item) for item in payload if isinstance(item, dict)]


def _label_names(raw_labels: object) -> list[str]:
    labels: list[str] = []
    if isinstance(raw_labels, list):
        for label in raw_labels:
            if isinstance(label, dict) and isinstance(label.get("name"), str):
                labels.append(label["name"])
            elif isinstance(label, str):
                labels.append(label)
    return labels


def find_open_regression_issue(
    repo: str, title: str, labels: tuple[str, ...]
) -> dict[str, object] | None:
    regression_label = next(
        (label for label in labels if label == REGRESSION_LABEL), REGRESSION_LABEL
    )
    candidates = list_open_issues(repo, regression_label)
    for issue in candidates:
        issue_title = str(issue.get("title") or "")
        issue_labels = _label_names(issue.get("labels"))
        if issue_title == title or regression_label in issue_labels:
            return issue
    return None


def issue_body(report: ScorecardDiff, summary_path: Path, baseline_path: Path) -> str:
    regressions = report.regressions
    regression_lines = [
        f"- {item.name}: {item.baseline_score:g} -> {item.current_score:g} (drop {item.drop:g})"
        for item in regressions
    ]
    missing_lines = [f"- {name}" for name in report.missing_checks]
    new_lines = [f"- {name}" for name in report.new_checks]
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    lines = [
        "# OpenSSF Scorecard regression monitoring",
        "",
        "This issue records a meaningful Scorecard regression. It is advisory only and does not block release publishing.",
        "",
        f"- Generated at: `{timestamp}`",
        f"- Baseline summary: `{baseline_path}`",
        f"- Latest summary: `{summary_path}`",
        f"- Aggregate score change: `{report.baseline.score:g}` -> `{report.current.score:g}` (drop `{report.score_drop:g}`)",
        f"- Meaningful regression: `{str(report.meaningful_regression).lower()}`",
        "",
        "## Regressions",
    ]
    lines.extend(regression_lines or ["- none"])
    lines.extend(
        [
            "",
            "## Missing checks",
        ]
    )
    lines.extend(missing_lines or ["- none"])
    lines.extend(
        [
            "",
            "## New checks",
        ]
    )
    lines.extend(new_lines or ["- none"])
    lines.extend(
        [
            "",
            "## Notes",
            "- Scorecard remains monitor-only and is not part of the release gate.",
            "- Release publishing continues independently of this issue.",
            "- Reproduce locally with `python scripts/security/scorecard_diff.py --baseline <baseline.json> --current <current.json>`.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def create_or_update_issue(
    repo: str, title: str, body: str, labels: tuple[str, ...]
) -> dict[str, object]:
    ensure_labels(repo, labels)
    existing = find_open_regression_issue(repo, title, labels)
    if existing is None:
        args = ["issue", "create", "--repo", repo, "--title", title, "--body", body]
        for label in labels:
            args.extend(["--label", label])
        url = run_gh(args)
        return {"url": url, "action": "created"}

    issue_number = int(existing["number"])
    args = [
        "issue",
        "edit",
        str(issue_number),
        "--repo",
        repo,
        "--title",
        title,
        "--body",
        body,
    ]
    for label in labels:
        args.extend(["--add-label", label])
    run_gh(args)
    return {"number": issue_number, "url": existing.get("url"), "action": "updated"}


def _write_summary(path: Path, summary: ScorecardSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_monitor(
    *,
    baseline_path: Path,
    current_path: Path,
    latest_summary_path: Path,
    repo: str | None,
    meaningful_drop: float,
    issue_title: str,
    issue_labels: tuple[str, ...],
) -> dict[str, object]:
    current_summary = load_summary(current_path)
    _write_summary(latest_summary_path, current_summary)

    if not baseline_path.exists():
        _write_summary(baseline_path, current_summary)
        return {
            "schema": "attestplane.scorecard.monitor.v1",
            "status": "baseline_initialized",
            "baseline": str(baseline_path),
            "latest": str(latest_summary_path),
            "current": current_summary.as_dict(),
        }

    baseline_summary = load_summary(baseline_path)
    report = compare_summaries(
        baseline_summary, current_summary, meaningful_drop=meaningful_drop
    )
    payload: dict[str, object] = {
        "schema": "attestplane.scorecard.monitor.v1",
        "status": "ok" if not report.meaningful_regression else "regression",
        "baseline": str(baseline_path),
        "latest": str(latest_summary_path),
        "report": report.as_dict(),
    }
    if report.meaningful_regression:
        resolved_repo = repo or repo_name_with_owner()
        issue_result = create_or_update_issue(
            resolved_repo,
            issue_title,
            issue_body(report, latest_summary_path, baseline_path),
            issue_labels,
        )
        payload["issue"] = issue_result
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--latest-summary", type=Path, required=True)
    parser.add_argument("--repo", default="")
    parser.add_argument("--issue-title", default=DEFAULT_ISSUE_TITLE)
    parser.add_argument(
        "--issue-label",
        action="append",
        dest="issue_labels",
        default=list(DEFAULT_ISSUE_LABELS),
    )
    parser.add_argument(
        "--meaningful-drop",
        type=float,
        default=DEFAULT_MEANINGFUL_DROP,
        help="Minimum aggregate or per-check score drop to count as a meaningful regression.",
    )
    args = parser.parse_args(argv)

    report = run_monitor(
        baseline_path=args.baseline,
        current_path=args.current,
        latest_summary_path=args.latest_summary,
        repo=args.repo or None,
        meaningful_drop=args.meaningful_drop,
        issue_title=args.issue_title,
        issue_labels=tuple(args.issue_labels),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
