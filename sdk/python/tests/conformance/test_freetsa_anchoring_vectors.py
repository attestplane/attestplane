# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Frozen FreeTSA replay bundles for anchoring regression coverage."""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import (
    VERIFY_REASON_ANCHOR_INVALID,
    VERIFY_REASON_ANCHOR_UNAVAILABLE,
)

ROOT = Path(__file__).resolve().parent
ANCHORED_FIXTURE = ROOT / "free_tsa_anchored_bundle.json"
QUARANTINED_FIXTURE = ROOT / "free_tsa_quarantined_bundle.json"
UNAVAILABLE_FIXTURE = ROOT / "free_tsa_unavailable_bundle.json"


def _load(path: Path) -> dict[str, object]:
    raw = path.read_text(encoding="utf-8")
    bundle = json.loads(raw)
    assert raw == json.dumps(bundle, indent=2) + "\n"
    return bundle


def test_freetsa_replay_fixtures_are_byte_stable() -> None:
    assert ANCHORED_FIXTURE.exists()
    assert QUARANTINED_FIXTURE.exists()
    assert UNAVAILABLE_FIXTURE.exists()
    _load(ANCHORED_FIXTURE)
    _load(QUARANTINED_FIXTURE)
    _load(UNAVAILABLE_FIXTURE)


def test_freetsa_anchored_fixture_verifies_as_anchored() -> None:
    result = verify_proof_bundle(_load(ANCHORED_FIXTURE))
    assert result.ok is True
    assert result.anchoring_status == "verified"
    assert result.anchoring_quarantined is False


def test_freetsa_quarantined_fixture_verifies_as_quarantined() -> None:
    result = verify_proof_bundle(_load(QUARANTINED_FIXTURE))
    assert result.ok is False
    assert result.anchoring_status == "quarantined"
    assert result.anchoring_quarantined is True
    assert result.primary_reason == VERIFY_REASON_ANCHOR_INVALID


def test_freetsa_unavailable_fixture_verifies_as_unavailable() -> None:
    result = verify_proof_bundle(_load(UNAVAILABLE_FIXTURE))
    assert result.ok is False
    assert result.anchoring_status == "quarantined"
    assert result.anchoring_quarantined is True
    assert result.primary_reason == VERIFY_REASON_ANCHOR_UNAVAILABLE
