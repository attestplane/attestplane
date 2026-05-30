# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Deterministic CI gate exit-code contract for ``attestplane verify --json``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
VALID_BUNDLE = ROOT / "fixtures" / "valid_bundle.att"
GOLDEN_FIXTURE = ROOT / "fixtures" / "golden" / "verify_json_v1.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
QUARANTINE_FIXTURE = ROOT / "fixtures" / "quarantined.bundle"

CI_GATE_EXIT_CODES = {
    "valid": 0,
    "invalid": 1,
    "quarantine_or_anchor_unverified": 2,
    "usage_error": 3,
    "pinning_mismatch": 4,
}


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object]]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, json.loads(captured.out)


def _gate_exit_code(
    verify_rc: int,
    payload: dict[str, object],
    golden: dict[str, object],
) -> int:
    if verify_rc != CI_GATE_EXIT_CODES["valid"]:
        return verify_rc
    if payload != golden:
        return CI_GATE_EXIT_CODES["pinning_mismatch"]
    return CI_GATE_EXIT_CODES["valid"]


def test_verify_json_exit_code_contract(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    golden = json.loads(GOLDEN_FIXTURE.read_text(encoding="utf-8"))

    rc, payload = _run_verify(["verify", "--json", str(VALID_BUNDLE)], capsys)
    assert rc == CI_GATE_EXIT_CODES["valid"]
    assert payload == golden
    assert _gate_exit_code(rc, payload, golden) == CI_GATE_EXIT_CODES["valid"]

    rc, payload = _run_verify(["verify", "--json", str(FAIL_FIXTURE)], capsys)
    assert rc == CI_GATE_EXIT_CODES["invalid"]
    assert _gate_exit_code(rc, payload, golden) == CI_GATE_EXIT_CODES["invalid"]

    rc, payload = _run_verify(["verify", "--json", str(QUARANTINE_FIXTURE)], capsys)
    assert rc == CI_GATE_EXIT_CODES["quarantine_or_anchor_unverified"]
    assert _gate_exit_code(rc, payload, golden) == CI_GATE_EXIT_CODES["quarantine_or_anchor_unverified"]

    missing = tmp_path / "missing.json"
    rc, payload = _run_verify(["verify", "--json", str(missing)], capsys)
    assert rc == CI_GATE_EXIT_CODES["usage_error"]
    assert _gate_exit_code(rc, payload, golden) == CI_GATE_EXIT_CODES["usage_error"]

    drifted_golden = dict(golden)
    drifted_golden["taxonomy_version"] = 99
    rc, payload = _run_verify(["verify", "--json", str(VALID_BUNDLE)], capsys)
    assert rc == CI_GATE_EXIT_CODES["valid"]
    assert _gate_exit_code(rc, payload, drifted_golden) == CI_GATE_EXIT_CODES["pinning_mismatch"]
