# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Negative conformance tests — five frozen broken chains.

Each fixture in ``tests/conformance/negative/`` is a chain that MUST fail
``verify_chain`` with a specific ``first_bad_index`` and a specific
substring in the human-readable reason. Together they pin attestation
gates A2 and A3 from ``docs/architecture/ATTESTATION_GATES.md``.

If any of these tests start passing (i.e., ``verify_chain`` returns
``ok=True`` on a known-broken fixture) the verifier has regressed in a
way that admits tampered chains. Block release immediately.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from attestplane.hashchain import verify_chain
from attestplane.types import AuditEvent, ChainedEvent, SubjectRef

_NEGATIVE_DIR = Path(__file__).parent / "conformance" / "negative"

_FIXTURE_NAMES = [
    "broken_chain",
    "missing_event",
    "reordered_event",
    "duplicate_event",
    "malformed_payload",
]


def _load_fixture(name: str) -> dict[str, Any]:
    path = _NEGATIVE_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _make_subject(raw: dict[str, Any] | None) -> SubjectRef | None:
    if raw is None:
        return None
    return SubjectRef(scheme=raw["scheme"], value=raw["value"])


def _rehydrate(events_raw: list[dict[str, Any]]) -> list[ChainedEvent]:
    chained: list[ChainedEvent] = []
    for ev_raw in events_raw:
        e = ev_raw["event"]
        ts = datetime.strptime(e["timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(UTC)
        audit_event = AuditEvent(
            schema_version=e["schema_version"],
            event_id=e["event_id"],
            timestamp=ts,
            event_type=e["event_type"],
            actor=e["actor"],
            payload=e["payload"],
            subject_ref=_make_subject(e.get("subject_ref")),
            session_id=e.get("session_id"),
            reference_db_ref=e.get("reference_db_ref"),
            matched_input_ref=e.get("matched_input_ref"),
            human_verifier=_make_subject(e.get("human_verifier")),
        )
        chained.append(
            ChainedEvent(
                seq=ev_raw["seq"],
                prev_hash=bytes.fromhex(ev_raw["prev_hash_hex"]),
                event_hash=bytes.fromhex(ev_raw["event_hash_hex"]),
                event=audit_event,
            )
        )
    return chained


def test_five_negative_fixtures_exist() -> None:
    """All five files listed in the migration plan ticket #16 are present."""
    for name in _FIXTURE_NAMES:
        assert (_NEGATIVE_DIR / f"{name}.json").exists(), name


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_verify_chain_rejects_negative_fixture(fixture_name: str) -> None:
    fixture = _load_fixture(fixture_name)
    chain = _rehydrate(fixture["events"])

    result = verify_chain(chain)

    expected = fixture["expected_failure"]
    assert result.ok is expected["ok"], (
        f"{fixture_name}: expected ok={expected['ok']}, got ok={result.ok}, reason={result.reason!r}"
    )
    assert result.first_bad_index == expected["first_bad_index"], (
        f"{fixture_name}: first_bad_index={result.first_bad_index}, expected {expected['first_bad_index']}"
    )
    assert expected["reason_substring"] in (result.reason or ""), (
        f"{fixture_name}: reason {result.reason!r} does not contain {expected['reason_substring']!r}"
    )


def test_broken_chain_specifically_detects_prev_hash() -> None:
    """Cross-check: the broken_chain fixture must fail on prev_hash, not on seq."""
    result = verify_chain(_rehydrate(_load_fixture("broken_chain")["events"]))
    assert not result.ok
    assert result.first_bad_index == 1
    assert "prev_hash" in (result.reason or "")


def test_malformed_payload_specifically_detects_event_hash() -> None:
    """Cross-check: tampered payload must produce event_hash mismatch (gate A2)."""
    result = verify_chain(_rehydrate(_load_fixture("malformed_payload")["events"]))
    assert not result.ok
    assert result.first_bad_index == 1
    assert "event_hash" in (result.reason or "")


def test_negative_fixtures_have_schema_version_one() -> None:
    """Negative fixtures pin against the frozen schema_version=1 contract."""
    for name in _FIXTURE_NAMES:
        fixture = _load_fixture(name)
        assert fixture["schema_version"] == 1, name
        for ev in fixture["events"]:
            assert ev["event"]["schema_version"] == 1, (name, ev["seq"])


def test_negative_fixtures_are_distinct_failure_modes() -> None:
    """The five fixtures cover five distinct failure modes; no two have the
    same (first_bad_index, reason_substring) pair AND the same name."""
    seen: set[tuple[int, str, str]] = set()
    for name in _FIXTURE_NAMES:
        fixture = _load_fixture(name)
        key = (
            fixture["expected_failure"]["first_bad_index"],
            fixture["expected_failure"]["reason_substring"],
            name,
        )
        assert key not in seen, key
        seen.add(key)
