# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "tests" / "conformance" / "fixtures"
CONTRACT_MANIFEST = FIXTURE_DIR / "verify_json_contract_v1.json"
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
PASS_GOLDEN = FIXTURE_DIR / "verify_json_pass.golden"
FAIL_GOLDEN = FIXTURE_DIR / "verify_json_fail.golden"


def _load_contract_manifest() -> dict[str, object]:
    return json.loads(CONTRACT_MANIFEST.read_text(encoding="utf-8"))


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out


def test_verify_json_output_contract_version_is_pinned() -> None:
    manifest = _load_contract_manifest()

    assert manifest["contract_version"] == 1
    assert manifest["output_ordering"] == "json.dumps(indent=2, sort_keys=True)"
    assert manifest["exit_codes"] == {
        "verified": 0,
        "verification_failure": 1,
        "usage_or_io_error": 2,
        "pinning_gate_failure": 3,
    }


def test_verify_json_output_contract_pass_fixture_matches_golden(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, stdout = _run_verify(["verify", "--json", str(PASS_FIXTURE)], capsys)

    assert rc == 0
    assert stdout == PASS_GOLDEN.read_text(encoding="utf-8")


def test_verify_json_output_contract_fail_fixture_matches_golden(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, stdout = _run_verify(["verify", "--json", str(FAIL_FIXTURE)], capsys)

    assert rc == 1
    assert stdout == FAIL_GOLDEN.read_text(encoding="utf-8")
