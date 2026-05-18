# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Settlement-precondition verifier tests (ADR-0009 § B.3 + P2.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.settlement_verifier import (
    SettlementPreconditionClaim,
    check_settlement_precondition,
)

_VECTORS_PATH = (
    Path(__file__).resolve().parent
    / "conformance"
    / "settlement_precondition_vectors.json"
)


def _load_vectors() -> dict:
    return json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))


def test_vectors_file_loads() -> None:
    v = _load_vectors()
    assert v["$schema_version"] == 2
    assert len(v["verifier_vectors"]) == 12


@pytest.mark.parametrize(
    "vec",
    _load_vectors()["verifier_vectors"],
    ids=lambda v: v["name"],
)
def test_verifier_vector(vec: dict) -> None:
    claim = SettlementPreconditionClaim(
        claim_kind=vec["claim"]["claim_kind"],
        lease_id_hash=vec["claim"]["lease_id_hash"],
        settlement_run_id=vec["claim"]["settlement_run_id"],
        expected_settlement_amount_hash=vec["claim"].get("expected_settlement_amount_hash"),
    )
    result = check_settlement_precondition(vec["chain"], claim)
    expected = vec["expected"]

    assert result.ok == expected["ok"], (
        f"{vec['name']!r}: expected ok={expected['ok']}, got ok={result.ok}; "
        f"reason={result.reason!r}"
    )
    assert result.lease_consumed_seq == expected["lease_consumed_seq"]
    assert result.settlement_event_seq == expected["settlement_event_seq"]
    if expected["ok"]:
        assert result.reason is None
    else:
        assert expected["reason_contains"] in (result.reason or "")


def test_pure_function_identical_results() -> None:
    chain = [
        {"seq": 0, "event_type": "lease_lifecycle_event",
         "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64}},
        {"seq": 1, "event_type": "settlement_event",
         "payload": {"settlement_run_id": "s"}},
    ]
    claim = SettlementPreconditionClaim(
        claim_kind="settlement_precondition",
        lease_id_hash="a" * 64,
        settlement_run_id="s",
    )
    r1 = check_settlement_precondition(chain, claim)
    r2 = check_settlement_precondition(chain, claim)
    assert r1 == r2
    assert r1.ok is True


def test_read_only_invariant() -> None:
    chain = [
        {"seq": 0, "event_type": "lease_lifecycle_event",
         "payload": {"lifecycle": "consumed", "lease_id_hash": "a" * 64}},
        {"seq": 1, "event_type": "settlement_event",
         "payload": {"settlement_run_id": "s", "amount_hash": "b" * 64}},
    ]
    before = json.loads(json.dumps(chain))
    claim = SettlementPreconditionClaim(
        claim_kind="settlement_precondition",
        lease_id_hash="a" * 64,
        settlement_run_id="s",
        expected_settlement_amount_hash="b" * 64,
    )
    assert check_settlement_precondition(chain, claim).ok is True
    assert chain == before


def test_handles_malformed_chain() -> None:
    result = check_settlement_precondition(
        "not a list",  # type: ignore[arg-type]
        SettlementPreconditionClaim(
            claim_kind="settlement_precondition",
            lease_id_hash="0" * 64,
            settlement_run_id="x",
        ),
    )
    assert result.ok is False
    assert "must be list" in (result.reason or "")


def test_handles_naive_verification_time() -> None:
    from datetime import datetime
    result = check_settlement_precondition(
        [],
        SettlementPreconditionClaim(
            claim_kind="settlement_precondition",
            lease_id_hash="0" * 64,
            settlement_run_id="x",
        ),
        verification_time=datetime(2026, 5, 17),  # naive
    )
    assert result.ok is False
    assert "UTC-aware" in (result.reason or "")
