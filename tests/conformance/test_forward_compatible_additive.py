# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main as cli_main
from attestplane.verifier import verify_proof_bundle
from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_UNKNOWN

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "conformance" / "vectors" / "manifest.json"
MANIFEST_CASES = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]


def _bundle(case: dict[str, object]) -> dict:
    path = ROOT / str(case["path"])
    return json.loads(path.read_text(encoding="utf-8"))


def _run_verify(path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object]]:
    rc = cli_main(["verify", "--json", str(path)])
    captured = capsys.readouterr()
    return rc, json.loads(captured.out)


def test_forward_compatible_additive_manifest_is_complete() -> None:
    assert {case["case_id"] for case in MANIFEST_CASES} == {
        "forward_compatible_additive_pass",
        "forward_compatible_additive_guard",
    }


@pytest.mark.parametrize("case", MANIFEST_CASES, ids=lambda case: case["case_id"])
def test_forward_compatible_additive_vectors_pin_expected_outcome(
    case: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = ROOT / str(case["path"])
    bundle = _bundle(case)

    result = verify_proof_bundle(bundle, require_signed_attestation=True)
    rc, payload = _run_verify(path, capsys)

    assert result.ok is case["ok"]
    assert result.primary_reason == case["expected_reason_code"]
    assert result.secondary_reasons == tuple(case["expected_secondary_reasons"])
    for field in case.get("chain_metadata_fields", ()):
        assert field in bundle["chain_metadata"]

    assert payload["schema_version"] == 1
    assert payload["result"] == ("pass" if case["ok"] else "fail")
    assert payload["reason_code"] == case["expected_reason_code"]
    assert rc == (0 if case["ok"] else 1)


def test_forward_compatible_additive_negative_guard_stays_fail_closed() -> None:
    guard = next(case for case in MANIFEST_CASES if case["case_id"] == "forward_compatible_additive_guard")
    bundle = _bundle(guard)

    result = verify_proof_bundle(bundle, require_signed_attestation=True)

    assert result.ok is False
    assert result.primary_reason == VERIFY_REASON_SCHEMA_UNKNOWN
    assert "critical_future_field" in (result.metadata_reason or "")
