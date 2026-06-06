# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-completion tests for attestplane.replay_verifier (target ≥98%)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from attestplane.replay_verifier import (
    ReplayManifest,
    verify_replay_manifest,
)


def _good_payload(
    replay_run_id: str = "r1",
    original_run_id: str = "o1",
    deterministic: bool = True,
    snapshot_id_ref: str | None = None,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "replay_event_schema_version": 1,
        "replay_run_id": replay_run_id,
        "original_run_id": original_run_id,
        "input_hash_match": deterministic,
        "artifact_hash_match": deterministic,
        "audit_chain_match": deterministic,
        "deterministic_result": deterministic,
        "observed_at": "2026-05-17T12:00:00.000000Z",
    }
    if snapshot_id_ref is not None:
        p["snapshot_id_ref"] = snapshot_id_ref
    return p


def _good_event(
    seq: int = 0,
    replay_run_id: str = "r1",
    original_run_id: str = "o1",
    deterministic: bool = True,
    snapshot_id_ref: str | None = None,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "event_type": "replay_event",
        "payload": _good_payload(
            replay_run_id=replay_run_id,
            original_run_id=original_run_id,
            deterministic=deterministic,
            snapshot_id_ref=snapshot_id_ref,
        ),
    }


# ── line 111: naive (no tzinfo) verification_time ────────────────────────────

def test_naive_verification_time_rejected() -> None:
    result = verify_replay_manifest(
        [_good_event()],
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
        verification_time=datetime(2026, 5, 17, 12, 0, 0),  # naive — no tzinfo
    )
    assert result.ok is False
    assert "UTC-aware" in (result.reason or "")


def test_aware_verification_time_accepted() -> None:
    # Ensure the UTC-aware path does NOT fail on that guard (line 110 branch)
    result = verify_replay_manifest(
        [_good_event()],
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
        verification_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC),
    )
    assert result.ok is True


# ── line 121: non-dict chain element is skipped ──────────────────────────────

def test_non_dict_chain_element_skipped() -> None:
    # line 121: non-dict element continues (skip), but if no candidates found…
    chain: list[Any] = ["not_a_dict", _good_event()]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    # The good event is still found despite the non-dict element
    assert result.ok is True


def test_all_non_dict_elements_no_candidates() -> None:
    # Ensures the non-dict skip path is hit and no candidates → no_replay_event
    chain_mixed: list[Any] = ["a", 42, None]
    result = verify_replay_manifest(
        chain_mixed,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is False
    assert result.coverage == "no_replay_event"


# ── line 126: event_type != replay_event skipped ─────────────────────────────

def test_non_replay_event_type_skipped() -> None:
    chain = [
        {"seq": 0, "event_type": "other_event", "payload": {"replay_run_id": "r1"}},
        _good_event(),
    ]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is True


# ── line 128: payload not a dict skipped ─────────────────────────────────────

def test_non_dict_payload_skipped() -> None:
    chain = [
        {"seq": 0, "event_type": "replay_event", "payload": "not_a_dict"},
        _good_event(seq=1),
    ]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is True


def test_none_payload_skipped() -> None:
    chain = [
        {"seq": 0, "event_type": "replay_event", "payload": None},
        _good_event(seq=1),
    ]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is True


# ── line 130: replay_run_id mismatch skipped ─────────────────────────────────

def test_replay_run_id_mismatch_skipped() -> None:
    chain = [
        _good_event(replay_run_id="other_run"),
        _good_event(seq=1, replay_run_id="r1"),
    ]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is True
    assert result.matching_seq == 1


def test_replay_run_id_mismatch_only_no_candidates() -> None:
    chain = [_good_event(replay_run_id="other")]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is False
    assert result.coverage == "no_replay_event"


# ── line 132: original_run_id mismatch skipped ───────────────────────────────

def test_original_run_id_mismatch_skipped() -> None:
    chain = [
        _good_event(original_run_id="wrong_orig"),
        _good_event(seq=1, original_run_id="o1"),
    ]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is True
    assert result.matching_seq == 1


# ── line 135: seq not an int skipped ─────────────────────────────────────────

def test_non_int_seq_skipped() -> None:
    chain = [
        {"seq": "not_int", "event_type": "replay_event", "payload": _good_payload()},
        _good_event(seq=5),
    ]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is True
    assert result.matching_seq == 5


def test_missing_seq_skipped() -> None:
    chain = [
        {"event_type": "replay_event", "payload": _good_payload()},  # no seq key
        _good_event(seq=3),
    ]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is True
    assert result.matching_seq == 3


# ── lines 157-158: matching payload fails validate_replay_event_payload ──────

def test_invalid_payload_internal_consistency_fails() -> None:
    # AND cross-check broken: input_hash_match=True, artifact=True, chain=True
    # but deterministic_result=False → validate_replay_event_payload raises
    bad_payload = {
        "replay_event_schema_version": 1,
        "replay_run_id": "r1",
        "original_run_id": "o1",
        "input_hash_match": True,
        "artifact_hash_match": True,
        "audit_chain_match": True,
        "deterministic_result": False,  # contradicts AND of True, True, True
        "observed_at": "2026-05-17T12:00:00.000000Z",
    }
    chain = [{"seq": 0, "event_type": "replay_event", "payload": bad_payload}]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=False),
    )
    assert result.ok is False
    assert "failed validation" in (result.reason or "")
    assert result.coverage == "no_replay_event"


# ── snapshot_id_ref mismatch branch (line 132 alternate) ─────────────────────

def test_snapshot_id_ref_mismatch_skipped() -> None:
    chain = [
        _good_event(snapshot_id_ref="snap-wrong"),
        _good_event(seq=1, snapshot_id_ref="snap-correct"),
    ]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(
            replay_run_id="r1",
            original_run_id="o1",
            expected_deterministic=True,
            snapshot_id_ref="snap-correct",
        ),
    )
    assert result.ok is True
    assert result.matching_seq == 1


def test_snapshot_id_ref_none_matches_any() -> None:
    # manifest has no snapshot_id_ref → any candidate matches regardless
    chain = [_good_event(snapshot_id_ref="snap-x")]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is True


# ── non_deterministic result branch (line 169) ───────────────────────────────

def test_expected_deterministic_true_but_chain_false() -> None:
    chain = [_good_event(deterministic=False)]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is False
    assert result.coverage == "non_deterministic"
    assert result.matching_seq == 0


def test_expected_deterministic_false_but_chain_true() -> None:
    chain = [_good_event(deterministic=True)]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=False),
    )
    assert result.ok is False
    assert result.coverage == "deterministic"
    assert result.matching_seq == 0


def test_non_deterministic_match_ok() -> None:
    chain = [_good_event(deterministic=False)]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=False),
    )
    assert result.ok is True
    assert result.coverage == "non_deterministic"


# ── line 104: chain_events not a list (type: ignore[unreachable]) ─────────────

def test_chain_events_dict_not_list_fails() -> None:
    # line 103-109: isinstance check - pass a dict (not a list)
    result = verify_replay_manifest(
        {"key": "value"},  # type: ignore[arg-type]
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is False
    assert "must be list" in (result.reason or "")
    assert result.coverage == "no_replay_event"


def test_chain_events_int_not_list_fails() -> None:
    result = verify_replay_manifest(
        42,  # type: ignore[arg-type]
        ReplayManifest(replay_run_id="r1", original_run_id="o1", expected_deterministic=True),
    )
    assert result.ok is False
    assert "must be list" in (result.reason or "")
