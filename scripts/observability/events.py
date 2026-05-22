#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Structured event helpers for release automation observability."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import IO, Any


PLANNED_ISSUE_REFETCH = "planned_issue_refetch"
PLANNED_ISSUE_POST_CREATE_FETCH = "planned_issue_post_create_fetch"

REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    PLANNED_ISSUE_REFETCH: frozenset(
        {
            "event",
            "milestone",
            "requested_count",
            "refetched_count",
            "latency_ms",
            "ok",
        },
    ),
    PLANNED_ISSUE_POST_CREATE_FETCH: frozenset(
        {
            "event",
            "milestone",
            "created_count",
            "refetched_count",
            "latency_ms",
            "ok",
        },
    ),
}


class EventValidationError(ValueError):
    """Raised when a structured observability event is malformed."""


@dataclass(frozen=True)
class ObservabilityEvent:
    """Validated structured observability event."""

    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return dict(self.payload)

    def to_json(self) -> str:
        return json.dumps(self.payload, sort_keys=True)


def parse_event(payload: dict[str, Any]) -> ObservabilityEvent:
    """Validate and return a structured observability event."""

    event_type = payload.get("event")
    if not isinstance(event_type, str) or not event_type:
        raise EventValidationError("event payload requires a non-empty string event field")

    required = REQUIRED_FIELDS.get(event_type)
    if required is None:
        raise EventValidationError(f"unknown observability event type: {event_type}")

    missing = sorted(field for field in required if field not in payload)
    if missing:
        raise EventValidationError(f"{event_type} missing required fields: {', '.join(missing)}")

    if not isinstance(payload.get("milestone"), str):
        raise EventValidationError(f"{event_type} milestone must be a string")
    if not isinstance(payload.get("latency_ms"), int):
        raise EventValidationError(f"{event_type} latency_ms must be an integer")
    if not isinstance(payload.get("ok"), bool):
        raise EventValidationError(f"{event_type} ok must be a boolean")

    for field in ("created_count", "requested_count", "refetched_count"):
        if field in payload and not isinstance(payload[field], int):
            raise EventValidationError(f"{event_type} {field} must be an integer")

    return ObservabilityEvent(dict(payload))


def emit_event(payload: dict[str, Any], stream: IO[str] | None = None) -> None:
    """Validate and emit one JSON event line."""

    output = stream if stream is not None else sys.stdout
    print(parse_event(payload).to_json(), file=output)
