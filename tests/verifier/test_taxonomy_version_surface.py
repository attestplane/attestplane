# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from attestplane.cli.main import main  # noqa: E402
from attestplane.verifier import verify_proof_bundle  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "bundles" / "valid_signed_attestation.json"


def _run_verify(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_taxonomy_version_is_surfaced_from_the_bundle_across_verifier_surfaces(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected = bundle["chain_metadata"]["evidence_taxonomy_version"]

    result = verify_proof_bundle(bundle)
    assert result.taxonomy_version == expected

    json_rc, json_out, json_err = _run_verify(["verify", "--json", str(FIXTURE)], capsys)
    explain_rc, explain_out, explain_err = _run_verify(
        ["verify", "--json", "--explain", str(FIXTURE)],
        capsys,
    )
    text_rc, text_out, text_err = _run_verify(["verify", "--explain", str(FIXTURE)], capsys)
    json_rc_2, json_out_2, json_err_2 = _run_verify(["verify", "--json", str(FIXTURE)], capsys)

    json_payload = json.loads(json_out)
    explain_payload = json.loads(explain_out)

    assert json_rc == 0
    assert explain_rc == 0
    assert text_rc == 0
    assert json_rc_2 == 0
    assert json_err == ""
    assert explain_err == ""
    assert text_err == ""
    assert json_err_2 == ""
    assert json_out == json_out_2
    assert json_payload["taxonomy_version"] == expected
    assert explain_payload["taxonomy_version"] == expected
    assert json_payload["taxonomy_version"] == explain_payload["taxonomy_version"]
    assert json_payload["taxonomy_version"] == result.taxonomy_version
    assert f"taxonomy_version={expected}" in explain_payload["explanation"][0]["message"]
    assert f"taxonomy_version={expected}" in text_out
