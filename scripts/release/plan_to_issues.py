#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Convert an accepted development plan into GitHub planned-task issues."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TASK_LABEL = "planned-task"
TITLE_RE = re.compile(
    r"^(?:#+\s*)?(?:\*\*)?\s*ISSUE\s+\d+\s*[.:·-]\s*(?P<title>\[[Pp][0-2]\].+?)(?:\*\*)?\s*$",
)
FALLBACK_TITLE_RE = re.compile(r"^(?:#+\s*)?(?:\*\*)?(?P<title>\[[Pp][0-2]\].+?)(?:\*\*)?\s*$")
PRIORITY_RE = re.compile(r"\[(P[0-2])\]", re.IGNORECASE)

MODULE_LABELS = {
    "architecture": ["architecture-audit"],
    "audit": ["architecture-audit", "area:release-integrity"],
    "boundary": ["type:security"],
    "compliance": ["area:docs", "claim-safety"],
    "compatibility": ["area:conformance"],
    "conformance": ["area:conformance", "area:verifier"],
    "docs": ["area:docs", "type:docs"],
    "release": ["area:release-integrity"],
    "security": ["type:security", "area:governance"],
    "test": ["type:docs"],
}


@dataclass(frozen=True)
class PlannedTask:
    title: str
    body: str
    priority: str
    labels: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "body": self.body,
            "priority": self.priority,
            "labels": list(self.labels),
        }


def normalize_title(raw: str) -> str:
    title = raw.strip()
    title = title.strip("*").strip()
    title = re.sub(r"\s+", " ", title)
    return title


def extract_priority(title: str, body: str) -> str:
    title_match = PRIORITY_RE.search(title)
    if title_match:
        return title_match.group(1).upper()
    body_match = re.search(r"Priority:\s*(P[0-2])", body, flags=re.IGNORECASE)
    if body_match:
        return body_match.group(1).upper()
    return "P2"


def labels_for(title: str, priority: str) -> tuple[str, ...]:
    labels: list[str] = [TASK_LABEL]
    labels.append("priority-P0" if priority == "P0" else f"priority:{priority}")
    for module in re.findall(r"\[([^\]]+)\]", title):
        key = module.strip().lower()
        labels.extend(MODULE_LABELS.get(key, []))
    deduped: list[str] = []
    for label in labels:
        if label not in deduped:
            deduped.append(label)
    return tuple(deduped)


def is_title_line(line: str) -> re.Match[str] | None:
    match = TITLE_RE.match(line.strip())
    if match:
        return match
    fallback = FALLBACK_TITLE_RE.match(line.strip())
    if fallback and "Acceptance criteria" not in line and "Validation commands" not in line:
        return fallback
    return None


def parse_plan(markdown: str, source_issue: int) -> list[PlannedTask]:
    tasks: list[PlannedTask] = []
    current_title: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_body
        if current_title is None:
            return
        body = "\n".join(current_body).strip()
        priority = extract_priority(current_title, body)
        if f"Source planning issue: #{source_issue}" not in body:
            body = f"Source planning issue: #{source_issue}\n{body}".strip()
        body = body + "\n\nGenerated from accepted development plan."
        tasks.append(
            PlannedTask(
                title=current_title,
                body=body + "\n",
                priority=priority,
                labels=labels_for(current_title, priority),
            ),
        )
        current_title = None
        current_body = []

    for line in markdown.splitlines():
        match = is_title_line(line)
        if match:
            flush()
            current_title = normalize_title(match.group("title"))
            current_body = []
            continue
        if current_title is not None:
            current_body.append(line)
    flush()
    return tasks


def run_gh(args: list[str]) -> str:
    proc = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def issue_exists(title: str, source_issue: int) -> str | None:
    query = f"{title} in:title"
    stdout = run_gh(["issue", "list", "--state", "all", "--search", query, "--json", "number,url,title"])
    for item in json.loads(stdout or "[]"):
        if item.get("title") == title:
            body = run_gh(["issue", "view", str(item["number"]), "--json", "body", "--jq", ".body"])
            if f"Source planning issue: #{source_issue}" in body:
                return str(item.get("url") or item.get("number") or "")
    return None


def create_issue(task: PlannedTask, source_issue: int) -> str:
    existing = issue_exists(task.title, source_issue)
    if existing:
        return existing
    args = ["issue", "create", "--title", task.title, "--body", task.body]
    for label in task.labels:
        args.extend(["--label", label])
    return run_gh(args)


def create_issues(tasks: list[PlannedTask], source_issue: int) -> list[dict[str, object]]:
    created: list[dict[str, object]] = []
    for task in tasks:
        url = create_issue(task, source_issue)
        created.append({**task.as_dict(), "url": url})
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--source-issue", type=int, required=True)
    parser.add_argument("--create", action="store_true", help="Create GitHub issues with gh.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)

    markdown = args.plan_file.read_text(encoding="utf-8")
    tasks = parse_plan(markdown, args.source_issue)
    if not tasks:
        print("no issue-ready tasks found in plan", file=sys.stderr)
        return 1

    payload: object
    if args.create:
        payload = create_issues(tasks, args.source_issue)
    else:
        payload = [task.as_dict() for task in tasks]

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for item in payload:
            if isinstance(item, dict):
                print(f"{item.get('title')} {item.get('url', '')}".rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
