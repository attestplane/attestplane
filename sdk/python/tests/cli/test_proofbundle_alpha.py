# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for the alpha ``verify-proofbundle`` CLI path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "proofbundle"


def _run_fixture(name: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict]:
    rc = main(["verify-proofbundle", str(FIXTURE_DIR / name)])
    payload = json.loads(capsys.readouterr().out)
    return rc, payload


def test_verify_proofbundle_help_declares_alpha_boundaries(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["verify-proofbundle", "--help"])
    assert exc_info.value.code == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "Alpha local ProofBundle verifier" in out
    assert "no network access" in out
    assert "signature verification" in out
    assert "anchor verification" in out
    assert "compliance certification" in out


def test_verify_proofbundle_valid_minimal_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_fixture("valid_minimal.json", capsys)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["exit_code"] == 0
    assert payload["verification_scope"] == "proofbundle_alpha_local"
    assert payload["network_access_performed"] is False
    assert payload["signature_verification_performed"] is False
    assert payload["anchor_verification_performed"] is False
    assert payload["compliance_certification"] is False
    assert payload["production_ready"] is False
    assert payload["certified_provenance"] is False
    assert payload["slsa_level_claimed"] is None
    assert payload["summary"]["checks_failed"] == 0
    assert [check["name"] for check in payload["checks"]] == [
        "json_parse",
        "required_fields",
        "schema_version",
        "proof_bundle_shape",
        "hash_chain_recompute",
        "artifact_hash",
        "hash_chain_metadata",
        "obligation_references",
        "in_toto_shape",
        "dsse_shape",
        "storage_compatibility",
        "provenance_shape",
    ]


@pytest.mark.parametrize(
    ("fixture", "expected_exit", "expected_check"),
    [
        ("missing_required_field.json", 2, "required_fields"),
        ("malformed.json", 2, "json_parse"),
        ("invalid_hash_format.json", 2, "artifact_hash"),
        ("tampered_artifact_hash.json", 1, "artifact_hash"),
        ("broken_hash_chain.json", 1, "hash_chain_recompute"),
        ("unsupported_version.json", 2, "schema_version"),
        ("missing_dsse_shape.json", 2, "required_fields"),
        ("missing_storage_compat.json", 2, "required_fields"),
        ("missing_provenance_shape.json", 2, "required_fields"),
    ],
)
def test_verify_proofbundle_negative_fixtures_fail_closed(
    fixture: str,
    expected_exit: int,
    expected_check: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_fixture(fixture, capsys)

    assert rc == expected_exit
    assert payload["ok"] is False
    assert payload["exit_code"] == expected_exit
    failed = [check for check in payload["checks"] if check["status"] == "fail"]
    assert failed
    assert failed[0]["name"] == expected_check
    assert payload["signature_verification_performed"] is False
    assert payload["anchor_verification_performed"] is False
    assert payload["compliance_certification"] is False

