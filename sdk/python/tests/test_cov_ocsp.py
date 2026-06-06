# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-completion tests for attestplane.anchoring.ocsp.

Targets the missing lines/branches reported in the 76% baseline:
  107, 111, 121, 128-129, 132-137, 143, 175-179, 183, 187, 191, 195
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from asn1crypto import algos, core
from asn1crypto import ocsp as asn1_ocsp
from asn1crypto import x509 as asn1_x509

from attestplane.anchoring import AnchorVerificationError
from attestplane.anchoring.ocsp import parse_and_verify_ocsp
from attestplane.anchoring.testing import TestTSAAuthority

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _serial_of_leaf(authority: TestTSAAuthority) -> int:
    leaf = asn1_x509.Certificate.load(authority.materials().leaf_cert_der)
    return int(leaf.serial_number)


def _build_non_successful_ocsp(status: str) -> bytes:
    """Build a minimal OCSPResponse with a non-successful response_status."""
    resp = asn1_ocsp.OCSPResponse({"response_status": status})
    der: bytes = resp.dump()
    return der


def _build_non_basic_ocsp(authority: TestTSAAuthority) -> bytes:
    """Build an OCSPResponse whose response_type is not basic_ocsp_response."""

    # Build a minimal tbs + signature using root key, but give a non-basic type.
    issuer_der = authority.materials().root_cert_der
    issuer_asn1 = asn1_x509.Certificate.load(issuer_der)

    # Produce a valid-looking BasicOCSPResponse body but with a wrong OID.
    leaf_der = authority.materials().leaf_cert_der
    leaf_asn1 = asn1_x509.Certificate.load(leaf_der)

    from hashlib import sha1

    issuer_name_hash = sha1(issuer_asn1["tbs_certificate"]["subject"].dump()).digest()
    spki = issuer_asn1["tbs_certificate"]["subject_public_key_info"]
    bit_bytes = spki["public_key"].contents
    if bit_bytes and bit_bytes[0] == 0:
        bit_bytes = bit_bytes[1:]
    issuer_key_hash = sha1(bit_bytes).digest()

    cert_id = asn1_ocsp.CertId(
        {
            "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha1"}),
            "issuer_name_hash": issuer_name_hash,
            "issuer_key_hash": issuer_key_hash,
            "serial_number": leaf_asn1.serial_number,
        }
    )
    cert_status = asn1_ocsp.CertStatus({"good": core.Null()})
    single_response = asn1_ocsp.SingleResponse(
        {
            "cert_id": cert_id,
            "cert_status": cert_status,
            "this_update": _NOW,
            "next_update": _NOW + timedelta(days=7),
        }
    )
    tbs = asn1_ocsp.ResponseData(
        {
            "responder_id": asn1_ocsp.ResponderId(
                name="by_name",
                value=issuer_asn1["tbs_certificate"]["subject"],
            ),
            "produced_at": _NOW,
            "responses": [single_response],
        }
    )
    tbs_der = tbs.dump()

    root_key_der = authority.materials().root_cert_der  # this is the cert, not the key
    # Use the authority's root key via its private interface by generating a new response
    # and patching the response_type OID.
    # Simpler: build a real basic response and patch the OID bytes directly.
    real_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    # Parse the real DER and reconstruct with a different OID (id-smime-aa-ets-certValues = 1.2.840.113549.1.9.16.2.23)
    real_resp = asn1_ocsp.OCSPResponse.load(real_der)
    rb = real_resp["response_bytes"]
    # Build ResponseBytes with a different OID
    alt_response_bytes = asn1_ocsp.ResponseBytes(
        {
            "response_type": "1.2.840.113549.1.9.16.2.23",  # not basic_ocsp_response
            "response": rb["response"],
        }
    )
    alt_resp = asn1_ocsp.OCSPResponse(
        {
            "response_status": "successful",
            "response_bytes": alt_response_bytes,
        }
    )
    der: bytes = alt_resp.dump()
    return der


# --- Line 107: non-successful response_status ---------------------------------


def test_ocsp_rejects_try_later_status() -> None:
    """Line 107: status != 'successful' raises AnchorVerificationError."""
    der = _build_non_successful_ocsp("try_later")
    authority = TestTSAAuthority(now=_NOW)
    with pytest.raises(AnchorVerificationError, match="try_later"):
        parse_and_verify_ocsp(
            der,
            expected_serial=_serial_of_leaf(authority),
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )


def test_ocsp_rejects_malformed_status() -> None:
    """Line 107: another non-successful status variant."""
    der = _build_non_successful_ocsp("unauthorized")
    authority = TestTSAAuthority(now=_NOW)
    with pytest.raises(AnchorVerificationError, match="unauthorized"):
        parse_and_verify_ocsp(
            der,
            expected_serial=_serial_of_leaf(authority),
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )


# --- Lines 111-113: non-basic response_type -----------------------------------


def test_ocsp_rejects_non_basic_response_type() -> None:
    """Lines 111-113: response_type != 'basic_ocsp_response' raises error."""
    authority = TestTSAAuthority(now=_NOW)
    der = _build_non_basic_ocsp(authority)
    with pytest.raises(AnchorVerificationError, match="basic_ocsp_response"):
        parse_and_verify_ocsp(
            der,
            expected_serial=_serial_of_leaf(authority),
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )


# --- Line 121: unsupported signature algorithm --------------------------------


def test_ocsp_rejects_unsupported_sig_algo() -> None:
    """Line 121: sig_algo not in (rsassa_pkcs1v15, sha256_rsa)."""
    authority = TestTSAAuthority(now=_NOW)
    real_der = authority.issue_real_ocsp_response(gen_time=_NOW)

    # Parse the real response and rebuild with a different sig_algorithm.
    resp = asn1_ocsp.OCSPResponse.load(real_der)
    basic = resp["response_bytes"]["response"].parsed

    # Rebuild BasicOCSPResponse with ecdsa-with-SHA256 algorithm OID.
    new_basic = asn1_ocsp.BasicOCSPResponse(
        {
            "tbs_response_data": basic["tbs_response_data"],
            "signature_algorithm": algos.SignedDigestAlgorithm({"algorithm": "sha256_ecdsa"}),
            "signature": basic["signature"],
        }
    )
    new_resp = asn1_ocsp.OCSPResponse(
        {
            "response_status": "successful",
            "response_bytes": asn1_ocsp.ResponseBytes(
                {
                    "response_type": "basic_ocsp_response",
                    "response": core.ParsableOctetString(new_basic.dump()),
                }
            ),
        }
    )
    with pytest.raises(AnchorVerificationError, match="RSA-PKCS1v15"):
        parse_and_verify_ocsp(
            new_resp.dump(),
            expected_serial=_serial_of_leaf(authority),
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )


# --- Lines 128-129: invalid issuer_cert_der -----------------------------------


def test_ocsp_rejects_invalid_issuer_cert_der() -> None:
    """Lines 128-129: issuer_cert_der is not valid DER raises error."""
    authority = TestTSAAuthority(now=_NOW)
    ocsp_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    with pytest.raises(AnchorVerificationError, match="issuer_cert_der is not valid DER"):
        parse_and_verify_ocsp(
            ocsp_der,
            expected_serial=_serial_of_leaf(authority),
            issuer_cert_der=b"not-valid-der-for-issuer",
            verification_time=_NOW,
        )


# --- Lines 132-137: embedded certs branch (responder != issuer) ---------------


def test_ocsp_uses_embedded_cert_when_present() -> None:
    """Lines 132-137: When certs are embedded in the OCSP response, use the first one."""
    authority = TestTSAAuthority(now=_NOW)
    real_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    serial = _serial_of_leaf(authority)

    # Parse the real response and rebuild it with the root cert embedded.
    resp = asn1_ocsp.OCSPResponse.load(real_der)
    basic = resp["response_bytes"]["response"].parsed

    # Embed the root cert (which is the same as the responder = issuer here).
    root_asn1 = asn1_x509.Certificate.load(authority.materials().root_cert_der)
    new_basic = asn1_ocsp.BasicOCSPResponse(
        {
            "tbs_response_data": basic["tbs_response_data"],
            "signature_algorithm": basic["signature_algorithm"],
            "signature": basic["signature"],
            "certs": [root_asn1],
        }
    )
    new_resp = asn1_ocsp.OCSPResponse(
        {
            "response_status": "successful",
            "response_bytes": asn1_ocsp.ResponseBytes(
                {
                    "response_type": "basic_ocsp_response",
                    "response": core.ParsableOctetString(new_basic.dump()),
                }
            ),
        }
    )
    parsed = parse_and_verify_ocsp(
        new_resp.dump(),
        expected_serial=serial,
        issuer_cert_der=authority.materials().root_cert_der,
        verification_time=_NOW,
    )
    assert parsed.cert_status == "good"
    assert parsed.responder_cert_der == authority.materials().root_cert_der


# --- Line 143: non-RSA responder key ------------------------------------------


def test_ocsp_rejects_ec_responder_key() -> None:
    """Line 143: responder key is EC (not RSA) raises AnchorVerificationError."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    # Build an EC key authority to produce the embedded cert.
    ec_key = ec.generate_private_key(ec.SECP256R1())
    ec_key_der = ec_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Use TestTSAAuthority with ec leaf_key_type so the leaf cert has EC key.
    # Then we embed the EC leaf cert as the responder cert — the check at line 142
    # will fire because the embedded cert's key is EC, not RSA.
    authority = TestTSAAuthority(now=_NOW, leaf_key_type="ec")
    real_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    serial = _serial_of_leaf(authority)

    resp = asn1_ocsp.OCSPResponse.load(real_der)
    basic = resp["response_bytes"]["response"].parsed

    # Embed the EC leaf cert as the responder cert to trigger the non-RSA branch.
    leaf_asn1 = asn1_x509.Certificate.load(authority.materials().leaf_cert_der)
    new_basic = asn1_ocsp.BasicOCSPResponse(
        {
            "tbs_response_data": basic["tbs_response_data"],
            "signature_algorithm": basic["signature_algorithm"],
            "signature": basic["signature"],
            "certs": [leaf_asn1],
        }
    )
    new_resp = asn1_ocsp.OCSPResponse(
        {
            "response_status": "successful",
            "response_bytes": asn1_ocsp.ResponseBytes(
                {
                    "response_type": "basic_ocsp_response",
                    "response": core.ParsableOctetString(new_basic.dump()),
                }
            ),
        }
    )
    with pytest.raises(AnchorVerificationError, match="RSA OCSP signer keys"):
        parse_and_verify_ocsp(
            new_resp.dump(),
            expected_serial=serial,
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )


# --- Lines 175-179: unknown cert_status branch --------------------------------


def _build_ocsp_with_unknown_status(authority: TestTSAAuthority) -> bytes:
    """Build a real OCSP response with 'unknown' cert_status."""
    from hashlib import sha1

    issuer_der = authority.materials().root_cert_der
    issuer_asn1 = asn1_x509.Certificate.load(issuer_der)
    leaf_asn1 = asn1_x509.Certificate.load(authority.materials().leaf_cert_der)

    issuer_name_hash = sha1(issuer_asn1["tbs_certificate"]["subject"].dump()).digest()
    spki = issuer_asn1["tbs_certificate"]["subject_public_key_info"]
    bit_bytes = spki["public_key"].contents
    if bit_bytes and bit_bytes[0] == 0:
        bit_bytes = bit_bytes[1:]
    issuer_key_hash = sha1(bit_bytes).digest()

    cert_id = asn1_ocsp.CertId(
        {
            "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha1"}),
            "issuer_name_hash": issuer_name_hash,
            "issuer_key_hash": issuer_key_hash,
            "serial_number": leaf_asn1.serial_number,
        }
    )
    # unknown status
    cert_status = asn1_ocsp.CertStatus({"unknown": core.Null()})
    single_response = asn1_ocsp.SingleResponse(
        {
            "cert_id": cert_id,
            "cert_status": cert_status,
            "this_update": _NOW,
            "next_update": _NOW + timedelta(days=7),
        }
    )
    tbs = asn1_ocsp.ResponseData(
        {
            "responder_id": asn1_ocsp.ResponderId(
                name="by_name",
                value=issuer_asn1["tbs_certificate"]["subject"],
            ),
            "produced_at": _NOW,
            "responses": [single_response],
        }
    )
    tbs_der = tbs.dump()
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding as asym_padding

    # Load the root private key — we need it to sign. Get it from a fresh authority
    # built the same way (root key is not exposed). We must use the authority's
    # internal root key by creating the response through a patched path.
    # Instead: build a new authority and use its _root_key directly.
    # Since TestTSAAuthority exposes _root_key we can access it.
    root_key = authority._root_key  # noqa: SLF001 (private access intentional in test)
    signature = root_key.sign(tbs_der, asym_padding.PKCS1v15(), hashes.SHA256())

    basic_response = asn1_ocsp.BasicOCSPResponse(
        {
            "tbs_response_data": tbs,
            "signature_algorithm": algos.SignedDigestAlgorithm({"algorithm": "rsassa_pkcs1v15"}),
            "signature": signature,
        }
    )
    full = asn1_ocsp.OCSPResponse(
        {
            "response_status": "successful",
            "response_bytes": asn1_ocsp.ResponseBytes(
                {
                    "response_type": "basic_ocsp_response",
                    "response": core.ParsableOctetString(basic_response.dump()),
                }
            ),
        }
    )
    der: bytes = full.dump()
    return der


def test_ocsp_unknown_cert_status() -> None:
    """Lines 175-179: cert_status == 'unknown' returns ParsedOcsp with cert_status='unknown'."""
    authority = TestTSAAuthority(now=_NOW)
    serial = _serial_of_leaf(authority)
    der = _build_ocsp_with_unknown_status(authority)
    parsed = parse_and_verify_ocsp(
        der,
        expected_serial=serial,
        issuer_cert_der=authority.materials().root_cert_der,
        verification_time=_NOW,
    )
    assert parsed.cert_status == "unknown"
    assert parsed.revocation_time is None


# --- Lines 183, 187, 191, 195: naive datetime tz fixup branches ---------------
# These fire when the datetime fields from the ASN.1 structure have no tzinfo.
# We mock OCSPResponse.load to return controlled objects with naive datetimes.


def _make_mock_resp(
    basic_obj: Any,
    *,
    this_update: datetime,
    next_update: datetime | None,
    produced_at: datetime,
) -> MagicMock:
    """Build a minimal mock OCSPResponse for patching OCSPResponse.load."""
    mock_this_update = MagicMock()
    mock_this_update.native = this_update

    mock_next_update = MagicMock()
    mock_next_update.native = next_update

    mock_produced_at = MagicMock()
    mock_produced_at.native = produced_at

    mock_single = MagicMock()
    mock_single.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "cert_id": basic_obj["tbs_response_data"]["responses"][0]["cert_id"],
            "cert_status": basic_obj["tbs_response_data"]["responses"][0]["cert_status"],
            "this_update": mock_this_update,
            "next_update": mock_next_update,
        }[k]
    )

    mock_tbs = MagicMock()
    tbs_dump: bytes = basic_obj["tbs_response_data"].dump()
    mock_tbs.dump.return_value = tbs_dump
    mock_tbs.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "responses": [mock_single],
            "produced_at": mock_produced_at,
        }[k]
    )

    mock_basic = MagicMock()
    mock_basic.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "tbs_response_data": mock_tbs,
            "signature": basic_obj["signature"],
            "signature_algorithm": basic_obj["signature_algorithm"],
            "certs": None,
        }[k]
    )

    mock_rb = MagicMock()
    mock_rb.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "response_type": MagicMock(native="basic_ocsp_response"),
            "response": MagicMock(parsed=mock_basic),
        }[k]
    )

    mock_resp = MagicMock()
    mock_resp.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "response_status": MagicMock(native="successful"),
            "response_bytes": mock_rb,
        }[k]
    )
    return mock_resp


def test_ocsp_this_update_naive_gets_utc_fixed() -> None:
    """Line 183: this_update without tzinfo gets UTC attached."""
    from unittest.mock import patch as mock_patch

    authority = TestTSAAuthority(now=_NOW)
    serial = _serial_of_leaf(authority)
    real_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    resp_obj = asn1_ocsp.OCSPResponse.load(real_der)
    basic_obj = resp_obj["response_bytes"]["response"].parsed

    mock_resp = _make_mock_resp(
        basic_obj,
        this_update=_NOW.replace(tzinfo=None),  # naive -> triggers line 183
        next_update=(_NOW + timedelta(days=7)).replace(tzinfo=None),  # naive -> triggers 191
        produced_at=_NOW,  # tz-aware -> doesn't trigger 195
    )

    with mock_patch.object(asn1_ocsp.OCSPResponse, "load", return_value=mock_resp):
        parsed = parse_and_verify_ocsp(
            real_der,
            expected_serial=serial,
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )
    assert parsed.this_update.tzinfo is not None
    assert parsed.next_update is not None
    assert parsed.next_update.tzinfo is not None


def test_ocsp_next_update_none_branch() -> None:
    """Lines 186-187: next_update field is None => next_update=None."""
    from unittest.mock import patch as mock_patch

    authority = TestTSAAuthority(now=_NOW)
    serial = _serial_of_leaf(authority)
    real_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    resp_obj = asn1_ocsp.OCSPResponse.load(real_der)
    basic_obj = resp_obj["response_bytes"]["response"].parsed

    mock_resp = _make_mock_resp(
        basic_obj,
        this_update=_NOW,
        next_update=None,  # triggers the None branch (line 187)
        produced_at=_NOW,
    )

    with mock_patch.object(asn1_ocsp.OCSPResponse, "load", return_value=mock_resp):
        parsed = parse_and_verify_ocsp(
            real_der,
            expected_serial=serial,
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )
    assert parsed.next_update is None


def test_ocsp_produced_at_naive_gets_utc_fixed() -> None:
    """Line 195: produced_at without tzinfo gets UTC attached."""
    from unittest.mock import patch as mock_patch

    authority = TestTSAAuthority(now=_NOW)
    serial = _serial_of_leaf(authority)
    real_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    resp_obj = asn1_ocsp.OCSPResponse.load(real_der)
    basic_obj = resp_obj["response_bytes"]["response"].parsed

    mock_resp = _make_mock_resp(
        basic_obj,
        this_update=_NOW,
        next_update=_NOW + timedelta(days=7),
        produced_at=_NOW.replace(tzinfo=None),  # naive -> triggers line 195
    )

    with mock_patch.object(asn1_ocsp.OCSPResponse, "load", return_value=mock_resp):
        parsed = parse_and_verify_ocsp(
            real_der,
            expected_serial=serial,
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )
    assert parsed.produced_at.tzinfo is not None


def test_ocsp_verification_time_defaults_to_now() -> None:
    """Ensure verification_time=None uses datetime.now(UTC) — covers the 'or' branch."""
    authority = TestTSAAuthority(now=_NOW)
    serial = _serial_of_leaf(authority)
    # Issue with now+past so it will be fresh against wall-clock.
    # Deliberately NOT passing verification_time to exercise the default path.
    gen_time = datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=5)
    ocsp_der = authority.issue_real_ocsp_response(gen_time=gen_time)
    # serial is from _NOW-keyed authority; actual serial from this authority
    parsed = parse_and_verify_ocsp(
        ocsp_der,
        expected_serial=serial,
        issuer_cert_der=authority.materials().root_cert_der,
        # no verification_time — uses now()
    )
    assert parsed.cert_status == "good"


# --- Line 134: embedded cert is not a Certificate instance --------------------


def test_ocsp_rejects_non_certificate_embedded_cert() -> None:
    """Line 134: embedded certs[0] is not an asn1_x509.Certificate raises error."""
    authority = TestTSAAuthority(now=_NOW)
    real_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    serial = _serial_of_leaf(authority)

    resp_obj = asn1_ocsp.OCSPResponse.load(real_der)
    basic_obj = resp_obj["response_bytes"]["response"].parsed

    # Build a fake embedded certs list where [0] is NOT an asn1_x509.Certificate.
    # We use a MagicMock that is not an instance of asn1_x509.Certificate.
    not_a_cert = MagicMock(spec=object)  # not an asn1_x509.Certificate
    # Ensure isinstance check fails.
    assert not isinstance(not_a_cert, asn1_x509.Certificate)

    mock_certs = [not_a_cert]

    mock_basic = MagicMock()
    mock_basic.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "tbs_response_data": basic_obj["tbs_response_data"],
            "signature": basic_obj["signature"],
            "signature_algorithm": basic_obj["signature_algorithm"],
            "certs": mock_certs,
        }[k]
    )

    mock_rb = MagicMock()
    mock_rb.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "response_type": MagicMock(native="basic_ocsp_response"),
            "response": MagicMock(parsed=mock_basic),
        }[k]
    )

    mock_resp = MagicMock()
    mock_resp.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "response_status": MagicMock(native="successful"),
            "response_bytes": mock_rb,
        }[k]
    )

    from unittest.mock import patch as mock_patch

    with mock_patch.object(asn1_ocsp.OCSPResponse, "load", return_value=mock_resp), pytest.raises(
        AnchorVerificationError, match="first OCSP-embedded cert is not a Certificate"
    ):
        parse_and_verify_ocsp(
            real_der,
            expected_serial=serial,
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )


# --- Line 179: unexpected cert_status name -----------------------------------


def test_ocsp_unexpected_cert_status_raises() -> None:
    """Line 179: cert_status name is not good/revoked/unknown raises AnchorVerificationError."""
    authority = TestTSAAuthority(now=_NOW)
    real_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    serial = _serial_of_leaf(authority)

    resp_obj = asn1_ocsp.OCSPResponse.load(real_der)
    basic_obj = resp_obj["response_bytes"]["response"].parsed

    # Mock cert_status with an unexpected name.
    mock_cert_status = MagicMock()
    mock_cert_status.name = "superseded"  # not good/revoked/unknown

    mock_this_update = MagicMock()
    mock_this_update.native = _NOW

    mock_next_update = MagicMock()
    mock_next_update.native = _NOW + timedelta(days=7)

    mock_single = MagicMock()
    mock_single.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "cert_id": basic_obj["tbs_response_data"]["responses"][0]["cert_id"],
            "cert_status": mock_cert_status,
            "this_update": mock_this_update,
            "next_update": mock_next_update,
        }[k]
    )

    mock_tbs = MagicMock()
    mock_tbs.dump.return_value = basic_obj["tbs_response_data"].dump()
    mock_tbs.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "responses": [mock_single],
            "produced_at": MagicMock(native=_NOW),
        }[k]
    )

    mock_basic = MagicMock()
    mock_basic.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "tbs_response_data": mock_tbs,
            "signature": basic_obj["signature"],
            "signature_algorithm": basic_obj["signature_algorithm"],
            "certs": None,
        }[k]
    )

    mock_rb = MagicMock()
    mock_rb.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "response_type": MagicMock(native="basic_ocsp_response"),
            "response": MagicMock(parsed=mock_basic),
        }[k]
    )

    mock_resp = MagicMock()
    mock_resp.__getitem__ = MagicMock(
        side_effect=lambda k: {
            "response_status": MagicMock(native="successful"),
            "response_bytes": mock_rb,
        }[k]
    )

    from unittest.mock import patch as mock_patch

    with mock_patch.object(asn1_ocsp.OCSPResponse, "load", return_value=mock_resp), pytest.raises(
        AnchorVerificationError, match="unexpected OCSP cert_status"
    ):
        parse_and_verify_ocsp(
            real_der,
            expected_serial=serial,
            issuer_cert_der=authority.materials().root_cert_der,
            verification_time=_NOW,
        )
