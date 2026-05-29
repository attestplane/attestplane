# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Claim-safe quarantine surface tests for ``attestplane verify --json``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
QUARANTINE_FIXTURE = ROOT / "fixtures" / "anchor" / "quarantine_case.json"


def test_verify_json_surfaces_quarantine_anchor_status(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["verify", "--json", str(QUARANTINE_FIXTURE)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["result"] == "pass"
    assert payload["anchor_status"] == "quarantined"
    assert payload["anchor_reason_code"] == "att.verify.anchor_quarantined"
    assert payload["reasons"] == []
