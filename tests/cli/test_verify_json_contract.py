# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Versioned contract pinning for ``attestplane verify --json``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main
from attestplane.cli.verify_json import VERIFY_JSON_RESULT_VALUES

ROOT = Path(__file__).resolve().parents[2]
VALID_BUNDLE = ROOT / "fixtures" / "bundles" / "valid.json"
VERIFY_JSON_CONTRACT = ROOT / "fixtures" / "contracts" / "verify_json_v1.json"
VERIFY_JSON_SCHEMA = ROOT / "schemas" / "cli" / "verify-result-v1.json"


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _canonical_json_text(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _classify_contract_exit_code(
    *,
    verify_rc: int,
    payload: dict[str, object] | None,
    contract_matches: bool,
) -> int:
    if verify_rc == 2:
        return 2
    if not contract_matches:
        return 4
    if payload is None:
        return verify_rc
    result = str(payload.get("result"))
    if result == "quarantined":
        return 3
    if result == "fail":
        return 1
    return 0


def test_verify_json_contract_v1_matches_pinned_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, stdout, stderr = _run_verify(["verify", "--json", str(VALID_BUNDLE)], capsys)
    payload = json.loads(stdout)
    pinned = VERIFY_JSON_CONTRACT.read_text(encoding="utf-8")

    assert rc == 0
    assert stderr == ""
    assert pinned == _canonical_json_text(json.loads(pinned))
    assert _canonical_json_text(payload) == pinned


def test_verify_json_contract_v1_schema_includes_quarantined() -> None:
    schema = json.loads(VERIFY_JSON_SCHEMA.read_text(encoding="utf-8"))

    assert schema["properties"]["result"]["enum"] == list(VERIFY_JSON_RESULT_VALUES)


@pytest.mark.parametrize(
    ("verify_rc", "payload", "contract_matches", "expected"),
    [
        (0, {"result": "pass"}, True, 0),
        (1, {"result": "fail"}, True, 1),
        (3, {"result": "quarantined"}, True, 3),
        (0, {"result": "pass"}, False, 4),
        (2, None, True, 2),
    ],
)
def test_verify_json_contract_exit_code_mapping_is_deterministic(
    verify_rc: int,
    payload: dict[str, object] | None,
    contract_matches: bool,
    expected: int,
) -> None:
    assert (
        _classify_contract_exit_code(
            verify_rc=verify_rc,
            payload=payload,
            contract_matches=contract_matches,
        )
        == expected
    )
