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


def _run_with_flags(
    name: str,
    capsys: pytest.CaptureFixture[str],
    *,
    flags: tuple[str, ...] = (),
) -> tuple[int, dict]:
    argv = ["verify-proofbundle", *flags, str(FIXTURE_DIR / name)]
    rc = main(argv)
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


# ----- P3.2 extension interface tests ---------------------------------------


def test_p3_2_default_flags_keep_p3_1_compatibility(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No flags → identical to P3.1 valid_minimal behaviour."""
    rc, payload = _run_with_flags("valid_minimal.json", capsys, flags=())
    assert rc == 0
    assert payload["ok"] is True
    assert payload["signature_verification_requested"] is False
    assert payload["signature_verification_performed"] is False
    assert payload["signature_verification_status"] == "skipped"
    assert payload["anchor_verification_requested"] is False
    assert payload["anchor_verification_performed"] is False
    assert payload["anchor_verification_status"] == "skipped"


def test_p3_2_signature_shape_valid_but_not_requested(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bundle carries signature_material but flag is OFF → skipped, exit 0."""
    rc, payload = _run_with_flags(
        "signature_shape_valid_but_not_requested.json", capsys, flags=()
    )
    assert rc == 0
    assert payload["signature_verification_status"] == "skipped"


def test_p3_2_anchor_shape_valid_but_not_requested(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bundle carries anchor_records but flag is OFF → skipped, exit 0."""
    rc, payload = _run_with_flags(
        "anchor_shape_valid_but_not_requested.json", capsys, flags=()
    )
    assert rc == 0
    assert payload["anchor_verification_status"] == "skipped"


@pytest.mark.parametrize(
    ("fixture", "flags", "expected_exit", "expected_field", "expected_status", "expected_reason"),
    [
        # --verify-signature paths
        (
            "missing_signature_material.json",
            ("--verify-signature",),
            2,
            "signature_verification_status",
            "invalid_input",
            "missing_material",
        ),
        (
            "unsupported_signature_algorithm.json",
            ("--verify-signature",),
            2,
            "signature_verification_status",
            "unsupported",
            "unsupported_algorithm",
        ),
        (
            "tampered_dsse_signature.json",
            ("--verify-signature",),
            2,
            "signature_verification_status",
            "not_implemented",
            "alpha_cryptographic_verification_not_implemented",
        ),
        (
            "signature_shape_valid_but_not_requested.json",
            ("--verify-signature",),
            2,
            "signature_verification_status",
            "not_implemented",
            "alpha_cryptographic_verification_not_implemented",
        ),
        # --verify-anchor paths
        (
            "missing_anchor_material.json",
            ("--verify-anchor",),
            2,
            "anchor_verification_status",
            "invalid_input",
            "missing_material",
        ),
        (
            "unsupported_anchor_type.json",
            ("--verify-anchor",),
            2,
            "anchor_verification_status",
            "unsupported",
            "unsupported_anchor_type",
        ),
        (
            "expired_tsa_timestamp.json",
            ("--verify-anchor",),
            2,
            "anchor_verification_status",
            "not_implemented",
            "alpha_anchor_verification_not_implemented",
        ),
        (
            "invalid_anchor_chain.json",
            ("--verify-anchor",),
            2,
            "anchor_verification_status",
            "not_implemented",
            "alpha_anchor_verification_not_implemented",
        ),
        (
            "anchor_shape_valid_but_not_requested.json",
            ("--verify-anchor",),
            2,
            "anchor_verification_status",
            "not_implemented",
            "alpha_anchor_verification_not_implemented",
        ),
    ],
)
def test_p3_2_signature_anchor_extension_fail_closed(
    fixture: str,
    flags: tuple[str, ...],
    expected_exit: int,
    expected_field: str,
    expected_status: str,
    expected_reason: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_with_flags(fixture, capsys, flags=flags)
    assert rc == expected_exit
    assert payload["ok"] is False
    assert payload[expected_field] == expected_status
    # Honest no-go claims preserved
    assert payload["signature_verification_performed"] is False
    assert payload["anchor_verification_performed"] is False
    assert payload["certified_provenance"] is False
    assert payload["compliance_certification"] is False
    # Reason field surfaced
    if expected_field == "signature_verification_status":
        assert payload["signature_verification_summary"]["reason"] == expected_reason
    elif expected_field == "anchor_verification_status":
        assert payload["anchor_verification_summary"]["reason"] == expected_reason


def test_p3_2_both_flags_missing_material_fails_closed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Both --verify-signature --verify-anchor with no material → exit 2."""
    rc, payload = _run_with_flags(
        "signature_and_anchor_requested_missing_material.json",
        capsys,
        flags=("--verify-signature", "--verify-anchor"),
    )
    assert rc == 2
    assert payload["ok"] is False
    assert payload["signature_verification_status"] == "invalid_input"
    assert payload["anchor_verification_status"] == "invalid_input"
    assert payload["signature_verification_performed"] is False
    assert payload["anchor_verification_performed"] is False


def test_p3_2_no_go_claims_present_in_every_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every report must surface the alpha-boundary no-go claims explicitly."""
    rc, payload = _run_with_flags("valid_minimal.json", capsys, flags=())
    assert rc == 0
    no_go = " | ".join(payload["no_go_claims"])
    for token in (
        "not production-ready",
        "not compliance-ready",
        "not certification-ready",
        "not certified provenance",
        "not SLSA L3",
        "not production-grade supply-chain security",
    ):
        assert token in no_go
