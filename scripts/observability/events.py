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
AUTODEV_TRAIN = "autodev-train"
PUBLICATION_STATUS = "publication_status"
PUSH_CI_WAIT_START = "push_ci_wait_start"
PUSH_CI_PROBE_RETRY = "push_ci_probe_retry"
PUSH_CI_FAILED = "push_ci_failed"
PUSH_CI_PASSED = "push_ci_passed"
PUSH_CI_WAITING = "push_ci_waiting"
RELEASE_CD_WAIT_START = "release_cd_wait_start"
RELEASE_CD_FAILED_BUT_COMPLETE = "release_cd_failed_but_complete"
CADENCE_SKIPPED = "cadence_skipped"
PRODUCT_DELTA_SKIPPED = "product_delta_skipped"
CYCLE_PREPARE = "cycle_prepare"
CYCLE_PREPARED_LOCAL = "cycle_prepared_local"
CYCLE_FAILED = "cycle_failed"
CYCLE_FINISHED = "cycle_finished"

COMMON_RELEASE_TRAIN_FIELDS = frozenset({"event", "ts", "train"})


def _release_train_fields(*fields: str) -> frozenset[str]:
    return COMMON_RELEASE_TRAIN_FIELDS | frozenset(fields)


FIELD_TYPES: dict[str, type[Any]] = {
    "event": str,
    "milestone": str,
    "requested_count": int,
    "refetched_count": int,
    "created_count": int,
    "latency_ms": int,
    "ok": bool,
    "ts": str,
    "train": str,
    "tag": str,
    "python_visible": bool,
    "npm_visible": bool,
    "npm_latest": bool,
    "github_release": bool,
    "complete": bool,
    "head_sha": str,
    "error": str,
    "details": str,
    "summary": str,
    "target_tag": str,
    "previous_tag": str,
    "force_cadence": bool,
    "reason": str,
    "product_files": list,
    "product_support_files": list,
    "support_only_files": list,
    "ignored_files": list,
    "channel": str,
    "publish": bool,
    "wait": bool,
    "dry_run": bool,
    "poll_seconds": int,
    "result": str,
}

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
    PUBLICATION_STATUS: _release_train_fields(
        "tag",
        "python_visible",
        "npm_visible",
        "npm_latest",
        "github_release",
        "complete",
    ),
    PUSH_CI_WAIT_START: _release_train_fields("head_sha"),
    PUSH_CI_PROBE_RETRY: _release_train_fields("head_sha", "error"),
    PUSH_CI_FAILED: _release_train_fields("head_sha", "details"),
    PUSH_CI_PASSED: _release_train_fields("head_sha"),
    PUSH_CI_WAITING: _release_train_fields("head_sha", "summary"),
    RELEASE_CD_WAIT_START: _release_train_fields("target_tag"),
    RELEASE_CD_FAILED_BUT_COMPLETE: _release_train_fields("target_tag"),
    CADENCE_SKIPPED: _release_train_fields(
        "previous_tag", "target_tag", "force_cadence", "reason"
    ),
    PRODUCT_DELTA_SKIPPED: _release_train_fields(
        "previous_tag",
        "target_tag",
        "reason",
        "product_files",
        "product_support_files",
        "support_only_files",
        "ignored_files",
    ),
    CYCLE_PREPARE: _release_train_fields(
        "previous_tag", "target_tag", "channel", "publish", "wait", "dry_run"
    ),
    CYCLE_PREPARED_LOCAL: _release_train_fields("target_tag", "publish"),
    CYCLE_FAILED: _release_train_fields("error", "poll_seconds"),
    CYCLE_FINISHED: _release_train_fields("result", "poll_seconds"),
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
        raise EventValidationError(
            "event payload requires a non-empty string event field"
        )

    required = REQUIRED_FIELDS.get(event_type)
    if required is None:
        raise EventValidationError(f"unknown observability event type: {event_type}")

    missing = sorted(
        field for field in required if field not in payload or payload[field] is None
    )
    if missing:
        raise EventValidationError(
            f"{event_type} missing required fields: {', '.join(missing)}"
        )

    for field in sorted(required):
        expected_type = FIELD_TYPES.get(field)
        if expected_type is None:
            continue
        value = payload[field]
        if expected_type is int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise EventValidationError(f"{event_type} {field} must be an integer")
            continue
        if expected_type is bool:
            if not isinstance(value, bool):
                raise EventValidationError(f"{event_type} {field} must be a boolean")
            continue
        if expected_type is list:
            if not isinstance(value, list):
                raise EventValidationError(f"{event_type} {field} must be a list")
            continue
        if not isinstance(value, expected_type):
            raise EventValidationError(
                f"{event_type} {field} must be a {expected_type.__name__}"
            )

    return ObservabilityEvent(dict(payload))


def emit_event(payload: dict[str, Any], stream: IO[str] | None = None) -> None:
    """Validate and emit one JSON event line."""

    output = stream if stream is not None else sys.stdout
    print(parse_event(payload).to_json(), file=output)
