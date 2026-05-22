from __future__ import annotations

import io
import json

import pytest

from scripts.observability.events import (
    PLANNED_ISSUE_POST_CREATE_FETCH,
    EventValidationError,
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


def test_post_create_fetch_emit_writes_json_line() -> None:
    stream = io.StringIO()

    emit_event(post_create_fetch_payload(), stream=stream)

    assert json.loads(stream.getvalue()) == post_create_fetch_payload()


def test_post_create_fetch_emitted_after_create_refetch(monkeypatch: pytest.MonkeyPatch) -> None:
    task = plan_to_issues.PlannedTask(
        title="[P1][observability] test",
        body="Source planning issue: #113\nPlan ID: `plan-1`\n",
        priority="P1",
        labels=("planned-task",),
        plan_id="plan-1",
    )
    monkeypatch.setattr(plan_to_issues, "create_issue", lambda task, source_issue: "https://example.test/1")
    monkeypatch.setattr(
        plan_to_issues,
        "fetch_uploaded_issues",
        lambda source_issue, plan_ids, titles: [{"number": 1, "title": task.title, "url": "https://example.test/1"}],
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
    assert uploaded == [{"number": 1, "title": task.title, "url": "https://example.test/1"}]
    assert event["event"] == PLANNED_ISSUE_POST_CREATE_FETCH
    assert event["milestone"] == "v1.6.2"
    assert event["created_count"] == 1
    assert event["refetched_count"] == 1
    assert isinstance(event["latency_ms"], int)
    assert event["ok"] is True


def test_post_create_fetch_failure_still_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    task = plan_to_issues.PlannedTask(
        title="[P1][observability] test",
        body="Source planning issue: #113\nPlan ID: `plan-1`\n",
        priority="P1",
        labels=("planned-task",),
        plan_id="plan-1",
    )
    monkeypatch.setattr(plan_to_issues, "create_issue", lambda task, source_issue: "https://example.test/1")
    monkeypatch.setattr(plan_to_issues, "fetch_uploaded_issues", lambda source_issue, plan_ids, titles: [])
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
