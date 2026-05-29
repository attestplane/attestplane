# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Conformance checks for FreeTSA opt-in and quarantine behavior."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "proofbundle"
ANCHOR_VECTORS = json.loads((Path(__file__).with_name("anchor_vectors.json")).read_text(encoding="utf-8"))


def _vector_entry(name: str) -> dict[str, object]:
    for entry in ANCHOR_VECTORS["entries"]:
        if entry["name"] == name:
            return entry
    raise AssertionError(f"unknown anchor vector {name!r}")


def _bundle_with_anchor(entry: dict[str, object]) -> dict[str, object]:
    bundle = json.loads((FIXTURE_DIR / "valid_minimal.json").read_text(encoding="utf-8"))
    root_cert_b64 = ANCHOR_VECTORS["test_tsa_root_cert_b64"]
    bundle["anchor_records"] = [
        {
            "anchor_type": "rfc3161",
            "anchored_event_hash_hex": entry["anchored_event_hash_hex"],
            "anchored_seq": entry["anchored_seq"],
            "issued_at_claimed": entry["issued_at_claimed"],
            "tsa_provider_id": entry["tsa_provider_id"],
            "tsa_token_b64": entry["tsa_token_b64"],
            "tsa_cert_chain_b64": entry["tsa_cert_chain_b64"],
            "trust_roots_der_b64": [root_cert_b64],
            "ocsp_responses_b64": entry["ocsp_responses_b64"],
            "alpha_no_go_claims": {
                "rfc3161_token_verification_performed": True,
                "legal_timestamp_attestation": False,
                "long_term_archival_trust": False,
            },
        }
    ]
    return bundle


def _build_positive_anchor_bundle(
    tmp_path,  # type: ignore[no-untyped-def]
    *,
    authority_now=None,
    cert_validity_days: int = 365,
):
    pytest.importorskip("asn1crypto")
    pytest.importorskip("cryptography")

    from attestplane.anchoring.testing import TestTSAAuthority

    bundle = json.loads((FIXTURE_DIR / "valid_minimal.json").read_text(encoding="utf-8"))
    head_hex = bundle["hash_chain"]["head_hash_hex"]
    digest = bytes.fromhex(head_hex)

    now = authority_now or datetime.now(UTC)
    authority = TestTSAAuthority(now=now, cert_validity_days=cert_validity_days)
    materials = authority.materials()
    token_der = authority.sign_timestamp_response(digest, gen_time=now, serial_number=1)

    bundle["anchor_records"] = [
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
    out.write_text(json.dumps(bundle, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def test_freetsa_live_path_is_opt_in(
    tmp_path,  # type: ignore[no-untyped-def]
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Default proofbundle verification keeps anchor verification skipped."""
    entry = _vector_entry("single_event_anchor")
    path = tmp_path / "freetsa_off_by_default.json"
    path.write_text(json.dumps(_bundle_with_anchor(entry), ensure_ascii=False) + "\n", encoding="utf-8")

    rc = main(["verify-proofbundle", str(path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["anchor_verification_requested"] is False
    assert payload["anchor_verification_performed"] is False
    assert payload["anchor_verification_status"] == "skipped"
    assert payload["network_access_performed"] is False


def test_quarantine_tampered_tsa_token_never_passes(
    tmp_path,  # type: ignore[no-untyped-def]
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A parseable-but-tampered RFC-3161 token must quarantine, not pass."""
    pytest.importorskip("asn1crypto")
    pytest.importorskip("cryptography")

    path = _build_positive_anchor_bundle(tmp_path)
    bundle = json.loads(path.read_text(encoding="utf-8"))
    token_b64 = bundle["anchor_records"][0]["tsa_token_b64"]
    token_bytes = bytearray(base64.standard_b64decode(token_b64))
    token_bytes[-32] ^= 0x01
    bundle["anchor_records"][0]["tsa_token_b64"] = base64.standard_b64encode(
        bytes(token_bytes),
    ).decode("ascii")
    quarantine_path = tmp_path / "quarantine_tampered_tsa.json"
    quarantine_path.write_text(json.dumps(bundle, ensure_ascii=False) + "\n", encoding="utf-8")

    rc = main(["verify-proofbundle", str(quarantine_path), "--verify-anchor"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert payload["ok"] is False
    assert payload["anchor_verification_status"] == "quarantined"
    assert payload["anchor_verification_performed"] is True
    assert payload["anchor_verification_summary"]["reason"] == "rfc3161_verify_failed"
    assert payload["anchor_verification_summary"]["quarantine_reason"] == "rfc3161_verification_failed"


def test_quarantine_expired_tsa_token_never_passes(
    tmp_path,  # type: ignore[no-untyped-def]
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A timestamp whose cert is expired at verification time must quarantine."""
    pytest.importorskip("asn1crypto")
    pytest.importorskip("cryptography")

    expired_at = datetime(2026, 5, 1, tzinfo=UTC)
    path = _build_positive_anchor_bundle(
        tmp_path,
        authority_now=expired_at,
        cert_validity_days=1,
    )

    rc = main(["verify-proofbundle", str(path), "--verify-anchor"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert payload["ok"] is False
    assert payload["anchor_verification_status"] == "quarantined"
    assert payload["anchor_verification_performed"] is True
    assert payload["anchor_verification_summary"]["reason"] == "rfc3161_verify_failed"
    assert payload["anchor_verification_summary"]["quarantine_reason"] == "rfc3161_verification_failed"
