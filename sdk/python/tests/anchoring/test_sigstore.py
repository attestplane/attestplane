# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.anchoring.sigstore` per ADR-0006.

Uses :class:`TestRekorAuthority` as a synthetic in-process Rekor log
to exercise the full anchor → verify round-trip with real Ed25519
signatures, no live network.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

pytest.importorskip("asn1crypto")
pytest.importorskip("cryptography")

from attestplane.anchoring import (
    AnchorVerificationError,
    TimestampRequest,
    verify_chain_with_anchors,
)
from attestplane.anchoring.http import RecordedHttpTransport
from attestplane.anchoring.sigstore import (
    PUBLIC_REKOR_URL,
    SIGSTORE_REKOR_OCSP_MARKER,
    SIGSTORE_REKOR_PROVIDER_PREFIX,
    SigstoreRekorAnchor,
    is_sigstore_rekor_anchor,
    parse_rekor_log_entry,
    verify_rekor_signed_entry_timestamp,
)
from attestplane.anchoring.testing import TestRekorAuthority
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import ChainHead, EventDraft

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _build_chain(n: int) -> list:
    chain = []
    head = genesis_head()
    for i in range(n):
        draft = EventDraft(
            event_type="eval_event",
            actor=f"a{i}",
            payload={"i": i},
        )
        ev = chain_extend(head, draft, now=_NOW, event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


def _make_authority_response(authority: TestRekorAuthority, digest: bytes, signing_key, now=None) -> bytes:
    """Replicate what SigstoreRekorAnchor builds, then have authority sign it."""
    import base64

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
            },
        },
    }
    body_bytes = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return authority.issue_log_entry(body_bytes, now=now)


# --- SigstoreRekorAnchor basic behaviour ---


def test_anchor_produces_rekor_record() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    authority = TestRekorAuthority(log_id="test.rekor", now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"chain-head").digest()

    # Pre-compute the expected response.
    expected = _make_authority_response(authority, digest, signing_key, now=_NOW)
    transport = RecordedHttpTransport(expected)

    anchor_provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id="test.rekor",
        signing_key=signing_key,
        transport=transport,
    )
    anchor = anchor_provider.request_timestamp(
        TimestampRequest(digest=digest),
        anchored_seq=0,
        now=_NOW,
    )

    assert anchor.tsa_provider_id == f"{SIGSTORE_REKOR_PROVIDER_PREFIX}test.rekor"
    assert anchor.tsa_token == expected
    assert anchor.anchored_event_hash == digest
    assert anchor.ocsp_responses == (SIGSTORE_REKOR_OCSP_MARKER,)
    assert is_sigstore_rekor_anchor(anchor)


def test_anchor_uses_authority_public_key_in_cert_chain() -> None:
    """tsa_cert_chain[0] is the Rekor public key DER per ADR-0006 § 3."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    authority = TestRekorAuthority(now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"x").digest()
    expected = _make_authority_response(authority, digest, signing_key, now=_NOW)
    transport = RecordedHttpTransport(expected)

    provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id=authority.log_id,
        signing_key=signing_key,
        transport=transport,
    )
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
    assert anchor.tsa_cert_chain == (authority.public_key_der,)


def test_rejects_empty_log_id() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    with pytest.raises(ValueError, match="log_id"):
        SigstoreRekorAnchor(
            rekor_public_key=Ed25519PrivateKey.generate().public_key(),
            log_id="",
        )


# --- parse_rekor_log_entry ---


def test_parse_rejects_non_json() -> None:
    with pytest.raises(AnchorVerificationError, match="not valid JSON"):
        parse_rekor_log_entry(b"not json")


def test_parse_rejects_non_object() -> None:
    with pytest.raises(AnchorVerificationError, match="not a JSON object"):
        parse_rekor_log_entry(b'"a string"')


def test_parse_rejects_missing_fields() -> None:
    with pytest.raises(AnchorVerificationError, match="missing fields"):
        parse_rekor_log_entry(b'{"logIndex": 1}')


def test_parse_extracts_fields() -> None:
    authority = TestRekorAuthority(log_id="test", now=_NOW)
    body_bytes = json.dumps(
        {"spec": {"content": {"hash": {"algorithm": "sha256", "value": "ff" * 32}}}},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    log_entry = authority.issue_log_entry(body_bytes, now=_NOW)

    parsed = parse_rekor_log_entry(log_entry)
    assert parsed.log_id == "test"
    assert parsed.log_index == 1
    assert parsed.integrated_time == _NOW
    assert len(parsed.signed_entry_timestamp) > 0


# --- verify_rekor_signed_entry_timestamp ---


def test_verify_succeeds_on_good_entry() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    authority = TestRekorAuthority(now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"good").digest()
    log_entry_bytes = _make_authority_response(authority, digest, signing_key, now=_NOW)
    parsed = parse_rekor_log_entry(log_entry_bytes)

    verify_rekor_signed_entry_timestamp(
        parsed,
        expected_digest=digest,
        rekor_public_key_der=authority.public_key_der,
    )


def test_verify_rejects_digest_mismatch() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    authority = TestRekorAuthority(now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"real").digest()
    log_entry_bytes = _make_authority_response(authority, digest, signing_key, now=_NOW)
    parsed = parse_rekor_log_entry(log_entry_bytes)

    other_digest = hashlib.sha256(b"other").digest()
    with pytest.raises(AnchorVerificationError, match="body digest"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=other_digest,
            rekor_public_key_der=authority.public_key_der,
        )


def test_verify_rejects_wrong_rekor_pubkey() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    authority_a = TestRekorAuthority(now=_NOW)
    authority_b = TestRekorAuthority(now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"x").digest()

    log_entry_bytes = _make_authority_response(authority_a, digest, signing_key, now=_NOW)
    parsed = parse_rekor_log_entry(log_entry_bytes)

    with pytest.raises(AnchorVerificationError, match="signedEntryTimestamp does not verify"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority_b.public_key_der,  # wrong authority
        )


def test_verify_rejects_wrong_digest_length() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    authority = TestRekorAuthority(now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"x").digest()
    log_entry_bytes = _make_authority_response(authority, digest, signing_key, now=_NOW)
    parsed = parse_rekor_log_entry(log_entry_bytes)

    with pytest.raises(AnchorVerificationError, match="32 bytes"):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=b"\x00" * 16,
            rekor_public_key_der=authority.public_key_der,
        )


def test_verify_rejects_tampered_body() -> None:
    """If someone alters the body but keeps the SET, verification fails."""
    import base64

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    authority = TestRekorAuthority(now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = hashlib.sha256(b"original").digest()
    log_entry_bytes = _make_authority_response(authority, digest, signing_key, now=_NOW)

    # Tamper: replace the body's hash with a different digest.
    log_entry = json.loads(log_entry_bytes)
    original_body_bytes = base64.standard_b64decode(log_entry["body"])
    original_body = json.loads(original_body_bytes)
    original_body["spec"]["content"]["hash"]["value"] = "ff" * 32  # different
    new_body_bytes = json.dumps(original_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    log_entry["body"] = base64.standard_b64encode(new_body_bytes).decode("ascii")

    parsed = parse_rekor_log_entry(json.dumps(log_entry, sort_keys=True, separators=(",", ":")).encode("utf-8"))

    # Two failure modes possible: digest mismatch OR SET signature
    # mismatch (since changing body changes SET payload). Either is
    # acceptable per ADR-0006 verification semantics.
    with pytest.raises(AnchorVerificationError):
        verify_rekor_signed_entry_timestamp(
            parsed,
            expected_digest=digest,
            rekor_public_key_der=authority.public_key_der,
        )


# --- End-to-end via verify_chain_with_anchors ---


def test_e2e_verify_chain_with_rekor_anchor() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    chain = _build_chain(2)
    authority = TestRekorAuthority(now=_NOW)
    signing_key = Ed25519PrivateKey.generate()

    # Build the anchor exactly as SigstoreRekorAnchor would, but via
    # the test-recorded transport so no network is touched.
    digest = chain[1].event_hash
    response_bytes = _make_authority_response(authority, digest, signing_key, now=_NOW)
    transport = RecordedHttpTransport(response_bytes)
    anchor_provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id=authority.log_id,
        signing_key=signing_key,
        transport=transport,
    )
    anchor = anchor_provider.request_timestamp(
        TimestampRequest(digest=digest),
        anchored_seq=1,
        now=_NOW,
    )

    # Verify via the public verifier API. We pass the authority's
    # pubkey as the trust root; verify_chain_with_anchors's Sigstore
    # dispatch reads it from anchor.tsa_cert_chain[0].
    result = verify_chain_with_anchors(
        chain,
        [anchor],
        trust_roots_der=[authority.public_key_der],
        verification_time=_NOW,
    )
    assert result.ok is True
    assert result.anchor_results[0].cert_status == "VALID"
    assert result.anchor_results[0].valid is True


def test_e2e_detects_tampered_token() -> None:
    from dataclasses import replace

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    chain = _build_chain(1)
    authority = TestRekorAuthority(now=_NOW)
    signing_key = Ed25519PrivateKey.generate()
    digest = chain[0].event_hash
    response_bytes = _make_authority_response(authority, digest, signing_key, now=_NOW)
    transport = RecordedHttpTransport(response_bytes)
    provider = SigstoreRekorAnchor(
        rekor_public_key=authority.public_key,
        log_id=authority.log_id,
        signing_key=signing_key,
        transport=transport,
    )
    anchor = provider.request_timestamp(
        TimestampRequest(digest=digest),
        anchored_seq=0,
        now=_NOW,
    )

    # Tamper: corrupt the SET bytes inside tsa_token.
    log_entry = json.loads(anchor.tsa_token)
    import base64

    bad_set = base64.standard_b64decode(log_entry["verification"]["signedEntryTimestamp"])
    bad_set_arr = bytearray(bad_set)
    bad_set_arr[0] ^= 0xFF
    log_entry["verification"]["signedEntryTimestamp"] = base64.standard_b64encode(bytes(bad_set_arr)).decode("ascii")
    tampered = replace(
        anchor,
        tsa_token=json.dumps(log_entry, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )

    result = verify_chain_with_anchors(
        chain,
        [tampered],
        trust_roots_der=[authority.public_key_der],
        verification_time=_NOW,
    )
    assert result.ok is False
    assert result.anchor_results[0].cert_status == "MISSING_LTV_ARTIFACTS"


def test_provider_constants_locked() -> None:
    assert PUBLIC_REKOR_URL == "https://rekor.sigstore.dev/api/v1/log/entries"
    assert SIGSTORE_REKOR_PROVIDER_PREFIX == "sigstore.rekor:"
    assert SIGSTORE_REKOR_OCSP_MARKER == b"SIGSTORE-REKOR-NO-OCSP-APPLIES"
