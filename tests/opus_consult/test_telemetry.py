# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Opus planning hotline telemetry module."""

from __future__ import annotations

import io
import json

import pytest

from scripts.opus_consult.telemetry import compute_prompt_hash, emit_plan_consult_event
from scripts.observability.events import (
    AUTODEV_PLAN_CONSULT,
    EventValidationError,
    REQUIRED_FIELDS,
)


def test_compute_prompt_hash_returns_first_16_hex_chars() -> None:
    h = compute_prompt_hash("hello")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_prompt_hash_is_deterministic() -> None:
    assert compute_prompt_hash("same text") == compute_prompt_hash("same text")


def test_compute_prompt_hash_differs_for_different_inputs() -> None:
    assert compute_prompt_hash("text a") != compute_prompt_hash("text b")


def test_compute_prompt_hash_empty_string_returns_zeros() -> None:
    assert compute_prompt_hash("") == "0" * 16


def test_compute_prompt_hash_does_not_leak_prompt_body() -> None:
    secret = "super-secret-prompt-body-with-PAT-ghp_abc123"
    h = compute_prompt_hash(secret)
    assert secret not in h
    assert len(h) == 16


def test_emit_plan_consult_event_produces_valid_json_line(monkeypatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    emit_plan_consult_event(
        milestone="v1.6.0",
        plan_level="daily",
        anchor="v1.5.9",
        head_sha="a" * 40,
        duration_ms=1234,
        exit_code=0,
        fallback_used=False,
        prompt_hash="a1b2c3d4e5f6a7b8",
        plan_source="opus-live",
    )
    line = buf.getvalue().strip()
    payload = json.loads(line)
    assert payload["event"] == AUTODEV_PLAN_CONSULT


def test_emit_plan_consult_event_writes_valid_event(monkeypatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)

    emit_plan_consult_event(
        milestone="v1.6.0",
        plan_level="daily",
        anchor="v1.5.9",
        head_sha="a" * 40,
        duration_ms=1234,
        exit_code=0,
        fallback_used=False,
        prompt_hash="a1b2c3d4e5f6a7b8",
        plan_source="opus-live",
    )

    line = buf.getvalue().strip()
    payload = json.loads(line)
    assert payload["event"] == AUTODEV_PLAN_CONSULT
    assert payload["milestone"] == "v1.6.0"
    assert payload["plan_level"] == "daily"
    assert payload["anchor"] == "v1.5.9"
    assert payload["head_sha"] == "a" * 40
    assert payload["duration_ms"] == 1234
    assert payload["exit_code"] == 0
    assert payload["fallback_used"] is False
    assert payload["prompt_hash"] == "a1b2c3d4e5f6a7b8"
    assert payload["plan_source"] == "opus-live"


def test_emit_plan_consult_event_with_fallback(monkeypatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)

    emit_plan_consult_event(
        milestone="v1.6.0",
        plan_level="medium",
        anchor="v1.5.0",
        head_sha="b" * 40,
        duration_ms=5678,
        exit_code=1,
        fallback_used=True,
        prompt_hash="deadbeef12345678",
        plan_source="deterministic-template",
    )

    line = buf.getvalue().strip()
    payload = json.loads(line)
    assert payload["event"] == AUTODEV_PLAN_CONSULT
    assert payload["exit_code"] == 1
    assert payload["fallback_used"] is True
    assert payload["plan_source"] == "deterministic-template"


def test_autodev_plan_consult_is_registered_in_required_fields() -> None:
    """The event type must have a REQUIRED_FIELDS entry."""
    assert AUTODEV_PLAN_CONSULT in REQUIRED_FIELDS


def test_autodev_plan_consult_required_fields_are_complete() -> None:
    expected = {
        "event",
        "milestone",
        "plan_level",
        "anchor",
        "head_sha",
        "duration_ms",
        "exit_code",
        "fallback_used",
        "prompt_hash",
        "plan_source",
    }
    assert REQUIRED_FIELDS[AUTODEV_PLAN_CONSULT] == frozenset(expected)


def test_emit_plan_consult_event_rejects_missing_field() -> None:
    """Passing an invalid event should raise EventValidationError."""
    from scripts.observability.events import parse_event

    with pytest.raises(EventValidationError):
        parse_event(
            {
                "event": AUTODEV_PLAN_CONSULT,
                "milestone": "v1.6.0",
                # Missing plan_level, anchor, head_sha, duration_ms, etc.
            }
        )


def test_emit_plan_consult_event_rejects_wrong_type() -> None:
    from scripts.observability.events import parse_event

    payload = {
        "event": AUTODEV_PLAN_CONSULT,
        "milestone": "v1.6.0",
        "plan_level": "daily",
        "anchor": "v1.5.9",
        "head_sha": "a" * 40,
        "duration_ms": "not-an-int",  # wrong type
        "exit_code": 0,
        "fallback_used": False,
        "prompt_hash": "a1b2c3d4e5f6a7b8",
        "plan_source": "opus-live",
    }
    with pytest.raises(EventValidationError):
        parse_event(payload)


def test_smoke_script_runs_with_dry_run(monkeypatch) -> None:
    """Verify the smoke script runs cleanly with --dry-run."""
    from scripts.opus_consult import smoke

    exit_code = smoke.main(["--milestone", "v1.6.0", "--dry-run"])
    assert exit_code == 0


def test_smoke_script_refuses_without_dry_run(monkeypatch) -> None:
    from scripts.opus_consult import smoke

    with pytest.raises(SystemExit) as exc_info:
        smoke.main(["--milestone", "v1.6.0"])
    assert exc_info.value.code == 2
