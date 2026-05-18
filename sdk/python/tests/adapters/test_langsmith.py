# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :class:`attestplane.adapters.LangSmithAdapter`."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

from attestplane.adapters.base import AdapterTranslationError
from attestplane.adapters.langsmith import (
    LangSmithAdapter,
    LangSmithRun,
)
from attestplane.event_types import TOOL_CALL_EVENT
from attestplane.types import SubjectRef

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _hash(obj: object) -> str:
    encoded = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                         default=str, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_translates_tool_run() -> None:
    adapter = LangSmithAdapter()
    run = LangSmithRun(
        id="run-1",
        name="search_web",
        run_type="tool",
        start_time=_NOW,
        end_time=_NOW,
        inputs={"query": "weather in tokyo"},
        outputs={"result": "sunny, 22C"},
        trace_id="trace-abc",
    )

    draft = adapter.translate(run)

    assert draft.event_type == TOOL_CALL_EVENT
    assert draft.payload["kind"] == "tool"
    assert draft.payload["tool_name"] == "langsmith.tool.search_web"
    assert draft.payload["tool_call_id"] == "run-1"
    assert draft.payload["result_status"] == "OK"
    assert draft.payload["arguments_hash"] == _hash({"query": "weather in tokyo"})
    assert draft.payload["result_hash"] == _hash({"result": "sunny, 22C"})
    assert draft.session_id == "trace-abc"


def test_redacts_inputs_and_outputs() -> None:
    """The raw input/output strings MUST NOT appear in the payload."""
    adapter = LangSmithAdapter()
    redacted_value = "REDACTED_FOR_TEST"
    run = LangSmithRun(
        id="run-2", name="tool", run_type="tool",
        start_time=_NOW, end_time=_NOW,
        inputs={"sensitive": redacted_value},
        outputs={"sensitive_result": redacted_value},
    )
    draft = adapter.translate(run)

    payload_str = json.dumps(draft.payload)
    assert redacted_value not in payload_str
    # But the hashes are present.
    assert "arguments_hash" in draft.payload
    assert "result_hash" in draft.payload


def test_error_run_marks_status_error() -> None:
    adapter = LangSmithAdapter()
    run = LangSmithRun(
        id="run-3", name="tool", run_type="tool",
        start_time=_NOW, end_time=_NOW,
        inputs={},
        error="ToolExecutionError: timeout after 30s",
    )
    draft = adapter.translate(run)
    assert draft.payload["result_status"] == "ERROR"
    assert "timeout" in draft.payload["error_code"]


def test_long_error_truncated() -> None:
    adapter = LangSmithAdapter()
    run = LangSmithRun(
        id="run-4", name="tool", run_type="tool",
        start_time=_NOW, end_time=_NOW,
        inputs={},
        error="X" * 5000,
    )
    draft = adapter.translate(run)
    assert len(draft.payload["error_code"]) <= 200


def test_user_id_pseudonymized_via_subject_ref() -> None:
    adapter = LangSmithAdapter()
    run = LangSmithRun(
        id="run-5", name="tool", run_type="tool",
        start_time=_NOW, end_time=_NOW,
        inputs={},
        end_user_id="user_42",
    )
    draft = adapter.translate(run)
    assert draft.subject_ref == SubjectRef(scheme="opaque", value="user_42")


def test_unknown_run_type_marked_unknown() -> None:
    adapter = LangSmithAdapter()
    run = LangSmithRun(
        id="run-6", name="x", run_type="weirdcustomtype",
        start_time=_NOW, end_time=_NOW, inputs={},
    )
    draft = adapter.translate(run)
    assert draft.payload["kind"] == "unknown"


def test_latency_ms_populated_when_end_time_present() -> None:
    adapter = LangSmithAdapter()
    end = datetime(2026, 5, 17, 12, 0, 1, 500000, tzinfo=UTC)  # 1.5s later
    run = LangSmithRun(
        id="r", name="t", run_type="tool",
        start_time=_NOW, end_time=end, inputs={},
    )
    draft = adapter.translate(run)
    assert draft.payload["latency_ms"] == 1500


def test_session_id_falls_back_to_run_id_if_no_trace_id() -> None:
    adapter = LangSmithAdapter()
    run = LangSmithRun(
        id="solo-run", name="t", run_type="tool",
        start_time=_NOW, inputs={},
    )
    draft = adapter.translate(run)
    assert draft.session_id == "solo-run"


def test_parent_run_id_becomes_reference_db_ref() -> None:
    adapter = LangSmithAdapter()
    run = LangSmithRun(
        id="child", name="t", run_type="tool",
        start_time=_NOW, inputs={},
        parent_run_id="parent-1",
    )
    draft = adapter.translate(run)
    assert draft.reference_db_ref == "parent-1"


def test_rejects_non_langsmith_run() -> None:
    adapter = LangSmithAdapter()
    with pytest.raises(AdapterTranslationError, match="LangSmithRun"):
        adapter.translate("not a run")  # type: ignore[arg-type]


def test_pure_function_idempotent() -> None:
    adapter = LangSmithAdapter()
    run = LangSmithRun(
        id="x", name="t", run_type="tool",
        start_time=_NOW, end_time=_NOW, inputs={"a": 1},
    )
    a = adapter.translate(run)
    b = adapter.translate(run)
    assert a == b


# --- from_dict tests ---


def test_from_dict_minimal() -> None:
    run = LangSmithAdapter.from_dict({
        "id": "r1",
        "name": "tool_x",
        "run_type": "tool",
        "start_time": "2026-05-17T12:00:00Z",
    })
    assert run.id == "r1"
    assert run.start_time == _NOW


def test_from_dict_z_suffix_normalized() -> None:
    run = LangSmithAdapter.from_dict({
        "id": "r", "name": "t", "run_type": "tool",
        "start_time": "2026-05-17T12:00:00Z",
    })
    assert run.start_time.tzinfo is not None


def test_from_dict_missing_required_field() -> None:
    with pytest.raises(AdapterTranslationError, match="missing required"):
        LangSmithAdapter.from_dict({"id": "x", "name": "y"})


def test_from_dict_bad_datetime() -> None:
    with pytest.raises(AdapterTranslationError, match="unparsable"):
        LangSmithAdapter.from_dict({
            "id": "x", "name": "y", "run_type": "tool",
            "start_time": "not-a-date",
        })


def test_from_dict_extracts_user_id_from_metadata() -> None:
    run = LangSmithAdapter.from_dict({
        "id": "x", "name": "y", "run_type": "tool",
        "start_time": "2026-05-17T12:00:00Z",
        "metadata": {"user_id": "u-42"},
    })
    assert run.end_user_id == "u-42"


def test_runtime_name_locked() -> None:
    assert LangSmithAdapter.runtime_name == "langsmith"
    assert LangSmithAdapter.schema_version == 1
