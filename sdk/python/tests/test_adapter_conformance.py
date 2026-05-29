# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Replayer + reference-fixture tests (ADR-0014 / P2.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.adapter_conformance import (
    AdapterConformanceError,
    replay_fixture,
)
from attestplane.adapters.langfuse import LangFuseAdapter
from attestplane.adapters.langsmith import LangSmithAdapter

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "adapter_conformance"


def test_fixtures_directory_exists() -> None:
    assert _FIXTURES_DIR.is_dir()


def test_langsmith_v1_fixture_passes_replay() -> None:
    fixture = _FIXTURES_DIR / "langsmith_v1.json"
    adapter = LangSmithAdapter()
    report = replay_fixture(fixture, adapter, pre_translate=LangSmithAdapter.from_dict)
    assert report.ok, f"LangSmith fixture FAILED: {[r for r in report.results if not r.ok]}"
    assert report.runtime_kind == "langsmith"
    assert report.fixture_version == 1
    assert report.cases_total == 2
    assert report.cases_passed == 2
    assert report.cases_failed == 0


def test_langfuse_v1_fixture_passes_replay() -> None:
    fixture = _FIXTURES_DIR / "langfuse_v1.json"
    adapter = LangFuseAdapter()
    report = replay_fixture(fixture, adapter, pre_translate=LangFuseAdapter.from_dict)
    assert report.ok, f"LangFuse fixture FAILED: {[r for r in report.results if not r.ok]}"
    assert report.runtime_kind == "langfuse"
    assert report.cases_total == 2


def test_replayer_reports_byte_mismatch() -> None:
    """If a fixture's expected_event_draft is wrong, replayer surfaces hash mismatch."""
    # Construct a fixture with deliberately wrong expected output.
    bad_fixture = {
        "$schema_version": 1,
        "fixture_kind": "adapter_conformance",
        "runtime_kind": "langsmith",
        "fixture_version": 1,
        "cases": [
            {
                "name": "intentional_mismatch",
                "runtime_event_input": {
                    "id": "33333333-3333-7000-8000-000000000003",
                    "name": "x",
                    "run_type": "tool",
                    "start_time": "2026-05-17T12:00:00.000000+00:00",
                },
                "expected_event_draft": {
                    "event_type": "WRONG_TYPE",
                    "actor": "WRONG",
                    "payload": {},
                    "subject_ref": None,
                    "session_id": None,
                    "reference_db_ref": None,
                    "matched_input_ref": None,
                    "human_verifier": None,
                },
            },
        ],
    }
    bad_path = _FIXTURES_DIR / "_tmp_bad_fixture.json"
    bad_path.write_text(json.dumps(bad_fixture))
    try:
        report = replay_fixture(
            bad_path,
            LangSmithAdapter(),
            pre_translate=LangSmithAdapter.from_dict,
        )
        assert not report.ok
        assert report.cases_failed == 1
        assert "canonical-bytes mismatch" in (report.results[0].reason or "")
    finally:
        bad_path.unlink(missing_ok=True)


def test_replayer_reports_adapter_raise() -> None:
    """If adapter.translate() raises, replayer records the failure."""
    fixture = {
        "$schema_version": 1,
        "fixture_kind": "adapter_conformance",
        "runtime_kind": "langsmith",
        "fixture_version": 1,
        "cases": [
            {
                "name": "malformed_input",
                "runtime_event_input": {},  # missing required fields → from_dict raises
                "expected_event_draft": {
                    "event_type": "tool_call_event",
                    "actor": "x",
                    "payload": {},
                    "subject_ref": None,
                    "session_id": None,
                    "reference_db_ref": None,
                    "matched_input_ref": None,
                    "human_verifier": None,
                },
            },
        ],
    }
    path = _FIXTURES_DIR / "_tmp_raise.json"
    path.write_text(json.dumps(fixture))
    try:
        report = replay_fixture(
            path,
            LangSmithAdapter(),
            pre_translate=LangSmithAdapter.from_dict,
        )
        assert not report.ok
        assert "adapter raised" in (report.results[0].reason or "")
    finally:
        path.unlink(missing_ok=True)


def test_replayer_validates_fixture_shape() -> None:
    """Malformed fixtures raise AdapterConformanceError immediately."""
    path = _FIXTURES_DIR / "_tmp_malformed.json"
    path.write_text('{"not_a_fixture": true}')
    try:
        with pytest.raises(AdapterConformanceError, match="\\$schema_version"):
            replay_fixture(path, LangSmithAdapter())
    finally:
        path.unlink(missing_ok=True)


def test_replayer_rejects_duplicate_case_names() -> None:
    fixture = {
        "$schema_version": 1,
        "fixture_kind": "adapter_conformance",
        "runtime_kind": "langsmith",
        "fixture_version": 1,
        "cases": [
            {
                "name": "dup",
                "runtime_event_input": {},
                "expected_event_draft": {},
            },
            {
                "name": "dup",
                "runtime_event_input": {},
                "expected_event_draft": {},
            },
        ],
    }
    path = _FIXTURES_DIR / "_tmp_dup.json"
    path.write_text(json.dumps(fixture))
    try:
        with pytest.raises(AdapterConformanceError, match="duplicate"):
            replay_fixture(path, LangSmithAdapter())
    finally:
        path.unlink(missing_ok=True)


def test_replayer_is_pure() -> None:
    """Same fixture + adapter → same report shape."""
    fixture = _FIXTURES_DIR / "langsmith_v1.json"
    r1 = replay_fixture(fixture, LangSmithAdapter(), pre_translate=LangSmithAdapter.from_dict)
    r2 = replay_fixture(fixture, LangSmithAdapter(), pre_translate=LangSmithAdapter.from_dict)
    assert r1 == r2
