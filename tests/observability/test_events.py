#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import io
import json

import pytest

from scripts.observability.events import (
    AUTODEV_TRAIN,
    CADENCE_SKIPPED,
    CYCLE_FAILED,
    CYCLE_FINISHED,
    CYCLE_PREPARE,
    CYCLE_PREPARED_LOCAL,
    EventValidationError,
    PLANNED_ISSUE_POST_CREATE_FETCH,
    PRODUCT_DELTA_SKIPPED,
    PUBLICATION_STATUS,
    PUSH_CI_FAILED,
    PUSH_CI_PASSED,
    PUSH_CI_PROBE_RETRY,
    PUSH_CI_WAITING,
    PUSH_CI_WAIT_START,
    RELEASE_CD_FAILED_BUT_COMPLETE,
    RELEASE_CD_WAIT_START,
    REQUIRED_FIELDS,
    emit_event,
    parse_event,
)
from scripts.release import plan_to_issues


def post_create_fetch_payload() -> dict[str, object]:
    return {
        "event": PLANNED_ISSUE_POST_CREATE_FETCH,
        "milestone": "v1.6.2",
        "created_count": 3,
        "refetched_count": 3,
        "latency_ms": 12,
        "ok": True,
    }


def release_train_payloads() -> dict[str, dict[str, object]]:
    common = {"ts": "2026-05-29T12:34:56Z", "train": AUTODEV_TRAIN}
    return {
        PUBLICATION_STATUS: {
            "event": PUBLICATION_STATUS,
            **common,
            "tag": "v1.2.3",
            "python_visible": True,
            "npm_visible": True,
            "npm_latest": False,
            "github_release": True,
            "complete": False,
        },
        PUSH_CI_WAIT_START: {
            "event": PUSH_CI_WAIT_START,
            **common,
            "head_sha": "deadbeef",
        },
        PUSH_CI_PROBE_RETRY: {
            "event": PUSH_CI_PROBE_RETRY,
            **common,
            "head_sha": "deadbeef",
            "error": "temporary gh failure",
        },
        PUSH_CI_FAILED: {
            "event": PUSH_CI_FAILED,
            **common,
            "head_sha": "deadbeef",
            "details": "ci=failure (https://example.test/runs/1)",
        },
        PUSH_CI_PASSED: {
            "event": PUSH_CI_PASSED,
            **common,
            "head_sha": "deadbeef",
        },
        PUSH_CI_WAITING: {
            "event": PUSH_CI_WAITING,
            **common,
            "head_sha": "deadbeef",
            "summary": "missing=ci pending=sdk-python",
        },
        RELEASE_CD_WAIT_START: {
            "event": RELEASE_CD_WAIT_START,
            **common,
            "target_tag": "v1.2.3",
        },
        RELEASE_CD_FAILED_BUT_COMPLETE: {
            "event": RELEASE_CD_FAILED_BUT_COMPLETE,
            **common,
            "target_tag": "v1.2.3",
        },
        CADENCE_SKIPPED: {
            "event": CADENCE_SKIPPED,
            **common,
            "previous_tag": "v1.2.2",
            "target_tag": "v1.2.3",
            "force_cadence": False,
            "reason": "no_real_work_since_previous_tag",
        },
        PRODUCT_DELTA_SKIPPED: {
            "event": PRODUCT_DELTA_SKIPPED,
            **common,
            "previous_tag": "v1.2.2",
            "target_tag": "v1.2.3",
            "reason": "support_only_delta",
            "product_files": ["src/core.py"],
            "product_support_files": ["scripts/release/helper.py"],
            "support_only_files": ["docs/runbooks/release.md"],
            "ignored_files": ["README.md"],
        },
        CYCLE_PREPARE: {
            "event": CYCLE_PREPARE,
            **common,
            "previous_tag": "v1.2.2",
            "target_tag": "v1.2.3",
            "channel": "latest",
            "publish": True,
            "wait": False,
            "dry_run": False,
        },
        CYCLE_PREPARED_LOCAL: {
            "event": CYCLE_PREPARED_LOCAL,
            **common,
            "target_tag": "v1.2.3",
            "publish": False,
        },
        CYCLE_FAILED: {
            "event": CYCLE_FAILED,
            **common,
            "error": "timed out waiting for push CI workflows",
            "poll_seconds": 300,
        },
        CYCLE_FINISHED: {
            "event": CYCLE_FINISHED,
            **common,
            "result": "v1.2.3",
            "poll_seconds": 300,
        },
    }


RELEASE_TRAIN_PAYLOADS = release_train_payloads()
RELEASE_TRAIN_EVENT_TYPES = tuple(RELEASE_TRAIN_PAYLOADS)
RELEASE_TRAIN_MISSING_CASES = tuple(
    (event_type, field)
    for event_type in RELEASE_TRAIN_EVENT_TYPES
    for field in sorted(REQUIRED_FIELDS[event_type])
)


def test_post_create_fetch_parser_accepts_required_fields() -> None:
    parsed = parse_event(post_create_fetch_payload())

    assert parsed.as_dict() == post_create_fetch_payload()


@pytest.mark.parametrize(
    "field",
    ["event", "milestone", "created_count", "refetched_count", "latency_ms", "ok"],
)
def test_post_create_fetch_parser_requires_fields(field: str) -> None:
    payload = post_create_fetch_payload()
    del payload[field]

    with pytest.raises(EventValidationError):
        parse_event(payload)


@pytest.mark.parametrize("event_type", RELEASE_TRAIN_EVENT_TYPES)
def test_release_train_parser_accepts_registered_fields(event_type: str) -> None:
    payload = RELEASE_TRAIN_PAYLOADS[event_type]

    parsed = parse_event(payload)

    assert parsed.as_dict() == payload


@pytest.mark.parametrize(("event_type", "field"), RELEASE_TRAIN_MISSING_CASES)
def test_release_train_parser_requires_each_registered_field(
    event_type: str, field: str
) -> None:
    payload = dict(RELEASE_TRAIN_PAYLOADS[event_type])
    del payload[field]

    with pytest.raises(EventValidationError):
        parse_event(payload)


def test_post_create_fetch_emit_writes_json_line() -> None:
    stream = io.StringIO()

    emit_event(post_create_fetch_payload(), stream=stream)

    assert json.loads(stream.getvalue()) == post_create_fetch_payload()


def test_post_create_fetch_emitted_after_create_refetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = plan_to_issues.PlannedTask(
        title="[P1][observability] test",
        body="Source planning issue: #113\nPlan ID: `plan-1`\n",
        priority="P1",
        labels=("planned-task",),
        plan_id="plan-1",
    )
    monkeypatch.setattr(
        plan_to_issues,
        "create_issue",
        lambda task, source_issue: "https://example.test/1",
    )
    monkeypatch.setattr(
        plan_to_issues,
        "fetch_uploaded_issues",
        lambda source_issue, plan_ids, titles: [
            {"number": 1, "title": task.title, "url": "https://example.test/1"}
        ],
    )
    stream = io.StringIO()

    uploaded = plan_to_issues.create_issues(
        [task],
        113,
        milestone="v1.6.2",
        emit_events=True,
        event_stream=stream,
    )

    event = json.loads(stream.getvalue())
    assert uploaded == [
        {"number": 1, "title": task.title, "url": "https://example.test/1"}
    ]
    assert event["event"] == PLANNED_ISSUE_POST_CREATE_FETCH
    assert event["milestone"] == "v1.6.2"
    assert event["created_count"] == 1
    assert event["refetched_count"] == 1
    assert isinstance(event["latency_ms"], int)
    assert event["ok"] is True


def test_post_create_fetch_failure_still_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = plan_to_issues.PlannedTask(
        title="[P1][observability] test",
        body="Source planning issue: #113\nPlan ID: `plan-1`\n",
        priority="P1",
        labels=("planned-task",),
        plan_id="plan-1",
    )
    monkeypatch.setattr(
        plan_to_issues,
        "create_issue",
        lambda task, source_issue: "https://example.test/1",
    )
    monkeypatch.setattr(
        plan_to_issues,
        "fetch_uploaded_issues",
        lambda source_issue, plan_ids, titles: [],
    )
    stream = io.StringIO()

    with pytest.raises(RuntimeError, match="could not be fetched back"):
        plan_to_issues.create_issues(
            [task],
            113,
            milestone="v1.6.2",
            emit_events=True,
            event_stream=stream,
        )

    event = json.loads(stream.getvalue())
    assert event["event"] == PLANNED_ISSUE_POST_CREATE_FETCH
    assert event["created_count"] == 1
    assert event["refetched_count"] == 0
    assert event["ok"] is False
