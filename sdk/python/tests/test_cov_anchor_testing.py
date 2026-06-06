# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-completion tests for attestplane.anchoring.testing.

Targets the missing lines/branches reported in the 88% baseline:
  104, 199, 201, 203, 339, 363, 394->396, 597-600, 610-611, 615, 622, 625,
  673, 676, 688
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring import AnchorVerificationError, TimestampRequest, TSAUnavailableError
from attestplane.anchoring.testing import (
    TestTSAAuthority,
    TestTSAProvider,
    _digest,
    _hash_algorithm,
    _sha256,
)

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


# --- Line 104: invalid leaf_key_type -----------------------------------------


def test_authority_rejects_invalid_leaf_key_type() -> None:
    """Line 104: leaf_key_type not in ('rsa', 'ec') raises ValueError."""
    with pytest.raises(ValueError, match="leaf_key_type must be 'rsa' or 'ec'"):
        TestTSAAuthority(now=_NOW, leaf_key_type="dsa")


# --- Lines 199, 201: sign_timestamp_response validation ----------------------


def test_sign_timestamp_rejects_wrong_digest_length() -> None:
    """Line 199: request_digest != 32 bytes raises ValueError."""
    authority = TestTSAAuthority(now=_NOW)
    with pytest.raises(ValueError, match="32 bytes"):
        authority.sign_timestamp_response(b"\x00" * 16, gen_time=_NOW)


def test_sign_timestamp_rejects_naive_gen_time() -> None:
    """Line 201: gen_time with no tzinfo raises ValueError."""
    authority = TestTSAAuthority(now=_NOW)
    naive = datetime(2026, 5, 17, 12, 0, 0)  # no tzinfo
    with pytest.raises(ValueError, match="UTC-aware"):
        authority.sign_timestamp_response(b"\x00" * 32, gen_time=naive)


def test_sign_timestamp_rejects_non_utc_tz_gen_time() -> None:
    """Line 201: gen_time with non-UTC tzinfo raises ValueError."""
    from datetime import timezone

    authority = TestTSAAuthority(now=_NOW)
    non_utc = datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
    with pytest.raises(ValueError, match="UTC-aware"):
        authority.sign_timestamp_response(b"\x00" * 32, gen_time=non_utc)


# --- Line 203: unsupported signer_digest_algorithm ---------------------------


def test_sign_timestamp_rejects_unsupported_algorithm() -> None:
    """Line 203: signer_digest_algorithm not in set raises ValueError."""
    authority = TestTSAAuthority(now=_NOW)
    with pytest.raises(ValueError, match="unsupported signer_digest_algorithm"):
        authority.sign_timestamp_response(
            b"\x00" * 32,
            gen_time=_NOW,
            signer_digest_algorithm="md5",  # type: ignore[arg-type]
        )


# --- sign_timestamp with sha384 and sha512 (EC and RSA) ----------------------


def test_sign_timestamp_sha384() -> None:
    """Covers sha384 path in sign_timestamp_response and _digest/_hash_algorithm."""
    authority = TestTSAAuthority(now=_NOW)
    der = authority.sign_timestamp_response(
        b"\x00" * 32,
        gen_time=_NOW,
        signer_digest_algorithm="sha384",
    )
    assert isinstance(der, bytes)
    assert len(der) > 0


def test_sign_timestamp_sha512() -> None:
    """Covers sha512 path in sign_timestamp_response and _digest/_hash_algorithm."""
    authority = TestTSAAuthority(now=_NOW)
    der = authority.sign_timestamp_response(
        b"\x00" * 32,
        gen_time=_NOW,
        signer_digest_algorithm="sha512",
    )
    assert isinstance(der, bytes)
    assert len(der) > 0


def test_sign_timestamp_with_nonce() -> None:
    """Exercises the nonce path in sign_timestamp_response."""
    authority = TestTSAAuthority(now=_NOW)
    der = authority.sign_timestamp_response(
        b"\x00" * 32,
        gen_time=_NOW,
        nonce=b"testnonce",
    )
    assert isinstance(der, bytes)


def test_sign_timestamp_ec_leaf_sha256() -> None:
    """Exercises the EC leaf key branch in sign_timestamp_response."""
    authority = TestTSAAuthority(now=_NOW, leaf_key_type="ec")
    der = authority.sign_timestamp_response(
        b"\xab" * 32,
        gen_time=_NOW,
        signer_digest_algorithm="sha256",
    )
    assert isinstance(der, bytes)


def test_sign_timestamp_ec_leaf_sha384() -> None:
    """Exercises the EC leaf key + sha384 combo."""
    authority = TestTSAAuthority(now=_NOW, leaf_key_type="ec")
    der = authority.sign_timestamp_response(
        b"\xcd" * 32,
        gen_time=_NOW,
        signer_digest_algorithm="sha384",
    )
    assert isinstance(der, bytes)


# --- Line 339: issue_ocsp_response with naive gen_time -----------------------


def test_issue_ocsp_response_rejects_naive_gen_time() -> None:
    """Line 339: gen_time without tzinfo raises ValueError."""
    authority = TestTSAAuthority(now=_NOW)
    naive = datetime(2026, 5, 17, 12, 0, 0)  # no tzinfo
    with pytest.raises(ValueError, match="UTC-aware"):
        authority.issue_ocsp_response(gen_time=naive)


# --- Line 363: issue_real_ocsp_response with naive gen_time ------------------


def test_issue_real_ocsp_response_rejects_naive_gen_time() -> None:
    """Line 363: gen_time without tzinfo raises ValueError."""
    authority = TestTSAAuthority(now=_NOW)
    naive = datetime(2026, 5, 17, 12, 0, 0)  # no tzinfo
    with pytest.raises(ValueError, match="UTC-aware"):
        authority.issue_real_ocsp_response(gen_time=naive)


# --- Lines 394->396: bit_string_bytes stripping branch -----------------------
# This fires when the leading byte of spki["public_key"].contents is 0x00.
# For RSA keys this is always true (the BITSTRING unused-bits prefix is 0x00).
# The existing tests already exercise the RSA path. But the branch 394->396
# specifically means the `if bit_string_bytes and bit_string_bytes[0] == 0`
# condition evaluated False (no stripping). We need a case where it's empty
# or the first byte is NOT 0x00. We can test by verifying the normal path
# runs without errors, which exercises the True branch (394->396 means we
# fall through to 396, i.e., the if was True and we stripped).
# The baseline report shows this as partially covered (394->396 is a branch
# meaning: when condition is True, goes to 396).
# A standard RSA key always has 0x00 prefix so the True branch is taken.
# We need to cover the False branch (first byte != 0x00 OR empty).
# We patch the spki contents to not start with 0x00.


def test_issue_real_ocsp_response_with_intermediate_chain() -> None:
    """Lines 376-378: intermediate chain path in issue_real_ocsp_response."""
    authority = TestTSAAuthority(now=_NOW, intermediate_count=1)
    from asn1crypto import x509 as asn1_x509

    leaf_asn1 = asn1_x509.Certificate.load(authority.materials().leaf_cert_der)
    serial = int(leaf_asn1.serial_number)

    from attestplane.anchoring.ocsp import parse_and_verify_ocsp

    # The intermediate signed the leaf, so use the intermediate as issuer cert.
    intermediate_der = authority.materials().intermediate_certs_der[0]
    ocsp_der = authority.issue_real_ocsp_response(gen_time=_NOW)
    parsed = parse_and_verify_ocsp(
        ocsp_der,
        expected_serial=serial,
        issuer_cert_der=intermediate_der,
        verification_time=_NOW,
    )
    assert parsed.cert_status == "good"


def test_issue_real_ocsp_response_bit_string_no_strip_branch() -> None:
    """Line 394->396 False branch: bit_string leading byte != 0x00.

    The condition `if bit_string_bytes and bit_string_bytes[0] == 0` is False
    when contents starts with a non-zero byte. We mock Certificate.load to
    return an object whose public_key.contents starts with 0x01.
    """
    from unittest.mock import MagicMock, patch

    authority = TestTSAAuthority(now=_NOW)

    from asn1crypto import x509 as asn1_x509

    import attestplane.anchoring.testing as tm

    orig_sha1 = tm._sha1

    # We intercept at the point where asn1_x509.Certificate.load is called
    # for the issuer cert inside issue_real_ocsp_response, replacing the
    # public_key.contents with bytes that start with 0x01 (no strip needed).
    original_load = asn1_x509.Certificate.load
    load_call_count = [0]

    def patched_load(data: bytes) -> asn1_x509.Certificate:
        cert = original_load(data)
        load_call_count[0] += 1
        if load_call_count[0] == 2:
            # This is the issuer_asn1 load call. Wrap it so contents != 0x00.
            real_spki = cert["tbs_certificate"]["subject_public_key_info"]
            real_pk = real_spki["public_key"]
            # Get the real contents (starts with 0x00).
            real_contents = real_pk.contents
            # Patch the public_key object's .contents to return bytes starting
            # with 0x01 instead of 0x00 (simulates the no-strip branch).
            fake_pk = MagicMock()
            fake_pk.contents = b"\x01" + real_contents[1:]  # non-zero prefix

            fake_spki = MagicMock()
            fake_spki.__getitem__ = MagicMock(
                side_effect=lambda k: fake_pk if k == "public_key" else real_spki[k]
            )

            fake_tbs = MagicMock()
            real_tbs = cert["tbs_certificate"]
            fake_tbs.__getitem__ = MagicMock(
                side_effect=lambda k: fake_spki if k == "subject_public_key_info" else real_tbs[k]
            )

            wrapper = MagicMock(spec=asn1_x509.Certificate)
            wrapper.__getitem__ = MagicMock(
                side_effect=lambda k: fake_tbs if k == "tbs_certificate" else cert[k]
            )
            wrapper.serial_number = cert.serial_number
            wrapper.dump = cert.dump
            return wrapper
        return cert

    with patch.object(asn1_x509.Certificate, "load", side_effect=patched_load):
        # Should not crash — just skip the strip since byte[0] != 0.
        ocsp_bytes = authority.issue_real_ocsp_response(gen_time=_NOW)
    assert isinstance(ocsp_bytes, bytes)
    assert len(ocsp_bytes) > 0


# --- Lines 597-600: _sha256 function -----------------------------------------


def test_sha256_helper() -> None:
    """Lines 597-600: _sha256 returns correct SHA-256 digest."""
    from hashlib import sha256

    data = b"hello attestplane"
    result = _sha256(data)
    assert result == sha256(data).digest()
    assert len(result) == 32


# --- Lines 610-611, 615: _digest sha384 and sha512 + fallback ----------------


def test_digest_sha256() -> None:
    """_digest with sha256."""
    from hashlib import sha256

    data = b"test"
    assert _digest(data, "sha256") == sha256(data).digest()


def test_digest_sha384() -> None:
    """Lines 610-611: _digest with sha384."""
    from hashlib import sha384

    data = b"test"
    assert _digest(data, "sha384") == sha384(data).digest()


def test_digest_sha512() -> None:
    """Lines 613-614: _digest with sha512."""
    from hashlib import sha512

    data = b"test"
    assert _digest(data, "sha512") == sha512(data).digest()


def test_digest_unsupported_raises() -> None:
    """Line 615: _digest with unsupported algorithm raises ValueError."""
    with pytest.raises(ValueError, match="unsupported digest algorithm"):
        _digest(b"test", "md5")


# --- Lines 622, 625: _hash_algorithm sha384 and sha512 + fallback ------------


def test_hash_algorithm_sha256() -> None:
    """_hash_algorithm with sha256 returns SHA256 instance."""
    from cryptography.hazmat.primitives import hashes

    result = _hash_algorithm("sha256")
    assert isinstance(result, hashes.SHA256)


def test_hash_algorithm_sha384() -> None:
    """Line 622: _hash_algorithm with sha384 returns SHA384 instance."""
    from cryptography.hazmat.primitives import hashes

    result = _hash_algorithm("sha384")
    assert isinstance(result, hashes.SHA384)


def test_hash_algorithm_sha512() -> None:
    """Line 624: _hash_algorithm with sha512 returns SHA512 instance."""
    from cryptography.hazmat.primitives import hashes

    result = _hash_algorithm("sha512")
    assert isinstance(result, hashes.SHA512)


def test_hash_algorithm_unsupported_raises() -> None:
    """Line 625: _hash_algorithm with unsupported algorithm raises ValueError."""
    with pytest.raises(ValueError, match="unsupported digest algorithm"):
        _hash_algorithm("md5")


# --- TestTSAProvider lines 673, 676, 688 ------------------------------------


def test_tsa_provider_raises_when_fail_with_set() -> None:
    """Line 673: fail_with is set, raises that exception."""
    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority, fail_with=TSAUnavailableError("oops"))
    with pytest.raises(TSAUnavailableError, match="oops"):
        provider.request_timestamp(TimestampRequest(digest=b"\x00" * 32))


def test_tsa_provider_rejects_empty_nonce() -> None:
    """Line 676: request.nonce is empty raises AnchorVerificationError."""
    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority)
    req = TimestampRequest(digest=b"\x00" * 32, nonce=b"")
    with pytest.raises(AnchorVerificationError, match="nonce must be non-empty"):
        provider.request_timestamp(req)


def test_tsa_provider_legacy_synthetic_ocsp_mode() -> None:
    """Line 688: ocsp_mode='legacy_synthetic' uses issue_ocsp_response."""
    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority, ocsp_mode="legacy_synthetic")
    anchor = provider.request_timestamp(
        TimestampRequest(digest=b"\xaa" * 32),
        now=_NOW,
    )
    # The ocsp_response in legacy mode starts with the synthetic marker.
    assert anchor.ocsp_responses[0].startswith(b"ATTESTPLANE-TEST-OCSP-V1|")


def test_tsa_provider_real_ocsp_mode() -> None:
    """Line 685-686: ocsp_mode='real' (default) uses issue_real_ocsp_response."""
    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority, ocsp_mode="real")
    anchor = provider.request_timestamp(
        TimestampRequest(digest=b"\xbb" * 32),
        now=_NOW,
    )
    # Real OCSP response is DER, starts with 0x30 (SEQUENCE tag).
    assert anchor.ocsp_responses[0][0:1] == b"\x30"


def test_tsa_provider_naive_now_raises() -> None:
    """Line 676 (gen_time.tzinfo is None): naive now raises TSAUnavailableError."""

    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority)
    # Inject a naive datetime via the 'now' parameter.
    # But gen_time = (now or datetime.now(UTC)).replace(microsecond=0)
    # So if we pass a naive 'now', it will be used. However the type annotation
    # doesn't guard against it. Let's pass a naive now.
    naive_now = datetime(2026, 5, 17, 12, 0, 0)  # no tzinfo
    # The .replace(microsecond=0) keeps it naive.
    # gen_time.tzinfo is None => raises TSAUnavailableError
    with pytest.raises(TSAUnavailableError, match="UTC-aware"):
        provider.request_timestamp(
            TimestampRequest(digest=b"\xcc" * 32),
            now=naive_now,
        )


# --- TestTSAAuthority with intermediate_count > 0 (lines 124-136) ----------


def test_authority_with_intermediates_materials() -> None:
    """Lines 124-136: intermediate CA generation loop."""
    authority = TestTSAAuthority(now=_NOW, intermediate_count=2)
    materials = authority.materials()
    assert len(materials.intermediate_certs_der) == 2
    # Each intermediate is a valid DER cert.
    from asn1crypto import x509 as asn1_x509

    for cert_der in materials.intermediate_certs_der:
        cert = asn1_x509.Certificate.load(cert_der)
        cn = cert["tbs_certificate"]["subject"].human_friendly
        assert "Intermediate" in cn


def test_authority_now_defaults_to_utc() -> None:
    """Line 105: now=None defaults to datetime.now(UTC)."""
    # Verify the authority initializes without error when now=None.
    authority = TestTSAAuthority()
    materials = authority.materials()
    assert materials.root_cert_der is not None
    assert materials.leaf_cert_der is not None


def test_authority_ec_leaf_materials() -> None:
    """Lines 142-143: EC leaf key branch in __init__."""
    authority = TestTSAAuthority(now=_NOW, leaf_key_type="ec")
    materials = authority.materials()
    # The leaf key DER should be a valid EC private key.
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
    from cryptography.hazmat.primitives.serialization import load_der_private_key

    key = load_der_private_key(materials.leaf_key_der, password=None)
    assert isinstance(key, EllipticCurvePrivateKey)


def test_provider_id_uses_common_name() -> None:
    """Line 661: provider_id is composed from authority.common_name."""
    authority = TestTSAAuthority(now=_NOW, common_name="My Custom TSA")
    provider = TestTSAProvider(authority)
    assert provider.provider_id == "test.tsa:My Custom TSA"


def test_tsa_provider_serial_increments() -> None:
    """Verify _serial increments across calls (covers _serial += 1 path)."""
    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority)
    anchor1 = provider.request_timestamp(TimestampRequest(digest=b"\x00" * 32), now=_NOW)
    anchor2 = provider.request_timestamp(TimestampRequest(digest=b"\x00" * 32), now=_NOW)
    # Both succeed; serial incremented internally.
    assert anchor1.tsa_token != anchor2.tsa_token  # different serials → different tokens


# --- Line 408: issue_real_ocsp_response revoked=True branch ------------------


def test_issue_real_ocsp_response_revoked_branch() -> None:
    """Line 408: revoked=True builds a revoked CertStatus."""
    authority = TestTSAAuthority(now=_NOW)
    ocsp_der = authority.issue_real_ocsp_response(gen_time=_NOW, revoked=True)
    assert isinstance(ocsp_der, bytes)
    # Verify the result is a real parseable OCSP response with revoked status.
    from asn1crypto import ocsp as asn1_ocsp

    resp = asn1_ocsp.OCSPResponse.load(ocsp_der)
    basic = resp["response_bytes"]["response"].parsed
    single = basic["tbs_response_data"]["responses"][0]
    assert single["cert_status"].name == "revoked"


# --- Lines 723-789: TestRekorAuthority ---------------------------------------


def test_rekor_authority_init_and_properties() -> None:
    """Lines 723-730, 734, 738, 742: TestRekorAuthority construction and properties."""
    from attestplane.anchoring.testing import TestRekorAuthority

    authority = TestRekorAuthority(log_id="test.log.id", now=_NOW)
    assert authority.log_id == "test.log.id"
    assert authority.public_key is not None
    assert isinstance(authority.public_key_der, bytes)
    assert len(authority.public_key_der) > 0


def test_rekor_authority_issue_log_entry() -> None:
    """Lines 763-789: issue_log_entry returns valid JSON with SET signature."""
    import base64
    import json

    from attestplane.anchoring.testing import TestRekorAuthority

    authority = TestRekorAuthority(log_id="my.test.log", now=_NOW)
    body = b'{"kind":"hashedrekord","apiVersion":"0.0.1","spec":{}}'
    entry_bytes = authority.issue_log_entry(body, now=_NOW)

    entry = json.loads(entry_bytes)
    assert entry["logID"] == "my.test.log"
    assert entry["logIndex"] == 1
    assert "verification" in entry
    assert "signedEntryTimestamp" in entry["verification"]
    # Verify the SET signature with the public key.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    pub_key = authority.public_key
    assert isinstance(pub_key, Ed25519PublicKey)

    set_sig = base64.standard_b64decode(entry["verification"]["signedEntryTimestamp"])
    set_payload = {
        "body": entry["body"],
        "integratedTime": entry["integratedTime"],
        "logID": entry["logID"],
        "logIndex": entry["logIndex"],
    }
    set_payload_bytes = json.dumps(set_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    # Should not raise.
    pub_key.verify(set_sig, set_payload_bytes)


def test_rekor_authority_issue_log_entry_no_fixed_time() -> None:
    """Line 766: now=None, _fixed_time=None → uses datetime.now(UTC)."""
    import json

    from attestplane.anchoring.testing import TestRekorAuthority

    # No now in constructor, no now in issue_log_entry → uses datetime.now(UTC).
    authority = TestRekorAuthority()
    body = b"test-body"
    entry_bytes = authority.issue_log_entry(body)
    entry = json.loads(entry_bytes)
    assert entry["logIndex"] == 1
    assert entry["integratedTime"] > 0


def test_rekor_authority_issue_log_entry_fixed_time_fallback() -> None:
    """Line 766: now=None but _fixed_time is set → uses _fixed_time."""
    import json

    from attestplane.anchoring.testing import TestRekorAuthority

    authority = TestRekorAuthority(now=_NOW)
    body = b"test-body-fixed-time"
    entry_bytes = authority.issue_log_entry(body)
    entry = json.loads(entry_bytes)
    assert entry["integratedTime"] == int(_NOW.timestamp())


def test_rekor_authority_increments_index() -> None:
    """Line 768: _index increments across issue_log_entry calls."""
    import json

    from attestplane.anchoring.testing import TestRekorAuthority

    authority = TestRekorAuthority(now=_NOW)
    body = b"entry-body"
    e1 = json.loads(authority.issue_log_entry(body, now=_NOW))
    e2 = json.loads(authority.issue_log_entry(body, now=_NOW))
    assert e2["logIndex"] == e1["logIndex"] + 1
