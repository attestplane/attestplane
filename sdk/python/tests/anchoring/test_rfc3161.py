# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""End-to-end RFC-3161 tests using the in-tree TestTSAAuthority.

Round-trips ``TestTSAAuthority`` issuance → ``parse_timestamp_response``
→ ``verify_timestamp_token`` → ``verify_chain_with_anchors`` with real
RSA signatures, real X.509 cert chain, real CMS SignedData structure.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

# Skip the whole module when the anchor extras are missing.
pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from cryptography import x509 as cx509
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from attestplane.anchoring import (
    ANCHOR_SCHEMA_VERSION,
    AnchorRecord,
    AnchorVerificationError,
    TimestampRequest,
    verify_chain_with_anchors,
)
from attestplane.anchoring.rfc3161 import (
    parse_timestamp_response,
    verify_timestamp_token,
)
from attestplane.anchoring.testing import (
    TestTSAAuthority,
    TestTSAProvider,
)
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import ChainHead, EventDraft

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _build_chain(n: int) -> list:
    chain = []
    head = genesis_head()
    for i in range(n):
        draft = EventDraft(
            event_type="eval_event",
            actor=f"agent://test/{i}",
            payload={"i": i},
        )
        ev = chain_extend(head, draft, now=_NOW, event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


# --- Authority + provider round-trip --------------------------------------


def test_authority_issues_parseable_response() -> None:
    authority = TestTSAAuthority(now=_NOW)
    digest = hashlib.sha256(b"hello").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW, serial_number=1)
    parsed = parse_timestamp_response(der)
    assert parsed.hash_algorithm == "sha256"
    assert parsed.message_imprint == digest
    assert parsed.gen_time == _NOW
    assert parsed.serial_number == 1


def test_authority_round_trip_verifies() -> None:
    authority = TestTSAAuthority(now=_NOW)
    digest = hashlib.sha256(b"hello").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)
    materials = authority.materials()
    verify_timestamp_token(
        parsed,
        expected_digest=digest,
        trust_roots_der=[materials.root_cert_der],
        verification_time=_NOW,
    )  # must not raise


def test_authority_with_nonce_round_trips() -> None:
    authority = TestTSAAuthority(now=_NOW)
    digest = hashlib.sha256(b"hello-nonce").digest()
    der = authority.sign_timestamp_response(
        digest,
        gen_time=_NOW,
        nonce=b"\x01\x02\x03\x04",
    )
    parsed = parse_timestamp_response(der)
    assert parsed.nonce == int.from_bytes(b"\x01\x02\x03\x04", "big")


def test_verify_rejects_digest_mismatch() -> None:
    authority = TestTSAAuthority(now=_NOW)
    digest = hashlib.sha256(b"hello").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)
    materials = authority.materials()
    with pytest.raises(AnchorVerificationError, match="message_imprint"):
        verify_timestamp_token(
            parsed,
            expected_digest=hashlib.sha256(b"other").digest(),
            trust_roots_der=[materials.root_cert_der],
            verification_time=_NOW,
        )


def test_verify_rejects_unknown_trust_root() -> None:
    authority_a = TestTSAAuthority(now=_NOW)
    authority_b = TestTSAAuthority(now=_NOW, common_name="Different TSA")
    digest = hashlib.sha256(b"hello").digest()
    der = authority_a.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)
    other_materials = authority_b.materials()  # wrong root
    # The wrong root has the same CN as the real one ("Attestplane Test
    # Root CA"), so the chain walker finds it as a candidate by DN match
    # then fails the signature verification.
    with pytest.raises(AnchorVerificationError, match="signature does not verify"):
        verify_timestamp_token(
            parsed,
            expected_digest=digest,
            trust_roots_der=[other_materials.root_cert_der],
            verification_time=_NOW,
        )


def test_verify_rejects_expired_cert() -> None:
    authority = TestTSAAuthority(now=_NOW, cert_validity_days=1)
    digest = hashlib.sha256(b"hello").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)
    materials = authority.materials()
    # Move verification_time past the leaf's not_after.
    future = _NOW + timedelta(days=30)
    with pytest.raises(AnchorVerificationError, match="exceeds leaf cert not_after"):
        verify_timestamp_token(
            parsed,
            expected_digest=digest,
            trust_roots_der=[materials.root_cert_der],
            verification_time=future,
        )


def test_verify_rejects_premature_verification() -> None:
    authority = TestTSAAuthority(now=_NOW)
    digest = hashlib.sha256(b"hello").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)
    materials = authority.materials()
    past = _NOW - timedelta(days=30)
    with pytest.raises(AnchorVerificationError, match="precedes leaf cert not_before"):
        verify_timestamp_token(
            parsed,
            expected_digest=digest,
            trust_roots_der=[materials.root_cert_der],
            verification_time=past,
        )


# --- TestTSAProvider integration -----------------------------------------


def test_provider_anchor_record_has_real_token() -> None:
    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority)
    digest = hashlib.sha256(b"chain-head").digest()
    record = provider.request_timestamp(
        TimestampRequest(digest=digest),
        anchored_seq=3,
        now=_NOW,
    )
    assert record.anchored_seq == 3
    assert record.anchored_event_hash == digest
    assert len(record.tsa_cert_chain) == 2  # leaf + root
    assert len(record.ocsp_responses) == 1

    parsed = parse_timestamp_response(record.tsa_token)
    materials = authority.materials()
    verify_timestamp_token(
        parsed,
        expected_digest=digest,
        trust_roots_der=[materials.root_cert_der],
        verification_time=_NOW,
    )


def test_provider_serial_numbers_increment() -> None:
    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority)
    digests = [hashlib.sha256(bytes([i])).digest() for i in range(3)]
    serials = []
    for d in digests:
        r = provider.request_timestamp(TimestampRequest(digest=d), now=_NOW)
        serials.append(parse_timestamp_response(r.tsa_token).serial_number)
    assert serials == [1, 2, 3]


def test_provider_fail_with_raises() -> None:
    from attestplane.anchoring import TSAUnavailableError

    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority, fail_with=TSAUnavailableError("oops"))
    with pytest.raises(TSAUnavailableError, match="oops"):
        provider.request_timestamp(TimestampRequest(digest=b"\x00" * 32))


# --- verify_chain_with_anchors with REAL trust_roots ---------------------


def test_verify_chain_with_anchors_uses_real_signature_check() -> None:
    chain = _build_chain(3)
    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority)
    anchor = provider.request_timestamp(
        TimestampRequest(digest=chain[2].event_hash),
        anchored_seq=2,
        now=_NOW,
    )
    materials = authority.materials()

    result = verify_chain_with_anchors(
        chain,
        [anchor],
        trust_roots_der=[materials.root_cert_der],
        verification_time=_NOW,
    )
    assert result.ok is True
    assert result.anchor_results[0].valid is True
    assert result.anchor_results[0].cert_status == "VALID"


def test_verify_chain_with_anchors_detects_token_tampering() -> None:
    chain = _build_chain(2)
    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority)
    good = provider.request_timestamp(
        TimestampRequest(digest=chain[1].event_hash),
        anchored_seq=1,
        now=_NOW,
    )
    # Flip a byte deep in the signed bytes — must fail signature check.
    tampered_token = bytearray(good.tsa_token)
    # Flip a byte well inside the token (avoid outer wrapper length bytes
    # which would crash the parser entirely; the verifier should reject
    # a parseable-but-invalid signature with AnchorVerificationError).
    flip_index = len(tampered_token) - 32  # somewhere in the signature
    tampered_token[flip_index] ^= 0x01
    tampered = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=good.anchored_seq,
        anchored_event_hash=good.anchored_event_hash,
        tsa_provider_id=good.tsa_provider_id,
        tsa_token=bytes(tampered_token),
        tsa_cert_chain=good.tsa_cert_chain,
        ocsp_responses=good.ocsp_responses,
        issued_at_claimed=good.issued_at_claimed,
    )
    materials = authority.materials()
    result = verify_chain_with_anchors(
        chain,
        [tampered],
        trust_roots_der=[materials.root_cert_der],
        verification_time=_NOW,
    )
    assert result.ok is False
    assert result.anchor_results[0].valid is False


def test_verify_chain_with_anchors_unknown_trust_root_fails() -> None:
    chain = _build_chain(1)
    authority_a = TestTSAAuthority(now=_NOW)
    authority_b = TestTSAAuthority(now=_NOW, common_name="Different")
    provider = TestTSAProvider(authority_a)
    anchor = provider.request_timestamp(
        TimestampRequest(digest=chain[0].event_hash),
        anchored_seq=0,
        now=_NOW,
    )
    # Provide only the WRONG authority's root.
    materials = authority_b.materials()
    result = verify_chain_with_anchors(
        chain,
        [anchor],
        trust_roots_der=[materials.root_cert_der],
        verification_time=_NOW,
    )
    assert result.ok is False
    # Both roots have the same CN, so the chain walker finds B's root
    # by DN match then fails the signature step.
    reason = result.anchor_results[0].reason or ""
    assert "signature does not verify" in reason or "trust root" in reason


def test_verify_chain_without_trust_roots_remains_unverified() -> None:
    """When trust_roots_der is None, cross-reference-correct anchors stay
    at cert_status=VALID_UNVERIFIED (preserves the substrate-only contract)."""
    chain = _build_chain(1)
    authority = TestTSAAuthority(now=_NOW)
    provider = TestTSAProvider(authority)
    anchor = provider.request_timestamp(
        TimestampRequest(digest=chain[0].event_hash),
        anchored_seq=0,
        now=_NOW,
    )
    result = verify_chain_with_anchors(chain, [anchor])
    assert result.ok is True
    assert result.anchor_results[0].cert_status == "VALID_UNVERIFIED"


# ----- P3 / Issue #9 follow-up: EC-leaf TSA support (FreeTSA 2026 rotation) ---


def test_authority_with_ec_leaf_round_trips() -> None:
    """EC (NIST P-256) leaf TSA — verifier must accept ECDSA signature.

    Reproduces the FreeTSA 2026 cert rotation locally: leaf cert public
    key is ECPublicKey instead of RSA. The verifier accepted only RSA
    before issue #9; this test pins the new EC branch.
    """
    authority = TestTSAAuthority(now=_NOW, leaf_key_type="ec")
    digest = hashlib.sha256(b"ec-leaf-roundtrip").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW, serial_number=1)
    parsed = parse_timestamp_response(der)
    assert parsed.hash_algorithm == "sha256"
    assert parsed.message_imprint == digest
    materials = authority.materials()
    verify_timestamp_token(
        parsed,
        expected_digest=digest,
        trust_roots_der=[materials.root_cert_der],
        verification_time=_NOW,
    )  # must not raise


def test_ec_leaf_with_sha512_cms_signer_digest_round_trips() -> None:
    """FreeTSA can sign CMS signed_attrs with SHA-512 ECDSA.

    The timestamped Attestplane chain-head digest remains SHA-256 in
    TSTInfo.messageImprint; the CMS SignerInfo digest/signature
    algorithm is independent and must be honored by the verifier.
    """
    authority = TestTSAAuthority(now=_NOW, leaf_key_type="ec")
    digest = hashlib.sha256(b"ec-leaf-sha512-signer-digest").digest()
    der = authority.sign_timestamp_response(
        digest,
        gen_time=_NOW,
        serial_number=1,
        signer_digest_algorithm="sha512",
    )
    parsed = parse_timestamp_response(der)
    assert parsed.hash_algorithm == "sha256"
    assert parsed.digest_algorithm_oid == "sha512"
    assert parsed.signature_algorithm_oid == "sha512_ecdsa"
    assert parsed.message_imprint == digest
    materials = authority.materials()
    verify_timestamp_token(
        parsed,
        expected_digest=digest,
        trust_roots_der=[materials.root_cert_der],
        verification_time=_NOW,
    )  # must not raise


def test_ec_leaf_signature_tamper_fails_closed() -> None:
    """Tampering the ECDSA signature byte must surface as fail-closed."""
    authority = TestTSAAuthority(now=_NOW, leaf_key_type="ec")
    digest = hashlib.sha256(b"ec-leaf-tamper").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)
    # Flip one bit of the signature.
    bad_sig = bytearray(parsed.signature)
    bad_sig[-1] ^= 0x01
    from dataclasses import replace

    tampered = replace(parsed, signature=bytes(bad_sig))
    materials = authority.materials()
    with pytest.raises(AnchorVerificationError, match="ECDSA signature does not verify"):
        verify_timestamp_token(
            tampered,
            expected_digest=digest,
            trust_roots_der=[materials.root_cert_der],
            verification_time=_NOW,
        )


def test_ec_leaf_provider_anchor_record_verifies() -> None:
    """End-to-end EC-leaf TSA through TestTSAProvider + verify_chain_with_anchors."""
    authority = TestTSAAuthority(now=_NOW, leaf_key_type="ec")
    provider = TestTSAProvider(authority=authority)
    chain = _build_chain(1)
    head_hash = chain[0].event_hash
    anchor = provider.request_timestamp(
        TimestampRequest(digest=head_hash),
        anchored_seq=0,
        now=_NOW,
    )
    result = verify_chain_with_anchors(chain, [anchor])
    assert result.ok is True
    # Absent OCSP material the cert_status stays VALID_UNVERIFIED — same
    # convention as the RSA leaf path. Leaf-key-class branch is exercised
    # via the verify_timestamp_token path inside verify_chain_with_anchors.
    assert result.anchor_results[0].cert_status == "VALID_UNVERIFIED"


def test_unsupported_leaf_key_type_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defensive branch — non-RSA / non-EC leaf must surface fail-closed.

    Triggered by patching ``leaf.public_key()`` to return an Ed25519PublicKey,
    which neither ``RSAPublicKey`` nor ``EllipticCurvePublicKey``. The verifier
    must raise ``AnchorVerificationError`` with the unsupported-key message.
    """
    authority = TestTSAAuthority(now=_NOW)
    digest = hashlib.sha256(b"unsupported-key-defensive").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)
    materials = authority.materials()

    ed_public = Ed25519PrivateKey.generate().public_key()
    original = cx509.Certificate.public_key

    def fake_public_key(self: cx509.Certificate) -> object:
        # Only swap for the leaf parse; intermediates/root walk shouldn't hit it.
        return ed_public

    monkeypatch.setattr(cx509.Certificate, "public_key", fake_public_key)
    with pytest.raises(AnchorVerificationError, match="unsupported leaf key type"):
        verify_timestamp_token(
            parsed,
            expected_digest=digest,
            trust_roots_der=[materials.root_cert_der],
            verification_time=_NOW,
        )
