#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Find stale autodev issues that do not target Attestplane product work.

The default mode is a dry run. Closing issues requires --execute so the train
cannot silently delete or close planning history.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass

AUTODEV_LABELS = frozenset({"planned-task", "development-plan", "autodev-plan"})
PRODUCT_TERMS = frozenset(
    {
        "attestation",
        "canonical",
        "conformance",
        "dsse",
        "eidAS".lower(),
        "hash chain",
        "in-toto",
        "ocsp",
        "proof bundle",
        "rfc-3161",
        "signing",
        "tsa",
        "verifier",
    }
)
SUPPORT_TERMS = frozenset(
    {
        "actions",
        "architecture audit",
        "autodev",
        "ci",
        "daily plan",
        "docs",
        "npm dist-tag",
        "opus_plan_command",
        "publish",
        "release",
        "release-cd",
        "slsa",
        "train",
        "workflow",
    }
)


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    labels: list[str]
    url: str
    body: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "number": self.number,
            "title": self.title,
            "labels": self.labels,
            "url": self.url,
            "body": self.body,
        }


def normalized_labels(labels: list[str]) -> set[str]:
    return {label.strip().lower() for label in labels if label.strip()}


def issue_is_autodev(issue: Issue) -> bool:
    return bool(AUTODEV_LABELS & normalized_labels(issue.labels))


def issue_is_product_targeted(issue: Issue) -> bool:
    text = f"{issue.title}\n{issue.body}".lower()
    return any(term in text for term in PRODUCT_TERMS)


def issue_is_support_targeted(issue: Issue) -> bool:
    text = f"{issue.title}\n{issue.body}".lower()
    return any(term in text for term in SUPPORT_TERMS)


def classify_issue(issue: Issue) -> str:
    if not issue_is_autodev(issue):
        return "not_autodev"
    if issue_is_product_targeted(issue):
        return "keep_product_targeted"
    if issue_is_support_targeted(issue):
        return "stale_support_only_autodev"
    return "manual_review_unknown_scope"


def run_gh(argv: list[str]) -> str:
    completed = subprocess.run(
        ["gh", *argv],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def fetch_open_issues(limit: int) -> list[Issue]:
    raw = run_gh(
        [
            "issue",
            "list",
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            "number,title,labels,url",
        ]
    )
    issues: list[Issue] = []
    for item in json.loads(raw):
        labels = [
            label["name"] for label in item.get("labels", []) if label.get("name")
        ]
        body = run_gh(
            ["issue", "view", str(item["number"]), "--json", "body", "--jq", ".body"]
        )
        issues.append(
            Issue(
                number=int(item["number"]),
                title=str(item["title"]),
                labels=labels,
                url=str(item["url"]),
                body=body,
            )
        )
    return issues


def close_candidate(issue: Issue) -> None:
    run_gh(["issue", "edit", str(issue.number), "--add-label", "stale-autodev"])
    run_gh(
        [
            "issue",
            "close",
            str(issue.number),
            "--comment",
            "Closing as stale autodev support-only planning. Product work should be tracked in a product-scoped issue.",
        ]
    )


def build_report(issues: list[Issue]) -> dict[str, object]:
    buckets: dict[str, list[dict[str, object]]] = {}
    for issue in issues:
        buckets.setdefault(classify_issue(issue), []).append(
            {
                "number": issue.number,
                "title": issue.title,
                "labels": issue.labels,
                "url": issue.url,
            }
        )
    return {"schema": "attestplane_stale_autodev_issue_cleanup.v1", "buckets": buckets}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    issues = fetch_open_issues(args.limit)
    report = build_report(issues)
    print(json.dumps(report, indent=2, sort_keys=True))
    candidates = [
        issue
        for issue in issues
        if classify_issue(issue) == "stale_support_only_autodev"
    ]
    if args.execute:
        for issue in candidates:
            close_candidate(issue)
        print(
            f"closed {len(candidates)} stale support-only autodev issue(s)",
            file=sys.stderr,
        )
    else:
        print(
            f"dry-run: {len(candidates)} stale support-only autodev candidate(s)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
