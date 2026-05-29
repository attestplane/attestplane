# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Unit + conformance tests for replay_event payload + verifier (P1.1 / A.9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.event_payloads import (
    ReplayEventPayload,
    validate_replay_event_payload,
)
from attestplane.replay_verifier import (
    ReplayManifest,
    verify_replay_manifest,
)

_VECTORS_PATH = Path(__file__).resolve().parent / "conformance" / "replay_event_vectors.json"


def _load_vectors() -> dict:
    return json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))


def test_vectors_file_loads() -> None:
    v = _load_vectors()
    assert v["$schema_version"] == 1
    assert len(v["positive_vectors"]) == 4
    assert len(v["negative_vectors"]) == 10
    assert len(v["verifier_vectors"]) == 4


@pytest.mark.parametrize(
    "vec",
    _load_vectors()["positive_vectors"],
    ids=lambda v: v["name"],
)
def test_positive_payload_vectors(vec: dict) -> None:
    validate_replay_event_payload(vec["payload"])


@pytest.mark.parametrize(
    "vec",
    _load_vectors()["negative_vectors"],
    ids=lambda v: v["name"],
)
def test_negative_payload_vectors(vec: dict) -> None:
    with pytest.raises(ValueError) as excinfo:
        validate_replay_event_payload(vec["payload"])
    assert vec["expected_error_contains"] in str(excinfo.value), (
        f"{vec['name']!r}: expected reason containing {vec['expected_error_contains']!r}, got {excinfo.value!s}"
    )


def test_typed_dict_round_trip() -> None:
    p: ReplayEventPayload = {
        "replay_event_schema_version": 1,
        "replay_run_id": "replay-1",
        "original_run_id": "orig-1",
        "input_hash_match": True,
        "artifact_hash_match": True,
        "audit_chain_match": True,
        "deterministic_result": True,
        "observed_at": "2026-05-17T12:00:00.000000Z",
    }
    validate_replay_event_payload(p)


def test_and_cross_check_load_bearing() -> None:
    """The AND cross-check is the key invariant from AIOS ReplayProof spec."""
    # All true; AND = true; deterministic_result must be true.
    validate_replay_event_payload(
        {
            "replay_event_schema_version": 1,
            "replay_run_id": "x",
            "original_run_id": "y",
            "input_hash_match": True,
            "artifact_hash_match": True,
            "audit_chain_match": True,
            "deterministic_result": True,
            "observed_at": "2026-05-17T12:00:00.000000Z",
        }
    )
    # One false; AND = false; deterministic_result must be false.
    validate_replay_event_payload(
        {
            "replay_event_schema_version": 1,
            "replay_run_id": "x",
            "original_run_id": "y",
            "input_hash_match": True,
            "artifact_hash_match": False,
            "audit_chain_match": True,
            "deterministic_result": False,
            "observed_at": "2026-05-17T12:00:00.000000Z",
        }
    )


# --- Verifier (read-only walker) ---


@pytest.mark.parametrize(
    "vec",
    _load_vectors()["verifier_vectors"],
    ids=lambda v: v["name"],
)
def test_verifier_replay_manifest(vec: dict) -> None:
    manifest = ReplayManifest(
        replay_run_id=vec["manifest"]["replay_run_id"],
        original_run_id=vec["manifest"]["original_run_id"],
        expected_deterministic=vec["manifest"]["expected_deterministic"],
        snapshot_id_ref=vec["manifest"].get("snapshot_id_ref"),
    )
    result = verify_replay_manifest(vec["chain"], manifest)
    expected = vec["expected_result"]
    assert result.ok == expected["ok"]
    assert result.coverage == expected["coverage"]
    assert result.matching_seq == expected["matching_seq"]


def test_verifier_never_executes_replay() -> None:
    """Sanity: verifier is pure-functional, returns deterministic result.

    Calling twice with identical inputs returns identical outputs.
    (If the verifier had side effects, this could fail.)
    """
    chain: list[dict] = [
        {
            "seq": 0,
            "event_type": "replay_event",
            "payload": {
                "replay_event_schema_version": 1,
                "replay_run_id": "r1",
                "original_run_id": "o1",
                "input_hash_match": True,
                "artifact_hash_match": True,
                "audit_chain_match": True,
                "deterministic_result": True,
                "observed_at": "2026-05-17T12:00:00.000000Z",
            },
        },
    ]
    manifest = ReplayManifest(
        replay_run_id="r1",
        original_run_id="o1",
        expected_deterministic=True,
    )
    r1 = verify_replay_manifest(chain, manifest)
    r2 = verify_replay_manifest(chain, manifest)
    assert r1 == r2
    assert r1.ok is True


def test_verifier_handles_malformed_chain_gracefully() -> None:
    # Non-list chain
    result = verify_replay_manifest(
        "not a list",  # type: ignore[arg-type]
        ReplayManifest(replay_run_id="x", original_run_id="y", expected_deterministic=True),
    )
    assert result.ok is False
    assert "must be list" in (result.reason or "")


def test_verifier_picks_latest_seq() -> None:
    """When multiple replay_event entries match, the highest seq wins."""
    chain: list[dict] = [
        {
            "seq": 1,
            "event_type": "replay_event",
            "payload": {
                "replay_event_schema_version": 1,
                "replay_run_id": "r",
                "original_run_id": "o",
                "input_hash_match": True,
                "artifact_hash_match": False,
                "audit_chain_match": True,
                "deterministic_result": False,
                "observed_at": "2026-05-17T12:00:00.000000Z",
            },
        },
        {
            "seq": 7,
            "event_type": "replay_event",
            "payload": {
                "replay_event_schema_version": 1,
                "replay_run_id": "r",
                "original_run_id": "o",
                "input_hash_match": True,
                "artifact_hash_match": True,
                "audit_chain_match": True,
                "deterministic_result": True,
                "observed_at": "2026-05-17T12:01:00.000000Z",
            },
        },
    ]
    result = verify_replay_manifest(
        chain,
        ReplayManifest(replay_run_id="r", original_run_id="o", expected_deterministic=True),
    )
    assert result.ok is True
    assert result.matching_seq == 7
