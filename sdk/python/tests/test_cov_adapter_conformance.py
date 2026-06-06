# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-gap tests for attestplane.adapter_conformance.

Targets missing lines: 101-102, 105, 109, 113, 115, 118, 122, 125, 130, 132, 134, 174.
These are all error-path branches inside _load_and_validate_fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from attestplane.adapter_conformance import (
    AdapterConformanceError,
    replay_fixture,
)


def _write_fixture(tmp_path: Path, data: Any, filename: str = "fixture.json") -> Path:
    p = tmp_path / filename
    if isinstance(data, str):
        p.write_text(data, encoding="utf-8")
    else:
        p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _load_and_validate_fixture error paths
# ---------------------------------------------------------------------------


def test_load_file_not_found(tmp_path: Path) -> None:
    """Line 101-102: OSError from path.read_text → AdapterConformanceError."""
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(AdapterConformanceError, match="cannot load fixture"):
        replay_fixture(missing, object())


def test_load_invalid_json(tmp_path: Path) -> None:
    """Line 101-102: json.JSONDecodeError → AdapterConformanceError."""
    p = _write_fixture(tmp_path, "not valid json {{{")
    with pytest.raises(AdapterConformanceError, match="cannot load fixture"):
        replay_fixture(p, object())


def test_load_top_level_not_dict(tmp_path: Path) -> None:
    """Line 105: top-level is list, not object."""
    p = _write_fixture(tmp_path, [1, 2, 3])
    with pytest.raises(AdapterConformanceError, match="top level must be object"):
        replay_fixture(p, object())


def test_load_wrong_schema_version(tmp_path: Path) -> None:
    """Line 107: $schema_version != 1."""
    p = _write_fixture(tmp_path, {"$schema_version": 2, "fixture_kind": "adapter_conformance"})
    with pytest.raises(AdapterConformanceError, match="\\$schema_version"):
        replay_fixture(p, object())


def test_load_wrong_fixture_kind(tmp_path: Path) -> None:
    """Line 109: fixture_kind != 'adapter_conformance'."""
    p = _write_fixture(tmp_path, {"$schema_version": 1, "fixture_kind": "other"})
    with pytest.raises(AdapterConformanceError, match="fixture_kind"):
        replay_fixture(p, object())


def test_load_empty_runtime_kind(tmp_path: Path) -> None:
    """Line 113: runtime_kind empty string."""
    p = _write_fixture(
        tmp_path,
        {
            "$schema_version": 1,
            "fixture_kind": "adapter_conformance",
            "runtime_kind": "",
        },
    )
    with pytest.raises(AdapterConformanceError, match="runtime_kind"):
        replay_fixture(p, object())


def test_load_non_string_runtime_kind(tmp_path: Path) -> None:
    """Line 113: runtime_kind is an int."""
    p = _write_fixture(
        tmp_path,
        {
            "$schema_version": 1,
            "fixture_kind": "adapter_conformance",
            "runtime_kind": 42,
        },
    )
    with pytest.raises(AdapterConformanceError, match="runtime_kind"):
        replay_fixture(p, object())


def test_load_fixture_version_zero(tmp_path: Path) -> None:
    """Line 115: fixture_version < 1."""
    p = _write_fixture(
        tmp_path,
        {
            "$schema_version": 1,
            "fixture_kind": "adapter_conformance",
            "runtime_kind": "test",
            "fixture_version": 0,
        },
    )
    with pytest.raises(AdapterConformanceError, match="fixture_version"):
        replay_fixture(p, object())


def test_load_fixture_version_not_int(tmp_path: Path) -> None:
    """Line 115: fixture_version is a string."""
    p = _write_fixture(
        tmp_path,
        {
            "$schema_version": 1,
            "fixture_kind": "adapter_conformance",
            "runtime_kind": "test",
            "fixture_version": "1",
        },
    )
    with pytest.raises(AdapterConformanceError, match="fixture_version"):
        replay_fixture(p, object())


def test_load_empty_cases_list(tmp_path: Path) -> None:
    """Line 118: cases is empty list."""
    p = _write_fixture(
        tmp_path,
        {
            "$schema_version": 1,
            "fixture_kind": "adapter_conformance",
            "runtime_kind": "test",
            "fixture_version": 1,
            "cases": [],
        },
    )
    with pytest.raises(AdapterConformanceError, match="cases must be non-empty"):
        replay_fixture(p, object())


def test_load_cases_not_list(tmp_path: Path) -> None:
    """Line 118: cases is not a list."""
    p = _write_fixture(
        tmp_path,
        {
            "$schema_version": 1,
            "fixture_kind": "adapter_conformance",
            "runtime_kind": "test",
            "fixture_version": 1,
            "cases": "not-a-list",
        },
    )
    with pytest.raises(AdapterConformanceError, match="cases must be non-empty"):
        replay_fixture(p, object())


def _base_fixture(cases: list[Any]) -> dict[str, Any]:
    return {
        "$schema_version": 1,
        "fixture_kind": "adapter_conformance",
        "runtime_kind": "test",
        "fixture_version": 1,
        "cases": cases,
    }


def test_load_case_not_dict(tmp_path: Path) -> None:
    """Line 122: cases[i] is not a dict."""
    p = _write_fixture(tmp_path, _base_fixture(["not-a-dict"]))
    with pytest.raises(AdapterConformanceError, match="must be object"):
        replay_fixture(p, object())


def test_load_case_name_empty(tmp_path: Path) -> None:
    """Line 125: cases[i].name is empty string."""
    p = _write_fixture(tmp_path, _base_fixture([{"name": ""}]))
    with pytest.raises(AdapterConformanceError, match="name must be non-empty"):
        replay_fixture(p, object())


def test_load_case_name_missing(tmp_path: Path) -> None:
    """Line 125: cases[i] missing name key."""
    p = _write_fixture(tmp_path, _base_fixture([{"not_name": "x"}]))
    with pytest.raises(AdapterConformanceError, match="name must be non-empty"):
        replay_fixture(p, object())


def test_load_duplicate_case_names(tmp_path: Path) -> None:
    """Line ~127: duplicate case name."""
    case = {
        "name": "dup",
        "runtime_event_input": {},
        "expected_event_draft": {
            "event_type": "t",
            "actor": "a",
            "payload": {},
            "subject_ref": None,
            "session_id": None,
            "reference_db_ref": None,
            "matched_input_ref": None,
            "human_verifier": None,
        },
    }
    p = _write_fixture(tmp_path, _base_fixture([case, dict(case)]))
    with pytest.raises(AdapterConformanceError, match="duplicate case name"):
        replay_fixture(p, object())


def test_load_missing_runtime_event_input(tmp_path: Path) -> None:
    """Line 130: cases[i] missing runtime_event_input."""
    case = {
        "name": "c1",
        "expected_event_draft": {"event_type": "t", "actor": "a", "payload": {}},
    }
    p = _write_fixture(tmp_path, _base_fixture([case]))
    with pytest.raises(AdapterConformanceError, match="runtime_event_input"):
        replay_fixture(p, object())


def test_load_missing_expected_event_draft(tmp_path: Path) -> None:
    """Line 132: cases[i] missing expected_event_draft."""
    case = {
        "name": "c1",
        "runtime_event_input": {},
    }
    p = _write_fixture(tmp_path, _base_fixture([case]))
    with pytest.raises(AdapterConformanceError, match="expected_event_draft"):
        replay_fixture(p, object())


def test_load_expected_event_draft_not_dict(tmp_path: Path) -> None:
    """Line 134: cases[i].expected_event_draft is not dict."""
    case = {
        "name": "c1",
        "runtime_event_input": {},
        "expected_event_draft": "should-be-dict",
    }
    p = _write_fixture(tmp_path, _base_fixture([case]))
    with pytest.raises(AdapterConformanceError, match="must be object"):
        replay_fixture(p, object())


# ---------------------------------------------------------------------------
# replay_fixture line 174: pre_translate path (exception inside pre_translate)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# replay_fixture happy path — lines 189-212 (successful translate + match/mismatch)
# ---------------------------------------------------------------------------


class _ConstantAdapter:
    """Always returns a fixed EventDraft (useful for hash-match and hash-mismatch tests)."""

    def __init__(self, event_type: str = "tool_call_event", actor: str = "test-actor") -> None:
        self._event_type = event_type
        self._actor = actor

    def translate(self, ev: Any) -> Any:
        from attestplane.types import EventDraft

        return EventDraft(event_type=self._event_type, actor=self._actor, payload={})


def _make_expected_for(event_type: str, actor: str) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "actor": actor,
        "payload": {},
        "subject_ref": None,
        "session_id": None,
        "reference_db_ref": None,
        "matched_input_ref": None,
        "human_verifier": None,
    }


def test_replay_fixture_successful_match(tmp_path: Path) -> None:
    """Lines 191-201: adapter output matches expected → ok=True."""
    case = {
        "name": "match_case",
        "runtime_event_input": {},
        "expected_event_draft": _make_expected_for("tool_call_event", "test-actor"),
    }
    p = _write_fixture(tmp_path, _base_fixture([case]))
    report = replay_fixture(p, _ConstantAdapter())
    assert report.ok
    assert report.cases_passed == 1
    assert report.cases_failed == 0
    assert report.results[0].ok is True
    assert report.results[0].reason is None


def test_replay_fixture_hash_mismatch_recorded(tmp_path: Path) -> None:
    """Lines 202-211: adapter output does NOT match expected → ok=False with reason."""
    case = {
        "name": "mismatch_case",
        "runtime_event_input": {},
        "expected_event_draft": _make_expected_for("WRONG_TYPE", "WRONG_ACTOR"),
    }
    p = _write_fixture(tmp_path, _base_fixture([case]))
    report = replay_fixture(p, _ConstantAdapter())  # returns tool_call_event/test-actor
    assert not report.ok
    assert report.cases_failed == 1
    assert "canonical-bytes mismatch" in (report.results[0].reason or "")


def test_replay_fixture_with_subject_ref_in_expected(tmp_path: Path) -> None:
    """Lines 65-70: _subjectref_to_dict with non-None SubjectRef.

    The adapter returns a draft with subject_ref; the expected dict has the
    same scheme+value so hashes match.
    """

    class _SubjectRefAdapter:
        def translate(self, ev: Any) -> Any:
            from attestplane.types import EventDraft, SubjectRef

            return EventDraft(
                event_type="tool_call_event",
                actor="a",
                payload={},
                subject_ref=SubjectRef(scheme="opaque", value="u1"),
            )

    expected = {
        "event_type": "tool_call_event",
        "actor": "a",
        "payload": {},
        "subject_ref": {"scheme": "opaque", "value": "u1"},
        "session_id": None,
        "reference_db_ref": None,
        "matched_input_ref": None,
        "human_verifier": None,
    }
    case = {"name": "subject_ref_case", "runtime_event_input": {}, "expected_event_draft": expected}
    p = _write_fixture(tmp_path, _base_fixture([case]))
    report = replay_fixture(p, _SubjectRefAdapter())
    assert report.ok, f"subject_ref case failed: {report.results}"


def test_replay_fixture_pre_translate_raises_recorded_as_failure(tmp_path: Path) -> None:
    """Line 174: pre_translate raises → AdapterCaseResult with ok=False."""

    def bad_pre_translate(raw: dict[str, Any]) -> Any:
        raise ValueError("pre_translate boom")

    class _DummyAdapter:
        def translate(self, ev: Any) -> Any:
            from attestplane.types import EventDraft
            return EventDraft(event_type="tool_call_event", actor="a", payload={})

    good_expected = {
        "event_type": "tool_call_event",
        "actor": "a",
        "payload": {},
        "subject_ref": None,
        "session_id": None,
        "reference_db_ref": None,
        "matched_input_ref": None,
        "human_verifier": None,
    }
    case = {
        "name": "pre_translate_fail",
        "runtime_event_input": {"x": 1},
        "expected_event_draft": good_expected,
    }
    p = _write_fixture(tmp_path, _base_fixture([case]))
    report = replay_fixture(p, _DummyAdapter(), pre_translate=bad_pre_translate)
    assert not report.ok
    assert report.cases_failed == 1
    result = report.results[0]
    assert "pre_translate boom" in (result.reason or "")
