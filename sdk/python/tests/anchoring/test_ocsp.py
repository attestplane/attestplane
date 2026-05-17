# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.anchoring.ocsp`.

Uses TestTSAAuthority to produce real OCSP responses and verifies them
via parse_and_verify_ocsp.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring import AnchorVerificationError
from attestplane.anchoring.ocsp import parse_and_verify_ocsp
from attestplane.anchoring.testing import TestTSAAuthority

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _serial_of_leaf(authority: TestTSAAuthority) -> int:
    from asn1crypto import x509 as asn1_x509
    leaf = asn1_x509.Certificate.load(authority.materials().leaf_cert_der)
    return int(leaf.serial_number)


def test_real_ocsp_response_verifies_good() -> None:
    authority = TestTSAAuthority(now=_NOW)
    serial = _serial_of_leaf(authority)
    ocsp_der = authority.issue_real_ocsp_response(gen_time=_NOW)

    parsed = parse_and_verify_ocsp(
        ocsp_der,
        expected_serial=serial,
        issuer_cert_der=authority.materials().root_cert_der,
        verification_time=_NOW,
    )

    assert parsed.cert_status == "good"
    assert parsed.serial_number == serial
    assert parsed.revocation_time is None
    assert parsed.next_update is not None
    assert parsed.next_update > parsed.this_update


def test_real_ocsp_response_revoked_status() -> None:
    authority = TestTSAAuthority(now=_NOW)
    serial = _serial_of_leaf(authority)
    ocsp_der = authority.issue_real_ocsp_response(gen_time=_NOW, revoked=True)

    parsed = parse_and_verify_ocsp(
        ocsp_der,
        expected_serial=serial,
        issuer_cert_der=authority.materials().root_cert_der,
        verification_time=_NOW,
    )

    assert parsed.cert_status == "revoked"
    assert parsed.revocation_time is not None


def test_ocsp_rejects_legacy_synthetic() -> None:
    authority = TestTSAAuthority(now=_NOW)
    synthetic = authority.issue_ocsp_response(gen_time=_NOW)
    with pytest.raises(AnchorVerificationError, match="synthetic placeholder"):
        parse_and_verify_ocsp(
            synthetic,
            expected_serial=_serial_of_leaf(authority),
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )


def test_ocsp_rejects_garbage_bytes() -> None:
    authority = TestTSAAuthority(now=_NOW)
    with pytest.raises(AnchorVerificationError, match="not valid DER"):
        parse_and_verify_ocsp(
            b"not-asn1-bytes",
            expected_serial=_serial_of_leaf(authority),
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )


def test_ocsp_rejects_serial_mismatch() -> None:
    authority = TestTSAAuthority(now=_NOW)
    ocsp_der = authority.issue_real_ocsp_response(gen_time=_NOW)

    with pytest.raises(AnchorVerificationError, match="no entry for serial"):
        parse_and_verify_ocsp(
            ocsp_der,
            expected_serial=99999999,  # not in the response
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )


def test_ocsp_rejects_premature_verification_time() -> None:
    authority = TestTSAAuthority(now=_NOW)
    ocsp_der = authority.issue_real_ocsp_response(gen_time=_NOW)

    past = _NOW - timedelta(days=1)
    with pytest.raises(AnchorVerificationError, match="precedes OCSP thisUpdate"):
        parse_and_verify_ocsp(
            ocsp_der,
            expected_serial=_serial_of_leaf(authority),
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=past,
        )


def test_ocsp_rejects_stale_verification_time() -> None:
    authority = TestTSAAuthority(now=_NOW)
    # Issue with a short window.
    ocsp_der = authority.issue_real_ocsp_response(
        gen_time=_NOW,
        next_update=_NOW + timedelta(hours=1),
    )

    future = _NOW + timedelta(days=30)
    with pytest.raises(AnchorVerificationError, match="exceeds OCSP nextUpdate"):
        parse_and_verify_ocsp(
            ocsp_der,
            expected_serial=_serial_of_leaf(authority),
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=future,
        )


def test_ocsp_rejects_wrong_issuer_signature_check() -> None:
    """A different authority's root cert should fail the OCSP signature check."""
    authority_a = TestTSAAuthority(now=_NOW)
    authority_b = TestTSAAuthority(now=_NOW, common_name="Other")
    ocsp_der = authority_a.issue_real_ocsp_response(gen_time=_NOW)

    with pytest.raises(AnchorVerificationError, match="signature does not verify"):
        parse_and_verify_ocsp(
            ocsp_der,
            expected_serial=_serial_of_leaf(authority_a),
            issuer_cert_der=authority_b.materials().root_cert_der,
            verification_time=_NOW,
        )


def test_parsed_ocsp_contains_responder_cert_der() -> None:
    """When no certs are embedded, the responder_cert_der is the issuer."""
    authority = TestTSAAuthority(now=_NOW)
    ocsp_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    parsed = parse_and_verify_ocsp(
        ocsp_der,
        expected_serial=_serial_of_leaf(authority),
        issuer_cert_der=authority.materials().root_cert_der,
        verification_time=_NOW,
    )
    # Our TestTSAAuthority doesn't embed certs in the OCSP response, so
    # responder_cert_der must equal the issuer.
    assert parsed.responder_cert_der == authority.materials().root_cert_der
