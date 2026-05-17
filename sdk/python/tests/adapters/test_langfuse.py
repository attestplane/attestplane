# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :class:`attestplane.adapters.LangFuseAdapter`."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

from attestplane.adapters.base import AdapterTranslationError
from attestplane.adapters.langfuse import (
    LangFuseAdapter,
    LangFuseObservation,
)
from attestplane.event_types import TOOL_CALL_EVENT
from attestplane.types import SubjectRef

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _hash(obj: object) -> str:
    encoded = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                         default=str, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_translates_generation_observation() -> None:
    adapter = LangFuseAdapter()
    obs = LangFuseObservation(
        id="obs-1",
        trace_id="trace-1",
        type="GENERATION",
        name="completion",
        start_time=_NOW,
        end_time=_NOW,
        input={"prompt": "Hello"},
        output={"text": "Hi there"},
        model="gpt-4o-mini",
        level="DEFAULT",
        user_id="user-42",
    )
    draft = adapter.translate(obs)

    assert draft.event_type == TOOL_CALL_EVENT
    assert draft.payload["kind"] == "generation"
    assert draft.payload["tool_name"] == "langfuse.generation.completion"
    assert draft.payload["tool_call_id"] == "obs-1"
    assert draft.payload["tool_version"] == "gpt-4o-mini"
    assert draft.payload["arguments_hash"] == _hash({"prompt": "Hello"})
    assert draft.payload["result_hash"] == _hash({"text": "Hi there"})
    assert draft.payload["result_status"] == "OK"
    assert draft.session_id == "trace-1"
    assert draft.subject_ref == SubjectRef(scheme="opaque", value="user-42")


def test_translates_span_observation() -> None:
    adapter = LangFuseAdapter()
    obs = LangFuseObservation(
        id="span-1", trace_id="t-1", type="SPAN", name="agent_loop",
    )
    draft = adapter.translate(obs)
    assert draft.payload["kind"] == "span"


def test_translates_event_observation() -> None:
    adapter = LangFuseAdapter()
    obs = LangFuseObservation(
        id="ev-1", trace_id="t-1", type="EVENT", name="checkpoint",
    )
    draft = adapter.translate(obs)
    assert draft.payload["kind"] == "event"


def test_error_level_maps_to_error_status() -> None:
    adapter = LangFuseAdapter()
    obs = LangFuseObservation(
        id="o", trace_id="t", type="GENERATION", name="x",
        level="ERROR", status_message="rate limit exceeded",
    )
    draft = adapter.translate(obs)
    assert draft.payload["result_status"] == "ERROR"
    assert "rate limit" in draft.payload["error_code"]


def test_warning_level_maps_to_ok() -> None:
    adapter = LangFuseAdapter()
    obs = LangFuseObservation(
        id="o", trace_id="t", type="SPAN", name="x", level="WARNING",
    )
    draft = adapter.translate(obs)
    assert draft.payload["result_status"] == "OK"
    assert draft.payload.get("level") == "WARNING"


def test_redacts_raw_input_output() -> None:
    """Raw input/output MUST NOT appear in the payload — only hashes."""
    adapter = LangFuseAdapter()
    secret = "Bearer sk-token-abc123"
    obs = LangFuseObservation(
        id="o", trace_id="t", type="GENERATION", name="x",
        input={"headers": secret},
        output={"text": secret},
    )
    draft = adapter.translate(obs)
    payload_str = json.dumps(draft.payload)
    assert secret not in payload_str
    assert "arguments_hash" in draft.payload
    assert "result_hash" in draft.payload


def test_null_input_still_emits_hash() -> None:
    """Even when input is None, arguments_hash is present (= hash of {})."""
    adapter = LangFuseAdapter()
    obs = LangFuseObservation(
        id="o", trace_id="t", type="GENERATION", name="x", input=None,
    )
    draft = adapter.translate(obs)
    assert draft.payload["arguments_hash"] == _hash({})


def test_unknown_type_marked_unknown() -> None:
    adapter = LangFuseAdapter()
    obs = LangFuseObservation(
        id="o", trace_id="t", type="WEIRDTYPE", name="x",
    )
    draft = adapter.translate(obs)
    assert draft.payload["kind"] == "unknown"


def test_latency_ms_populated() -> None:
    adapter = LangFuseAdapter()
    end = datetime(2026, 5, 17, 12, 0, 2, 500000, tzinfo=UTC)
    obs = LangFuseObservation(
        id="o", trace_id="t", type="GENERATION", name="x",
        start_time=_NOW, end_time=end,
    )
    draft = adapter.translate(obs)
    assert draft.payload["latency_ms"] == 2500


def test_user_id_subject_ref() -> None:
    adapter = LangFuseAdapter()
    obs = LangFuseObservation(
        id="o", trace_id="t", type="GENERATION", name="x",
        user_id="alice",
    )
    draft = adapter.translate(obs)
    assert draft.subject_ref == SubjectRef(scheme="opaque", value="alice")


def test_no_user_id_no_subject_ref() -> None:
    adapter = LangFuseAdapter()
    obs = LangFuseObservation(
        id="o", trace_id="t", type="GENERATION", name="x",
    )
    draft = adapter.translate(obs)
    assert draft.subject_ref is None


def test_rejects_non_observation() -> None:
    adapter = LangFuseAdapter()
    with pytest.raises(AdapterTranslationError, match="LangFuseObservation"):
        adapter.translate({"id": "o"})  # type: ignore[arg-type]


def test_pure_function_idempotent() -> None:
    adapter = LangFuseAdapter()
    obs = LangFuseObservation(
        id="o", trace_id="t", type="GENERATION", name="x",
        start_time=_NOW, end_time=_NOW, input={"a": 1},
    )
    assert adapter.translate(obs) == adapter.translate(obs)


# --- from_dict tests ---


def test_from_dict_minimal() -> None:
    obs = LangFuseAdapter.from_dict({
        "id": "o-1", "trace_id": "t-1", "type": "GENERATION",
    })
    assert obs.id == "o-1"
    assert obs.trace_id == "t-1"
    assert obs.type == "GENERATION"


def test_from_dict_with_user_id_kwarg() -> None:
    obs = LangFuseAdapter.from_dict(
        {"id": "o", "trace_id": "t", "type": "GENERATION"},
        user_id="trace-user",
    )
    assert obs.user_id == "trace-user"


def test_from_dict_missing_required() -> None:
    with pytest.raises(AdapterTranslationError, match="missing required"):
        LangFuseAdapter.from_dict({"id": "x"})


def test_from_dict_parses_iso_datetime() -> None:
    obs = LangFuseAdapter.from_dict({
        "id": "o", "trace_id": "t", "type": "GENERATION",
        "start_time": "2026-05-17T12:00:00Z",
        "end_time": "2026-05-17T12:00:01Z",
    })
    assert obs.start_time == _NOW
    assert obs.end_time == datetime(2026, 5, 17, 12, 0, 1, tzinfo=UTC)


def test_from_dict_bad_metadata_type() -> None:
    with pytest.raises(AdapterTranslationError, match="metadata"):
        LangFuseAdapter.from_dict({
            "id": "o", "trace_id": "t", "type": "GENERATION",
            "metadata": "not a dict",
        })


def test_runtime_name_locked() -> None:
    assert LangFuseAdapter.runtime_name == "langfuse"
    assert LangFuseAdapter.schema_version == 1
