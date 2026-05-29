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
    assert "signature material verification" in out
    assert "anchor material verification" in out
    assert "compliance certification" in out


def test_verify_proofbundle_valid_minimal_fixture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_fixture("valid_minimal.json", capsys)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "ok"
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
    ("fixture", "expected_exit", "expected_status", "expected_check"),
    [
        ("missing_required_field.json", 3, "output_contract_error", "required_fields"),
        ("malformed.json", 3, "output_contract_error", "json_parse"),
        ("invalid_hash_format.json", 3, "output_contract_error", "artifact_hash"),
        ("tampered_artifact_hash.json", 2, "invalid_signature_or_anchor", "artifact_hash"),
        ("broken_hash_chain.json", 2, "invalid_signature_or_anchor", "hash_chain_recompute"),
        ("unsupported_version.json", 3, "output_contract_error", "schema_version"),
        ("missing_dsse_shape.json", 3, "output_contract_error", "required_fields"),
        ("missing_storage_compat.json", 3, "output_contract_error", "required_fields"),
        ("missing_provenance_shape.json", 3, "output_contract_error", "required_fields"),
    ],
)
def test_verify_proofbundle_negative_fixtures_fail_closed(
    fixture: str,
    expected_exit: int,
    expected_status: str,
    expected_check: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload = _run_fixture(fixture, capsys)
    assert rc == expected_exit
    assert payload["ok"] is False
    assert payload["status"] == expected_status
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
    assert payload["status"] == "ok"
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
    rc, payload = _run_with_flags("signature_shape_valid_but_not_requested.json", capsys, flags=())
    assert rc == 0
    assert payload["status"] == "ok"
    assert payload["signature_verification_status"] == "skipped"


def test_p3_2_anchor_shape_valid_but_not_requested(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bundle carries anchor_records but flag is OFF → skipped, exit 0."""
    rc, payload = _run_with_flags("anchor_shape_valid_but_not_requested.json", capsys, flags=())
    assert rc == 0
    assert payload["status"] == "ok"
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
        # P3.4: real crypto now runs. Tampered fixture has placeholder PEM-less
        # public_keys[] block → "missing_keyid_or_pem" invalid_input.
        (
            "tampered_dsse_signature.json",
            ("--verify-signature",),
            2,
            "signature_verification_status",
            "invalid_input",
            "missing_keyid_or_pem",
        ),
        # signature_shape_valid_but_not_requested has empty dsse_envelope.signatures[].
        # With --verify-signature the algorithm allowlist check passes (ed25519),
        # then the empty-signatures branch trips → missing_material.
        (
            "signature_shape_valid_but_not_requested.json",
            ("--verify-signature",),
            2,
            "signature_verification_status",
            "invalid_input",
            "missing_material",
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
        # P3.4: real anchor verify now runs. P3.2 fixtures predate the
        # trust_roots_der_b64 schema field, so they trip missing_trust_roots
        # invalid_input before reaching the cryptographic verify path.
        # Positive crypto path is exercised in
        # test_p3_4_anchor_verify_passes_with_real_test_tsa below.
        (
            "expired_tsa_timestamp.json",
            ("--verify-anchor",),
            2,
            "anchor_verification_status",
            "invalid_input",
            "anchor_extras_missing",
        ),
        (
            "invalid_anchor_chain.json",
            ("--verify-anchor",),
            2,
            "anchor_verification_status",
            "invalid_input",
            "anchor_extras_missing",
        ),
        (
            "anchor_shape_valid_but_not_requested.json",
            ("--verify-anchor",),
            2,
            "anchor_verification_status",
            "invalid_input",
            "anchor_extras_missing",
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
    assert payload["status"] == "invalid_signature_or_anchor"
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
    assert payload["status"] == "invalid_signature_or_anchor"
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


# ----- P3.4 positive crypto wiring -----------------------------------------


def _build_positive_signature_bundle(tmp_path):  # type: ignore[no-untyped-def]
    """Build a ProofBundle envelope JSON with a real ed25519 DSSE signature.

    Generates a test-only ed25519 keypair, signs the DSSE PAE bytes derived
    from the existing valid_minimal.json's in-toto Statement, embeds the
    public key in PEM + the signature in base64 inside the envelope, and
    writes the result to ``tmp_path / positive.json``. Returns the path.
    """
    import base64
    import json

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from attestplane.intoto import DSSE_PAYLOAD_TYPE, dsse_pae

    base = json.loads((FIXTURE_DIR / "valid_minimal.json").read_text(encoding="utf-8"))
    envelope = base["dsse_envelope"]
    payload_bytes = base64.standard_b64decode(envelope["payload"])
    pae = dsse_pae(DSSE_PAYLOAD_TYPE, payload_bytes)

    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    pem = pk.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    sig = sk.sign(pae)
    sig_b64 = base64.standard_b64encode(sig).decode("ascii")

    base["signature_material"] = {
        "algorithm": "ed25519",
        "key_provider": "test-only-fixture-runtime",
        "public_keys": [
            {
                "keyid": "test-ed25519-key-01",
                "algorithm": "ed25519",
                "public_key_pem": pem,
                "note": "test-only ed25519 public key generated at test runtime",
            }
        ],
        "alpha_no_go_claims": {
            "cryptographic_verification_performed": True,
            "production_key_lifecycle": False,
        },
    }
    envelope["signatures"] = [
        {
            "keyid": "test-ed25519-key-01",
            "algorithm": "ed25519",
            "sig": sig_b64,
        }
    ]

    out = tmp_path / "positive_signature.json"
    out.write_text(json.dumps(base, ensure_ascii=False) + "\n", encoding="utf-8")
    return out, sk, sig_b64, envelope


def test_p3_4_verify_signature_real_dsse_passes(
    tmp_path,  # type: ignore[no-untyped-def]
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Positive: real ed25519 DSSE signature verifies; status=passed, exit 0."""
    path, _sk, _sig, _envelope = _build_positive_signature_bundle(tmp_path)
    rc = main(["verify-proofbundle", str(path), "--verify-signature"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "ok"
    assert payload["signature_verification_status"] == "passed"
    assert payload["signature_verification_performed"] is True
    assert payload["signature_verification_summary"]["verified_signature_count"] == 1
    assert payload["signature_verification_claims"]["cryptographic_verification_performed"] is True
    # Honest no-go claims preserved even on positive crypto.
    assert payload["compliance_certification"] is False
    assert payload["certified_provenance"] is False


def test_p3_4_verify_signature_tampered_signature_fails(
    tmp_path,  # type: ignore[no-untyped-def]
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Tampering the DSSE signature bytes produces verification_failed (exit 1)."""
    import base64
    import json as json_mod

    path, _sk, _sig, _envelope = _build_positive_signature_bundle(tmp_path)
    bundle = json_mod.loads(path.read_text(encoding="utf-8"))
    # Flip 1 bit of the signature (keep payload intact so all earlier checks
    # pass and we genuinely reach the cryptographic verify step).
    sig_b64 = bundle["dsse_envelope"]["signatures"][0]["sig"]
    sig_bytes = bytearray(base64.standard_b64decode(sig_b64))
    sig_bytes[-1] ^= 0x01
    bundle["dsse_envelope"]["signatures"][0]["sig"] = base64.standard_b64encode(
        bytes(sig_bytes),
    ).decode("ascii")
    path.write_text(json_mod.dumps(bundle, ensure_ascii=False) + "\n", encoding="utf-8")

    rc = main(["verify-proofbundle", str(path), "--verify-signature"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["ok"] is False
    assert payload["status"] == "invalid_signature_or_anchor"
    assert payload["signature_verification_status"] == "failed"
    assert payload["signature_verification_performed"] is False
    assert payload["signature_verification_summary"]["reason"] == "signature_does_not_verify"


def _build_positive_anchor_bundle(tmp_path):  # type: ignore[no-untyped-def]
    """Build a ProofBundle envelope JSON with a real RFC-3161 token anchor.

    Uses the in-tree TestTSAAuthority to issue a real, byte-valid timestamp
    response over the ProofBundle chain head hash. The trust root is the
    authority's own self-signed root cert.
    """
    import base64
    import json
    from datetime import UTC, datetime

    from attestplane.anchoring.testing import TestTSAAuthority

    base = json.loads((FIXTURE_DIR / "valid_minimal.json").read_text(encoding="utf-8"))
    head_hex = base["hash_chain"]["head_hash_hex"]
    digest = bytes.fromhex(head_hex)

    # Use current wall-clock time so the leaf-cert not_before window covers
    # `datetime.now(UTC)` (the default verification_time inside
    # verify_timestamp_token). Otherwise a fixed future "now" produces a
    # leaf cert that is not-yet-valid at verify time and the verifier
    # correctly rejects it.
    now = datetime.now(UTC)
    authority = TestTSAAuthority(now=now)
    materials = authority.materials()
    token_der = authority.sign_timestamp_response(digest, gen_time=now, serial_number=1)

    base["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "anchored_event_hash_hex": head_hex,
            "anchored_seq": 0,
            "issued_at_claimed": now.isoformat(),
            "tsa_provider_id": "test.tsa:Attestplane Test TSA — Positive",
            "tsa_token_b64": base64.standard_b64encode(token_der).decode("ascii"),
            "tsa_cert_chain_b64": [
                base64.standard_b64encode(materials.leaf_cert_der).decode("ascii"),
                base64.standard_b64encode(materials.root_cert_der).decode("ascii"),
            ],
            "trust_roots_der_b64": [
                base64.standard_b64encode(materials.root_cert_der).decode("ascii"),
            ],
            "alpha_no_go_claims": {
                "rfc3161_token_verification_performed": True,
                "legal_timestamp_attestation": False,
                "long_term_archival_trust": False,
            },
        }
    ]

    out = tmp_path / "positive_anchor.json"
    out.write_text(json.dumps(base, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def test_p3_4_verify_anchor_real_rfc3161_passes(
    tmp_path,  # type: ignore[no-untyped-def]
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Positive: real RFC-3161 anchor verifies against TestTSA root; exit 0."""
    pytest.importorskip("asn1crypto")
    pytest.importorskip("cryptography")
    path = _build_positive_anchor_bundle(tmp_path)
    rc = main(["verify-proofbundle", str(path), "--verify-anchor"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["status"] == "ok"
    assert payload["anchor_verification_status"] == "passed"
    assert payload["anchor_verification_performed"] is True
    assert payload["anchor_verification_summary"]["verified_anchor_count"] == 1
    assert payload["anchor_verification_claims"]["anchor_verification_performed"] is True
    assert payload["anchor_verification_claims"]["network_access_attempted"] is False
    # No-go claims preserved.
    assert payload["anchor_verification_claims"]["legal_timestamp_attestation"] is False
    assert payload["anchor_verification_claims"]["long_term_archival_trust"] is False


def test_p3_4_verify_anchor_wrong_trust_root_quarantines(
    tmp_path,  # type: ignore[no-untyped-def]
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Anchor signed by authority A but verified against root of authority B fails."""
    pytest.importorskip("asn1crypto")
    pytest.importorskip("cryptography")
    import base64
    import json as json_mod
    from datetime import UTC, datetime

    from attestplane.anchoring.testing import TestTSAAuthority

    path = _build_positive_anchor_bundle(tmp_path)
    # Replace trust_roots_der_b64 with a different authority's root.
    bundle = json_mod.loads(path.read_text(encoding="utf-8"))
    other_authority = TestTSAAuthority(
        now=datetime.now(UTC),
        common_name="Other Authority",
    )
    bundle["anchor_records"][0]["trust_roots_der_b64"] = [
        base64.standard_b64encode(other_authority.materials().root_cert_der).decode("ascii"),
    ]
    path.write_text(json_mod.dumps(bundle, ensure_ascii=False) + "\n", encoding="utf-8")

    rc = main(["verify-proofbundle", str(path), "--verify-anchor"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 4
    assert payload["ok"] is False
    assert payload["status"] == "quarantined"
    assert payload["anchor_verification_status"] == "quarantined"
    assert payload["anchor_verification_performed"] is False
    assert payload["anchor_verification_summary"]["reason"] == "anchor_unverifiable"
