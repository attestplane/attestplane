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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.release.plan_schema import (  # noqa: E402
    PLAN_SCHEMA_NAME,
    compute_plan_id,
    extract_plan_payload,
    plan_issue_body,
)
from scripts.observability.events import (  # noqa: E402
    PLANNED_ISSUE_POST_CREATE_FETCH,
    emit_event,
)

TASK_LABEL = "planned-task"
TITLE_RE = re.compile(
    r"^(?:#+\s*)?(?:\*\*)?\s*ISSUE\s+\d+\s*[.:·-]\s*(?P<title>\[[Pp][0-2]\].+?)(?:\*\*)?\s*$",
)
FALLBACK_TITLE_RE = re.compile(r"^(?:#+\s*)?(?:\*\*)?(?P<title>\[[Pp][0-2]\].+?)(?:\*\*)?\s*$")
PRIORITY_RE = re.compile(r"\[(P[0-2])\]", re.IGNORECASE)

MODULE_LABELS = {
    "api": ["area:conformance"],
    "architecture": ["architecture-audit"],
    "audit": ["architecture-audit", "area:release-integrity"],
    "boundary": ["type:security"],
    "canonical": ["area:conformance"],
    "canonicalization": ["area:conformance"],
    "cli": ["area:conformance"],
    "compliance": ["area:docs", "claim-safety"],
    "compatibility": ["area:conformance"],
    "conformance": ["area:conformance", "area:verifier"],
    "docs": ["area:docs", "type:docs"],
    "proof bundle": ["area:conformance", "area:verifier"],
    "proof-bundle": ["area:conformance", "area:verifier"],
    "release": ["area:release-integrity"],
    "sdk": ["area:verifier"],
    "security": ["type:security", "area:governance"],
    "test": ["type:docs"],
    "verifier": ["area:verifier"],
}


@dataclass(frozen=True)
class PlannedTask:
    title: str
    body: str
    priority: str
    labels: tuple[str, ...]
    plan_id: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "body": self.body,
            "priority": self.priority,
            "labels": list(self.labels),
            "plan_id": self.plan_id,
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


def labels_for(title: str, priority: str, modules: list[str] | tuple[str, ...] | None = None) -> tuple[str, ...]:
    labels: list[str] = [TASK_LABEL]
    labels.append("priority-P0" if priority == "P0" else f"priority:{priority}")
    module_tokens = modules if modules is not None else re.findall(r"\[([^\]]+)\]", title)
    for module in module_tokens:
        key = module.strip().lower()
        labels.extend(MODULE_LABELS.get(key, []))
        if key not in MODULE_LABELS:
            for token, mapped_labels in MODULE_LABELS.items():
                if token in key:
                    labels.extend(mapped_labels)
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


def parse_structured_plan(markdown: str, source_issue: int) -> list[PlannedTask] | None:
    payload = extract_plan_payload(markdown)
    if payload is None:
        return None
    issues = payload.get("issues", [])
    if not isinstance(issues, list) or not issues:
        raise ValueError("structured plan payload did not include any issues")

    plan_id = str(payload.get("plan_id") or compute_plan_id(payload))
    schema_name = str(payload.get("schema", PLAN_SCHEMA_NAME))
    tasks: list[PlannedTask] = []
    for raw_issue in issues:
        if not isinstance(raw_issue, dict):
            continue
        title = normalize_title(str(raw_issue.get("title", "")))
        priority = str(raw_issue.get("priority", "P2")).upper()
        modules = raw_issue.get("modules", [])
        body = plan_issue_body(
            source_issue=source_issue,
            plan_id=plan_id,
            plan_schema=schema_name,
            task=raw_issue,
        )
        tasks.append(
            PlannedTask(
                title=title,
                body=body,
                priority=priority,
                labels=labels_for(title, priority, modules if isinstance(modules, (list, tuple)) else None),
                plan_id=plan_id,
            ),
        )
    return tasks


def parse_plan(markdown: str, source_issue: int) -> list[PlannedTask]:
    structured = parse_structured_plan(markdown, source_issue)
    if structured is not None:
        return structured

    tasks: list[PlannedTask] = []
    current_title: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_body
        if current_title is None:
            return
        body = "\n".join(current_body).strip()
        priority = extract_priority(current_title, body)
        plan_id = compute_plan_id(
            {
                "source_issue": source_issue,
                "title": current_title,
                "body": body,
            },
        )
        if f"Source planning issue: #{source_issue}" not in body:
            body = f"Source planning issue: #{source_issue}\n{body}".strip()
        if "Plan ID:" not in body:
            body = f"{body}\nPlan ID: `{plan_id}`".strip()
        body = body + "\n\nGenerated from accepted development plan."
        tasks.append(
            PlannedTask(
                title=current_title,
                body=body + "\n",
                priority=priority,
                labels=labels_for(current_title, priority),
                plan_id=plan_id,
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


def run_gh(args: list[str], *, retries: int = 0, retry_delay: float = 2.0) -> str:
    attempt = 0
    while True:
        try:
            proc = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
            return proc.stdout.strip()
        except subprocess.CalledProcessError:
            attempt += 1
            if attempt > retries:
                raise
            time.sleep(retry_delay * attempt)


def issue_exists(title: str, source_issue: int, plan_id: str | None = None) -> str | None:
    query = f"{title} in:title"
    stdout = run_gh(["issue", "list", "--state", "all", "--search", query, "--json", "number,url,title"], retries=2)
    for item in json.loads(stdout or "[]"):
        if item.get("title") == title:
            body = run_gh(["issue", "view", str(item["number"]), "--json", "body", "--jq", ".body"], retries=2)
            has_source = f"Source planning issue: #{source_issue}" in body
            has_plan = plan_id is None or f"Plan ID: `{plan_id}`" in body
            legacy_unstructured = plan_id is not None and "Plan ID:" not in body
            if has_source and (has_plan or legacy_unstructured):
                return str(item.get("url") or item.get("number") or "")
    return None


def create_issue(task: PlannedTask, source_issue: int) -> str:
    existing = issue_exists(task.title, source_issue, task.plan_id)
    if existing:
        return existing
    args = ["issue", "create", "--title", task.title, "--body", task.body]
    for label in task.labels:
        args.extend(["--label", label])
    return run_gh(args)


def issue_payload_from_github(item: dict[str, object]) -> dict[str, object]:
    labels: list[str] = []
    raw_labels = item.get("labels", [])
    if isinstance(raw_labels, list):
        for label in raw_labels:
            if isinstance(label, dict) and isinstance(label.get("name"), str):
                labels.append(label["name"])
            elif isinstance(label, str):
                labels.append(label)
    return {
        "number": item.get("number"),
        "title": item.get("title"),
        "url": item.get("url"),
        "labels": labels,
    }


def fetch_uploaded_issues(source_issue: int, plan_ids: set[str], titles: set[str] | None = None) -> list[dict[str, object]]:
    stdout = run_gh(
        [
            "issue",
            "list",
            "--state",
            "open",
            "--label",
            TASK_LABEL,
            "--limit",
            "100",
            "--json",
            "number,title,labels,url,body",
        ],
        retries=3,
    )
    uploaded: list[dict[str, object]] = []
    source_marker = f"Source planning issue: #{source_issue}"
    for item in json.loads(stdout or "[]"):
        if not isinstance(item, dict):
            continue
        body = item.get("body", "")
        if not isinstance(body, str) or source_marker not in body:
            continue
        has_matching_plan = any(f"Plan ID: `{plan_id}`" in body for plan_id in plan_ids)
        legacy_matching_title = "Plan ID:" not in body and (not titles or str(item.get("title") or "") in titles)
        if plan_ids and not (has_matching_plan or legacy_matching_title):
            continue
        uploaded.append(issue_payload_from_github(item))
    return sorted(uploaded, key=lambda issue: int(issue.get("number") or 0))


def _latency_ms(start: float) -> int:
    return max(0, int((time.perf_counter() - start) * 1000))


def _emit_post_create_fetch_event(
    *,
    milestone: str,
    created_count: int,
    refetched_count: int,
    latency_ms: int,
    ok: bool,
    stream: IO[str] | None,
) -> None:
    emit_event(
        {
            "event": PLANNED_ISSUE_POST_CREATE_FETCH,
            "milestone": milestone,
            "created_count": created_count,
            "refetched_count": refetched_count,
            "latency_ms": latency_ms,
            "ok": ok,
        },
        stream=stream,
    )


def create_issues(
    tasks: list[PlannedTask],
    source_issue: int,
    *,
    milestone: str = "",
    emit_events: bool = False,
    event_stream: IO[str] | None = None,
) -> list[dict[str, object]]:
    for task in tasks:
        create_issue(task, source_issue)
    plan_ids = {task.plan_id for task in tasks if task.plan_id}
    titles = {task.title for task in tasks}
    started = time.perf_counter()
    try:
        uploaded = fetch_uploaded_issues(source_issue, plan_ids, titles)
    except Exception:
        if emit_events:
            _emit_post_create_fetch_event(
                milestone=milestone,
                created_count=len(tasks),
                refetched_count=0,
                latency_ms=_latency_ms(started),
                ok=False,
                stream=event_stream,
            )
        raise
    if emit_events:
        _emit_post_create_fetch_event(
            milestone=milestone,
            created_count=len(tasks),
            refetched_count=len(uploaded),
            latency_ms=_latency_ms(started),
            ok=bool(uploaded),
            stream=event_stream,
        )
    if not uploaded:
        raise RuntimeError("planned-task issues were created but could not be fetched back from GitHub")
    return uploaded


def emit_dry_run_post_create_fetch_event(
    tasks: list[PlannedTask],
    milestone: str,
    stream: IO[str] | None = None,
) -> None:
    """Emit the post-create fetch shape for local dry-run validation."""

    _emit_post_create_fetch_event(
        milestone=milestone,
        created_count=len(tasks),
        refetched_count=0,
        latency_ms=0,
        ok=True,
        stream=stream,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--source-issue", type=int, default=0)
    parser.add_argument("--create", action="store_true", help="Create GitHub issues with gh.")
    parser.add_argument("--dry-run", action="store_true", help="Parse without creating GitHub issues.")
    parser.add_argument("--emit-events", action="store_true", help="Emit structured observability events.")
    parser.add_argument("--milestone", default="", help="Milestone value included in observability events.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)

    if args.create and args.dry_run:
        parser.error("--create and --dry-run are mutually exclusive")
    if args.create and not args.plan_file:
        parser.error("--create requires --plan-file")
    if args.plan_file and args.source_issue == 0:
        parser.error("--plan-file requires --source-issue")

    tasks: list[PlannedTask] = []
    if args.plan_file:
        markdown = args.plan_file.read_text(encoding="utf-8")
        tasks = parse_plan(markdown, args.source_issue)

    if not tasks and not args.dry_run:
        print("no issue-ready tasks found in plan", file=sys.stderr)
        return 1

    payload: object
    if args.create:
        payload = create_issues(
            tasks,
            args.source_issue,
            milestone=args.milestone,
            emit_events=args.emit_events,
        )
    else:
        if args.dry_run and args.emit_events:
            emit_dry_run_post_create_fetch_event(tasks, args.milestone)
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
