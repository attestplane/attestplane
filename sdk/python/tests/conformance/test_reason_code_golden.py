# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Golden lock for the ADR-0010 reason-code taxonomy.

The contract is append-only within a reason_code_version: any add, remove, or
rename must be accompanied by a version bump and explicit regeneration of the
checked-in snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

from attestplane.reason_codes import ALL_REASON_CODES_V1, REASON_CODE_SCHEMA_VERSION

from .generate_reason_code_golden import build_snapshot

SNAPSHOT_PATH = Path(__file__).with_name("reason_code_golden.json")


def _load_snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_reason_code_golden_snapshot_matches_current_taxonomy() -> None:
    """Golden snapshot must stay in lockstep with the current v1 taxonomy."""
    snapshot = _load_snapshot()
    expected = build_snapshot()

    assert snapshot == expected
    assert snapshot["reason_code_version"] == REASON_CODE_SCHEMA_VERSION
    assert snapshot["reason_codes"] == sorted(ALL_REASON_CODES_V1)
    assert len(snapshot["reason_codes"]) == len(ALL_REASON_CODES_V1)


def test_reason_code_golden_snapshot_documents_append_only_contract() -> None:
    """The locked taxonomy is append-only within a single version."""
    snapshot = _load_snapshot()

    assert snapshot["reason_code_version"] == 1
    assert snapshot["reason_codes"] == sorted(snapshot["reason_codes"])
    assert len(snapshot["reason_codes"]) == len(set(snapshot["reason_codes"]))
