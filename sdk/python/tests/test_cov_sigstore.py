# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""Coverage-completion tests for attestplane.anchoring.sigstore (≥98%)."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from attestplane.anchoring.base import (
    AnchorVerificationError,
    TimestampRequest,
    TSAUnavailableError,
)
from attestplane.anchoring.http import RecordedHttpTransport
from attestplane.anchoring.sigstore import (
    ParsedRekorEntry,
    SigstoreRekorAnchor,
    _set_payload,
    is_sigstore_rekor_anchor,
    parse_rekor_log_entry,
    verify_rekor_signed_entry_timestamp,
)
from attestplane.anchoring.testing import TestRekorAuthority

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_log_entry(
    digest: bytes,
    *,
    authority: TestRekorAuthority | None = None,
    signing_key: Ed25519PrivateKey | None = None,
) -> bytes:
    """Return a valid Rekor LogEntry JSON bytes via TestRekorAuthority."""
    if authority is None:
        authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    if signing_key is None:
        signing_key = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization

    signature = signing_key.sign(digest)
    pubkey_der = signing_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    body = {
        "spec": {
            "content": {
                "hash": {"algorithm": "sha256", "value": digest.hex()},
                "publicKey": {"content": base64.standard_b64encode(pubkey_der).decode("ascii")},
                "signature": {"content": base64.standard_b64encode(signature).decode("ascii")},
            }
        }
    }
    body_bytes = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return authority.issue_log_entry(body_bytes, now=_NOW)


def _make_parsed(body_bytes: bytes, *, authority: TestRekorAuthority | None = None) -> ParsedRekorEntry:
    """Issue a log entry and parse it."""
    if authority is None:
        authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    entry_bytes = authority.issue_log_entry(body_bytes, now=_NOW)
    return parse_rekor_log_entry(entry_bytes)


# ---------------------------------------------------------------------------
# SigstoreRekorAnchor — transport raises TSAUnavailableError (lines 177-178)
# ---------------------------------------------------------------------------

def test_request_timestamp_propagates_tsa_unavailable() -> None:
    """Lines 177-178: TSAUnavailableError from transport is re-raised as-is."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()

    class FailingTransport(RecordedHttpTransport):
        def __init__(self) -> None:
            super().__init__(b"")

        def submit(self, url: str, request_der: bytes, *, timeout_seconds: float = 30.0) -> bytes:
            raise TSAUnavailableError("network error in test")

    provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id="test.rekor",
        signing_key=signing_key,
        transport=FailingTransport(),
    )
    with pytest.raises(TSAUnavailableError, match="network error in test"):
        provider.request_timestamp(TimestampRequest(digest=hashlib.sha256(b"x").digest()))


# ---------------------------------------------------------------------------
# SigstoreRekorAnchor — non-JSON response (lines 182-183)
# ---------------------------------------------------------------------------

def test_request_timestamp_non_json_response() -> None:
    """Lines 182-183: non-JSON response raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    transport = RecordedHttpTransport(b"not valid json!!!")

    provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id="test.rekor",
        signing_key=signing_key,
        transport=transport,
    )
    with pytest.raises(AnchorVerificationError, match="non-JSON"):
        provider.request_timestamp(TimestampRequest(digest=hashlib.sha256(b"x").digest()))


# ---------------------------------------------------------------------------
# SigstoreRekorAnchor — response is JSON but not an object (line 186)
# ---------------------------------------------------------------------------

def test_request_timestamp_json_array_response() -> None:
    """Line 186: JSON response that is not an object raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    transport = RecordedHttpTransport(b'["not", "an", "object"]')

    provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id="test.rekor",
        signing_key=signing_key,
        transport=transport,
    )
    with pytest.raises(AnchorVerificationError, match="not a JSON object"):
        provider.request_timestamp(TimestampRequest(digest=hashlib.sha256(b"x").digest()))


# ---------------------------------------------------------------------------
# SigstoreRekorAnchor — response missing required fields (line 188)
# ---------------------------------------------------------------------------

def test_request_timestamp_missing_fields() -> None:
    """Line 188: JSON object without logIndex/integratedTime raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    transport = RecordedHttpTransport(b'{"someField": 1}')

    provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id="test.rekor",
        signing_key=signing_key,
        transport=transport,
    )
    with pytest.raises(AnchorVerificationError, match="missing required fields"):
        provider.request_timestamp(TimestampRequest(digest=hashlib.sha256(b"x").digest()))


# ---------------------------------------------------------------------------
# SigstoreRekorAnchor — missing logIndex only (line 188 branch)
# ---------------------------------------------------------------------------

def test_request_timestamp_missing_log_index() -> None:
    """Line 188: Missing logIndex (has integratedTime) raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    payload = json.dumps({"integratedTime": 1716000000}).encode()
    transport = RecordedHttpTransport(payload)

    provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id="test.rekor",
        signing_key=signing_key,
        transport=transport,
    )
    with pytest.raises(AnchorVerificationError, match="missing required fields"):
        provider.request_timestamp(TimestampRequest(digest=hashlib.sha256(b"x").digest()))


# ---------------------------------------------------------------------------
# SigstoreRekorAnchor — missing integratedTime only (line 188 branch)
# ---------------------------------------------------------------------------

def test_request_timestamp_missing_integrated_time() -> None:
    """Line 188: Missing integratedTime (has logIndex) raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    payload = json.dumps({"logIndex": 42}).encode()
    transport = RecordedHttpTransport(payload)

    provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id="test.rekor",
        signing_key=signing_key,
        transport=transport,
    )
    with pytest.raises(AnchorVerificationError, match="missing required fields"):
        provider.request_timestamp(TimestampRequest(digest=hashlib.sha256(b"x").digest()))


# ---------------------------------------------------------------------------
# parse_rekor_log_entry — verification dict missing signedEntryTimestamp (line 231)
# ---------------------------------------------------------------------------

def test_parse_verification_missing_set() -> None:
    """Line 231: verification dict without signedEntryTimestamp raises AnchorVerificationError."""
    entry = {
        "logIndex": 1,
        "logID": "test",
        "integratedTime": 1716000000,
        "body": base64.standard_b64encode(b'{"spec":{}}').decode("ascii"),
        "verification": {"other": "value"},  # no signedEntryTimestamp
    }
    with pytest.raises(AnchorVerificationError, match="signedEntryTimestamp missing"):
        parse_rekor_log_entry(json.dumps(entry).encode())


# ---------------------------------------------------------------------------
# parse_rekor_log_entry — verification is not a dict (line 231)
# ---------------------------------------------------------------------------

def test_parse_verification_not_dict() -> None:
    """Line 231: verification that is not a dict raises AnchorVerificationError."""
    entry = {
        "logIndex": 1,
        "logID": "test",
        "integratedTime": 1716000000,
        "body": base64.standard_b64encode(b'{"spec":{}}').decode("ascii"),
        "verification": "not-a-dict",
    }
    with pytest.raises(AnchorVerificationError, match="signedEntryTimestamp missing"):
        parse_rekor_log_entry(json.dumps(entry).encode())


# ---------------------------------------------------------------------------
# parse_rekor_log_entry — invalid base64 for signedEntryTimestamp (lines 235-236)
# ---------------------------------------------------------------------------

def test_parse_invalid_set_base64() -> None:
    """Lines 235-236: bad base64 in signedEntryTimestamp raises AnchorVerificationError."""
    entry = {
        "logIndex": 1,
        "logID": "test",
        "integratedTime": 1716000000,
        "body": base64.standard_b64encode(b'{"spec":{}}').decode("ascii"),
        "verification": {"signedEntryTimestamp": "!!!not-valid-base64!!!"},
    }
    with pytest.raises(AnchorVerificationError, match="not valid base64"):
        parse_rekor_log_entry(json.dumps(entry).encode())


# ---------------------------------------------------------------------------
# parse_rekor_log_entry — invalid base64 for body (lines 240-241)
# ---------------------------------------------------------------------------

def test_parse_invalid_body_base64() -> None:
    """Lines 240-241: bad base64 in body raises AnchorVerificationError."""
    entry = {
        "logIndex": 1,
        "logID": "test",
        "integratedTime": 1716000000,
        "body": "!!!not-valid-base64!!!",
        "verification": {"signedEntryTimestamp": base64.standard_b64encode(b"fakesig").decode("ascii")},
    }
    with pytest.raises(AnchorVerificationError, match="not valid base64"):
        parse_rekor_log_entry(json.dumps(entry).encode())


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — body not valid JSON (lines 298-299)
# ---------------------------------------------------------------------------

def test_verify_body_not_json() -> None:
    """Lines 298-299: body_bytes is invalid JSON raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    # Issue an entry with non-JSON body bytes by constructing ParsedRekorEntry directly.
    # We need body_bytes = invalid JSON, but we still need valid structure for ParsedRekorEntry.
    # Use a properly structured log entry but with non-JSON in body field.
    bad_body_bytes = b"not-json!!!"
    set_bytes = b"\x00" * 64  # fake sig bytes

    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=set_bytes,
        body_bytes=bad_body_bytes,
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match="not valid JSON"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — body is JSON but not a dict (line 301)
# ---------------------------------------------------------------------------

def test_verify_body_not_dict() -> None:
    """Line 301: body_bytes is valid JSON but not a dict raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=b"\x00" * 64,
        body_bytes=b'"just a string"',
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match="not a JSON object"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — spec missing (line 307)
# ---------------------------------------------------------------------------

def test_verify_spec_missing() -> None:
    """Line 307: body without spec raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    body = {"no_spec": True}
    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=b"\x00" * 64,
        body_bytes=json.dumps(body).encode(),
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match=r"body\.spec missing"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — spec not a dict (line 307)
# ---------------------------------------------------------------------------

def test_verify_spec_not_dict() -> None:
    """Line 307: spec is not a dict raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    body = {"spec": "not-a-dict"}
    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=b"\x00" * 64,
        body_bytes=json.dumps(body).encode(),
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match=r"body\.spec missing"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — content missing (line 310)
# ---------------------------------------------------------------------------

def test_verify_content_missing() -> None:
    """Line 310: spec without content raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    body: dict[str, object] = {"spec": {}}
    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=b"\x00" * 64,
        body_bytes=json.dumps(body).encode(),
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match=r"body\.spec\.content missing"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — content not a dict (line 310)
# ---------------------------------------------------------------------------

def test_verify_content_not_dict() -> None:
    """Line 310: content is not a dict raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    body: dict[str, object] = {"spec": {"content": 42}}
    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=b"\x00" * 64,
        body_bytes=json.dumps(body).encode(),
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match=r"body\.spec\.content missing"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — hash field missing (line 313)
# ---------------------------------------------------------------------------

def test_verify_hash_field_missing() -> None:
    """Line 313: content without hash raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    body: dict[str, object] = {"spec": {"content": {}}}
    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=b"\x00" * 64,
        body_bytes=json.dumps(body).encode(),
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match=r"body\.spec\.content\.hash missing"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — hash not a dict (line 313)
# ---------------------------------------------------------------------------

def test_verify_hash_not_dict() -> None:
    """Line 313: hash is not a dict raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    body = {"spec": {"content": {"hash": "not-a-dict"}}}
    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=b"\x00" * 64,
        body_bytes=json.dumps(body).encode(),
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match=r"body\.spec\.content\.hash missing"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — wrong hash algorithm (line 316)
# ---------------------------------------------------------------------------

def test_verify_wrong_algorithm() -> None:
    """Line 316: hash algorithm != 'sha256' raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    body = {"spec": {"content": {"hash": {"algorithm": "sha512", "value": "ff" * 32}}}}
    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=b"\x00" * 64,
        body_bytes=json.dumps(body).encode(),
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match="hash algorithm is 'sha512'"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — hash value missing (line 319)
# ---------------------------------------------------------------------------

def test_verify_hash_value_missing() -> None:
    """Line 319: hash value is not a str raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    body = {"spec": {"content": {"hash": {"algorithm": "sha256"}}}}
    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=b"\x00" * 64,
        body_bytes=json.dumps(body).encode(),
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match="hash value missing"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — hash value is not valid hex (lines 322-323)
# ---------------------------------------------------------------------------

def test_verify_hash_value_not_hex() -> None:
    """Lines 322-323: hash value that is not valid hex raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    body = {"spec": {"content": {"hash": {"algorithm": "sha256", "value": "zzzz-not-hex"}}}}
    parsed = ParsedRekorEntry(
        log_index=1,
        log_id="test.rekor",
        integrated_time=_NOW,
        signed_entry_timestamp=b"\x00" * 64,
        body_bytes=json.dumps(body).encode(),
        raw_log_entry={},
    )
    digest = hashlib.sha256(b"x").digest()
    with pytest.raises(AnchorVerificationError, match="not valid hex"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — invalid DER public key (lines 330-331)
# ---------------------------------------------------------------------------

def test_verify_invalid_der_public_key() -> None:
    """Lines 330-331: invalid DER public key raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"test-der").digest()
    log_entry_bytes = _make_valid_log_entry(digest, authority=authority, signing_key=signing_key)
    parsed = parse_rekor_log_entry(log_entry_bytes)

    with pytest.raises(AnchorVerificationError, match="not valid DER SPKI"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=b"this is not valid DER",
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — non-Ed25519 public key (line 333)
# ---------------------------------------------------------------------------

def test_verify_non_ed25519_public_key() -> None:
    """Line 333: DER key that is not Ed25519 raises AnchorVerificationError."""
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric import ec

    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"test-ec").digest()
    log_entry_bytes = _make_valid_log_entry(digest, authority=authority, signing_key=signing_key)
    parsed = parse_rekor_log_entry(log_entry_bytes)

    # Generate an EC key and use its public key DER
    ec_private = ec.generate_private_key(ec.SECP256R1())
    ec_pubkey_der = ec_private.public_key().public_bytes(
        encoding=ser.Encoding.DER,
        format=ser.PublicFormat.SubjectPublicKeyInfo,
    )

    with pytest.raises(AnchorVerificationError, match="Ed25519"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=ec_pubkey_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — wrong digest length (line 294)
# ---------------------------------------------------------------------------

def test_verify_wrong_digest_length() -> None:
    """Line 294: expected_digest not 32 bytes raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"x").digest()
    log_entry_bytes = _make_valid_log_entry(digest, authority=authority, signing_key=signing_key)
    parsed = parse_rekor_log_entry(log_entry_bytes)
    with pytest.raises(AnchorVerificationError, match="32 bytes"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=b"\x00" * 16,  # wrong length
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# SigstoreRekorAnchor — empty log_id raises ValueError (line 116)
# ---------------------------------------------------------------------------

def test_anchor_empty_log_id_raises() -> None:
    """Line 116: empty log_id raises ValueError."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    with pytest.raises(ValueError, match="log_id"):
        SigstoreRekorAnchor(
            rekor_public_key=authority.public_key,
            log_id="",
        )


# ---------------------------------------------------------------------------
# SigstoreRekorAnchor — full success path (lines 190-198: AnchorRecord built)
# ---------------------------------------------------------------------------

def test_request_timestamp_success_path() -> None:
    """Lines 190-198: successful request_timestamp builds AnchorRecord correctly."""
    authority = TestRekorAuthority(log_id="rekor.test", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"full-success").digest()
    log_entry_bytes = _make_valid_log_entry(digest, authority=authority, signing_key=signing_key)
    transport = RecordedHttpTransport(log_entry_bytes)

    provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id="rekor.test",
        signing_key=signing_key,
        transport=transport,
    )
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), anchored_seq=5, now=_NOW)
    assert anchor.anchored_seq == 5
    assert anchor.anchored_event_hash == digest
    assert anchor.tsa_token == log_entry_bytes
    assert len(anchor.tsa_cert_chain) == 1


# ---------------------------------------------------------------------------
# parse_rekor_log_entry — non-JSON (lines 219-220)
# ---------------------------------------------------------------------------

def test_parse_non_json() -> None:
    """Lines 219-220: non-JSON raises AnchorVerificationError."""
    with pytest.raises(AnchorVerificationError, match="not valid JSON"):
        parse_rekor_log_entry(b"not-json-at-all")


# ---------------------------------------------------------------------------
# parse_rekor_log_entry — non-object JSON (line 222)
# ---------------------------------------------------------------------------

def test_parse_non_object_json() -> None:
    """Line 222: JSON non-object raises AnchorVerificationError."""
    with pytest.raises(AnchorVerificationError, match="not a JSON object"):
        parse_rekor_log_entry(b'"a string"')


# ---------------------------------------------------------------------------
# parse_rekor_log_entry — missing required fields (line 227)
# ---------------------------------------------------------------------------

def test_parse_missing_required_fields() -> None:
    """Line 227: dict missing required fields raises AnchorVerificationError."""
    partial = json.dumps({"logIndex": 1}).encode()
    with pytest.raises(AnchorVerificationError, match="missing fields"):
        parse_rekor_log_entry(partial)


# ---------------------------------------------------------------------------
# parse_rekor_log_entry — full success path (lines 243-252)
# ---------------------------------------------------------------------------

def test_parse_success_returns_parsed_entry() -> None:
    """Lines 243-252: valid log entry is parsed successfully."""
    authority = TestRekorAuthority(log_id="parse.test", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"parse-success").digest()
    log_entry_bytes = _make_valid_log_entry(digest, authority=authority, signing_key=signing_key)
    parsed = parse_rekor_log_entry(log_entry_bytes)
    assert parsed.log_id == "parse.test"
    assert parsed.log_index >= 1
    assert parsed.integrated_time == _NOW
    assert len(parsed.signed_entry_timestamp) > 0
    assert len(parsed.body_bytes) > 0


# ---------------------------------------------------------------------------
# _set_payload — reconstruction (lines 263-269)
# ---------------------------------------------------------------------------

def test_set_payload_reconstruction() -> None:
    """Lines 263-269: _set_payload produces canonical JSON bytes."""
    authority = TestRekorAuthority(log_id="set.test", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"set-payload").digest()
    log_entry_bytes = _make_valid_log_entry(digest, authority=authority, signing_key=signing_key)
    parsed = parse_rekor_log_entry(log_entry_bytes)
    payload = _set_payload(parsed)
    assert isinstance(payload, bytes)
    decoded = json.loads(payload)
    assert decoded["logID"] == "set.test"
    assert decoded["logIndex"] == parsed.log_index


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — full success (line 294+)
# ---------------------------------------------------------------------------

def test_verify_full_success() -> None:
    """Lines 293-341: full successful verification path."""
    authority = TestRekorAuthority(log_id="verify.test", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"full-verify").digest()
    log_entry_bytes = _make_valid_log_entry(digest, authority=authority, signing_key=signing_key)
    parsed = parse_rekor_log_entry(log_entry_bytes)
    # Should not raise
    verify_rekor_signed_entry_timestamp(
        parsed,
        expected_digest=digest,
        rekor_public_key_der=authority.public_key_der,
    )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — digest mismatch (line 325)
# ---------------------------------------------------------------------------

def test_verify_digest_mismatch() -> None:
    """Line 325: digest mismatch raises AnchorVerificationError."""
    authority = TestRekorAuthority(log_id="verify.test", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"real").digest()
    log_entry_bytes = _make_valid_log_entry(digest, authority=authority, signing_key=signing_key)
    parsed = parse_rekor_log_entry(log_entry_bytes)
    other = hashlib.sha256(b"different").digest()
    with pytest.raises(AnchorVerificationError, match="body digest"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=other,
            rekor_public_key_der=authority.public_key_der,
        )


# ---------------------------------------------------------------------------
# verify_rekor_signed_entry_timestamp — wrong SET signature (lines 335-339)
# ---------------------------------------------------------------------------

def test_verify_wrong_set_signature() -> None:
    """Lines 335-339: wrong Rekor public key causes SET signature to fail."""
    authority_a = TestRekorAuthority(log_id="verify.test", now=_NOW)
    authority_b = TestRekorAuthority(log_id="verify.test", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"set-sig").digest()
    log_entry_bytes = _make_valid_log_entry(digest, authority=authority_a, signing_key=signing_key)
    parsed = parse_rekor_log_entry(log_entry_bytes)
    with pytest.raises(AnchorVerificationError, match="signedEntryTimestamp does not verify"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority_b.public_key_der,
        )


# ---------------------------------------------------------------------------
# is_sigstore_rekor_anchor — false case
# ---------------------------------------------------------------------------

def test_is_sigstore_rekor_anchor_false() -> None:
    """is_sigstore_rekor_anchor returns False for non-sigstore providers."""
    from attestplane.anchoring.base import ANCHOR_SCHEMA_VERSION, AnchorRecord

    record = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=b"\x00" * 32,
        tsa_provider_id="freetsa.org",
        tsa_token=b"token",
        tsa_cert_chain=(b"cert",),
        ocsp_responses=(b"ocsp",),
        issued_at_claimed=_NOW,
    )
    assert not is_sigstore_rekor_anchor(record)


# ---------------------------------------------------------------------------
# SigstoreRekorAnchor — ephemeral key generated when signing_key is None
# ---------------------------------------------------------------------------

def test_anchor_generates_ephemeral_key() -> None:
    """When signing_key=None, an ephemeral key is auto-generated."""
    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"ephemeral").digest()
    # We don't know the ephemeral key, so we can't produce a matching response
    # via authority — just verify the provider instantiation succeeds and
    # that the transport error propagates cleanly.

    class BombTransport(RecordedHttpTransport):
        def __init__(self) -> None:
            super().__init__(b"")

        def submit(self, url: str, req_der: bytes, *, timeout_seconds: float = 30.0) -> bytes:
            raise TSAUnavailableError("bomb")

    provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id="test.rekor",
        signing_key=None,  # ephemeral
        transport=BombTransport(),
    )
    with pytest.raises(TSAUnavailableError):
        provider.request_timestamp(TimestampRequest(digest=digest))
