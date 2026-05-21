#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Shared plan schema helpers for release planning workflows.

The schema is intentionally lightweight and serializes to a fenced JSON
comment block so GitHub issue comments remain readable while downstream
automation can parse a stable machine-readable payload.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

PLAN_SCHEMA_NAME = "attestplane.plan.v1"
PLAN_SCHEMA_VERSION = 1
PLAN_SCHEMA_MARKER_START = "<!-- ATT_PLAN_SCHEMA_V1_START -->"
PLAN_SCHEMA_MARKER_END = "<!-- ATT_PLAN_SCHEMA_V1_END -->"

PLAN_BLOCK_RE = re.compile(
    r"<!-- ATT_PLAN_SCHEMA_V1_START -->\s*```json\s*(?P<body>\{.*?\})\s*```\s*<!-- ATT_PLAN_SCHEMA_V1_END -->",
    re.DOTALL,
)


@dataclass(frozen=True)
class PlanIssue:
    ordinal: int
    title: str
    priority: str
    modules: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    validation_commands: tuple[str, ...]
    rollout_notes: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "title": self.title,
            "priority": self.priority,
            "modules": list(self.modules),
            "acceptance_criteria": list(self.acceptance_criteria),
            "validation_commands": list(self.validation_commands),
            "rollout_notes": self.rollout_notes,
        }


def canonical_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"generated_at", "plan_id"}
    }


def compute_plan_id(payload: Mapping[str, Any], *, source_issue: int | None = None) -> str:
    fingerprint_payload = _fingerprint_payload(payload)
    if source_issue is not None:
        fingerprint_payload = dict(fingerprint_payload)
        fingerprint_payload["source_issue"] = int(source_issue)
    fingerprint = canonical_json(fingerprint_payload)
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]


def with_plan_id(payload: Mapping[str, Any], *, source_issue: int | None = None) -> dict[str, Any]:
    result = dict(payload)
    result["plan_id"] = compute_plan_id(result, source_issue=source_issue)
    return result


def render_plan_block(payload: Mapping[str, Any]) -> str:
    serialized = canonical_json(dict(payload))
    return (
        f"{PLAN_SCHEMA_MARKER_START}\n"
        "```json\n"
        f"{serialized}\n"
        "```\n"
        f"{PLAN_SCHEMA_MARKER_END}"
    )


def append_plan_block(markdown: str, payload: Mapping[str, Any]) -> str:
    body = markdown.rstrip()
    return f"{body}\n\n{render_plan_block(payload)}\n"


def extract_plan_payload(comment_body: str) -> dict[str, Any] | None:
    match = PLAN_BLOCK_RE.search(comment_body)
    if match is None:
        return None
    payload = json.loads(match.group("body"))
    if not isinstance(payload, dict):
        raise ValueError("structured plan payload must be a JSON object")
    return payload


def plan_issue_body(*, source_issue: int, plan_id: str, plan_schema: str, task: Mapping[str, Any]) -> str:
    lines = [
        f"Source planning issue: #{source_issue}",
        f"Plan schema: `{plan_schema}`",
        f"Plan ID: `{plan_id}`",
        f"Priority: {task.get('priority', 'P2')}",
        "",
        f"Title: {task.get('title', '')}",
        "",
        "Affected modules:",
    ]
    for module in task.get("modules", []):
        lines.append(f"- {module}")
    lines.extend(
        [
            "",
            "Acceptance criteria:",
        ]
    )
    for index, item in enumerate(task.get("acceptance_criteria", []), start=1):
        lines.append(f"{index}. {item}")
    lines.extend(
        [
            "",
            "Validation commands:",
        ]
    )
    for command in task.get("validation_commands", []):
        lines.append(f"- `{command}`")
    rollout_notes = str(task.get("rollout_notes", "")).strip()
    if rollout_notes:
        lines.extend(["", "Rollout / migration notes:", rollout_notes])
    lines.extend(["", "Generated from accepted development plan."])
    return "\n".join(lines).strip() + "\n"
