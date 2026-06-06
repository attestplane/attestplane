# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-gap tests for attestplane.signing.verifier_ext.

Targets missing lines/branches:
  133, 146, 157, 178, 201-202, 210, 219, 244, 252, 273-274,
  287->301 (elif per_event true path), 290, 380, 383, 406.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization

from attestplane.hashchain import chain_extend, genesis_head
from attestplane.signing import (
    SIGNATURE_SCHEMA_VERSION,
    InMemoryKeyProvider,
    SignatureRecord,
    Signer,
    SigningError,
    TrustRootEntry,
    TrustRoots,
    derive_key_id,
    verify_chain_full,
    verify_chain_with_signatures,
)
from attestplane.signing.verifier_ext import _verify_single_signature
from attestplane.types import ChainHead, EventDraft

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_VF = datetime(2026, 1, 1, tzinfo=UTC)
_VU = datetime(2027, 5, 17, tzinfo=UTC)

_SEED_00 = b"\x00" * 32
_SEED_01 = b"\x01" * 32


def _build_chain(n: int) -> list:
    chain = []
    head = genesis_head()
    for i in range(n):
        draft = EventDraft(event_type="eval_event", actor=f"a{i}", payload={"i": i})
        ev = chain_extend(head, draft, now=_NOW, event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


def _trust_root_entry(seed: bytes, *, vf: datetime = _VF, vu: datetime = _VU) -> TrustRootEntry:
    p = InMemoryKeyProvider(seed=seed)
    der = p.get_signing_material().public_key_der
    return TrustRootEntry(
        key_id=derive_key_id(der),
        public_key_der=der,
        valid_from=vf,
        valid_until=vu,
        provider_id=None,
        label=None,
    )


def _trust_roots(*entries: TrustRootEntry) -> TrustRoots:
    return TrustRoots(version=1, entries=tuple(entries))


def _make_valid_record(seed: bytes, chain: list, seq: int, *, mode: str = "segment_head") -> SignatureRecord:
    """Helper: produce a real signed record for the given seq."""
    signer = Signer(chain_id="test-chain", key_provider=InMemoryKeyProvider(seed=seed), now=lambda: _NOW)
    if mode == "segment_head":
        return signer.sign_segment_head(ChainHead(seq=seq, event_hash=chain[seq].event_hash))[0]
    else:
        return signer.sign_event(chain[seq])[0]


def _tamper_record(record: SignatureRecord, **kwargs) -> SignatureRecord:
    """Build a new SignatureRecord with specific fields overridden (bypasses post_init checks via object.__new__)."""
    obj = object.__new__(SignatureRecord)
    fields = {
        "signature_schema_version": record.signature_schema_version,
        "signed_seq": record.signed_seq,
        "signed_event_hash": record.signed_event_hash,
        "signature": record.signature,
        "key_id": record.key_id,
        "public_key_der": record.public_key_der,
        "signing_cert_chain": record.signing_cert_chain,
        "signed_at": record.signed_at,
        "signature_mode": record.signature_mode,
        "signed_payload": record.signed_payload,
    }
    fields.update(kwargs)
    for k, v in fields.items():
        object.__setattr__(obj, k, v)
    return obj


# ---------------------------------------------------------------------------
# Line 133: wrong signature_schema_version
# ---------------------------------------------------------------------------


def test_verify_single_signature_wrong_schema_version() -> None:
    """Line 133: signature_schema_version != expected → invalid."""
    chain = _build_chain(2)
    record = _make_valid_record(_SEED_00, chain, 1)
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    # Tamper the schema version to 99 (bypass post_init)
    bad_record = _tamper_record(record, signature_schema_version=99)

    result = _verify_single_signature(
        bad_record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert result.status == "invalid"
    assert "unsupported" in (result.reason or "")


# ---------------------------------------------------------------------------
# Line 146: empty signed_payload (defense-in-depth)
# ---------------------------------------------------------------------------


def test_verify_single_signature_empty_signed_payload() -> None:
    """Line 146: signed_payload empty → invalid (defense-in-depth)."""
    chain = _build_chain(2)
    record = _make_valid_record(_SEED_00, chain, 1)
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    bad_record = _tamper_record(record, signature_schema_version=SIGNATURE_SCHEMA_VERSION, signed_payload=b"")

    result = _verify_single_signature(
        bad_record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert result.status == "invalid"
    assert "signed_payload is empty" in (result.reason or "")


# ---------------------------------------------------------------------------
# Line 157: key_id does not derive from public_key_der
# ---------------------------------------------------------------------------


def test_verify_single_signature_key_id_mismatch() -> None:
    """Line 157: derived key_id != record.key_id → invalid."""
    chain = _build_chain(2)
    record = _make_valid_record(_SEED_00, chain, 1)
    # Use a different key's id (so it doesn't match public_key_der)
    other_provider = InMemoryKeyProvider(seed=_SEED_01)
    other_der = other_provider.get_signing_material().public_key_der
    wrong_key_id = derive_key_id(other_der)

    tr = TrustRoots(version=1, entries=(
        TrustRootEntry(
            key_id=wrong_key_id,
            public_key_der=other_der,
            valid_from=_VF,
            valid_until=_VU,
            provider_id=None,
            label=None,
        ),
    ))
    bad_record = _tamper_record(record, key_id=wrong_key_id)

    result = _verify_single_signature(
        bad_record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert result.status == "invalid"
    assert "does not derive from public_key_der" in (result.reason or "")


# ---------------------------------------------------------------------------
# Line 178: verification_time < valid_from (precedes valid_from)
# ---------------------------------------------------------------------------


def test_verify_single_signature_precedes_valid_from() -> None:
    """Line 178: verification_time before valid_from → expired_key."""
    chain = _build_chain(2)
    record = _make_valid_record(_SEED_00, chain, 1)
    # Key valid starting 2027, but we verify in 2026
    tr = _trust_roots(
        _trust_root_entry(
            _SEED_00,
            vf=datetime(2027, 1, 1, tzinfo=UTC),
            vu=datetime(2028, 1, 1, tzinfo=UTC),
        )
    )

    status, results, _, _ = verify_chain_with_signatures(
        chain,
        [record],
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,  # 2026 < valid_from 2027
    )
    assert status == "expired_key"
    assert "precedes valid_from" in (results[0].reason or "")


# ---------------------------------------------------------------------------
# Lines 201-202: public_key_der not parseable
# ---------------------------------------------------------------------------


def test_verify_single_signature_unparsable_public_key_der() -> None:
    """Lines 201-202: load_der_public_key raises → invalid."""
    chain = _build_chain(2)
    record = _make_valid_record(_SEED_00, chain, 1)
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    # Use garbage DER bytes that match key_id (trick: build a new entry with garbage DER)
    # We need key_id to match, so we use the same key_id but replace public_key_der with garbage
    # that produces the same hash — impossible normally, so instead we must craft the
    # trust_roots entry with the real key_id but mangle the record's public_key_der.
    # Since post_init checks key_id = derive(public_key_der), we use _tamper_record
    # with garbage DER *and* matching key_id (we pre-compute what key_id that garbage derives to).
    garbage_der = b"\x00\x01\x02\x03" * 10  # definitely not a valid DER key
    garbage_kid = derive_key_id(garbage_der)

    tampered_entry = TrustRootEntry(
        key_id=garbage_kid,
        public_key_der=garbage_der,
        valid_from=_VF,
        valid_until=_VU,
        provider_id=None,
        label=None,
    )
    tr2 = TrustRoots(version=1, entries=(tampered_entry,))
    bad_record = _tamper_record(record, public_key_der=garbage_der, key_id=garbage_kid)

    result = _verify_single_signature(
        bad_record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr2,
        verification_time=_NOW,
    )
    assert result.status == "invalid"
    assert "not parseable" in (result.reason or "")


# ---------------------------------------------------------------------------
# Line 210: public key is not Ed25519 (non-Ed25519 type)
# ---------------------------------------------------------------------------


def test_verify_single_signature_non_ed25519_public_key() -> None:
    """Line 210: pubkey is not Ed25519PublicKey → invalid."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    chain = _build_chain(2)

    # Build an RSA public key in DER SPKI format
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_pub_der = rsa_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    rsa_kid = derive_key_id(rsa_pub_der)

    rsa_entry = TrustRootEntry(
        key_id=rsa_kid,
        public_key_der=rsa_pub_der,
        valid_from=_VF,
        valid_until=_VU,
        provider_id=None,
        label=None,
    )
    tr = TrustRoots(version=1, entries=(rsa_entry,))

    # Build a record using the real Ed25519 signer, but swap in RSA DER
    real_provider = InMemoryKeyProvider(seed=_SEED_00)
    real_mat = real_provider.get_signing_material()
    signed_payload = b"dummy payload"
    signature = real_mat.private_key.sign(signed_payload)

    bad_record = _tamper_record(
        _make_valid_record(_SEED_00, chain, 1),
        public_key_der=rsa_pub_der,
        key_id=rsa_kid,
        signed_payload=signed_payload,
        signature=signature,
    )

    result = _verify_single_signature(
        bad_record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert result.status == "invalid"
    assert "Ed25519" in (result.reason or "")


# ---------------------------------------------------------------------------
# Line 219: trust-root public_key_der != record.public_key_der (tamper signal)
# ---------------------------------------------------------------------------


def test_verify_single_signature_trust_root_der_mismatch() -> None:
    """Line 219: same key_id but different DER in trust root → invalid tamper signal."""
    chain = _build_chain(2)
    record = _make_valid_record(_SEED_00, chain, 1)

    # Build a trust-root entry with the correct key_id but different DER
    # We need key_id to match but DER to differ.
    # Use a different Ed25519 key that "happens" to have the same key_id — not possible
    # cryptographically, so instead we craft a TrustRootEntry with a DIFFERENT public_key_der
    # but the SAME key_id (by setting entry manually without validation).
    real_kid = record.key_id
    alt_der = InMemoryKeyProvider(seed=_SEED_01).get_signing_material().public_key_der

    # Build entry manually (TrustRootEntry is frozen dataclass so use direct construction)
    tampered_entry = TrustRootEntry(
        key_id=real_kid,
        public_key_der=alt_der,  # different DER, same key_id
        valid_from=_VF,
        valid_until=_VU,
        provider_id=None,
        label=None,
    )
    tr = TrustRoots(version=1, entries=(tampered_entry,))

    result = _verify_single_signature(
        record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert result.status == "invalid"
    assert "tamper signal" in (result.reason or "")


# ---------------------------------------------------------------------------
# Line 244: signed_seq not in chain
# ---------------------------------------------------------------------------


def test_verify_single_signature_signed_seq_not_in_chain() -> None:
    """Line 244: record.signed_seq does not exist in chain → invalid."""
    chain = _build_chain(3)
    signer = Signer(chain_id="test-chain", key_provider=InMemoryKeyProvider(seed=_SEED_00), now=lambda: _NOW)
    # Sign seq=2 with correct payload
    record = signer.sign_segment_head(ChainHead(seq=2, event_hash=chain[2].event_hash))[0]
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    # Verify against a chain that only has seq 0 and 1 (seq=2 missing)
    short_chain = chain[:2]

    status, results, _, _ = verify_chain_with_signatures(
        short_chain,
        [record],
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert status == "invalid"
    assert "not in chain" in (results[0].reason or "")


# ---------------------------------------------------------------------------
# Line 252: signed_event_hash mismatch
# ---------------------------------------------------------------------------


def test_verify_single_signature_event_hash_mismatch() -> None:
    """Line 252: signed_event_hash does not match the chain event → invalid."""
    chain = _build_chain(3)
    record = _make_valid_record(_SEED_00, chain, 2)
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    # Tamper: change signed_event_hash to wrong value (but keep signature valid for signed_payload)
    wrong_hash = b"\xff" * 32
    bad_record = _tamper_record(record, signed_event_hash=wrong_hash)

    result = _verify_single_signature(
        bad_record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert result.status == "invalid"
    assert "mismatch" in (result.reason or "")


# ---------------------------------------------------------------------------
# Lines 273-274: JSON parse exception in chain_id mismatch (unparsable payload)
# ---------------------------------------------------------------------------


def test_verify_single_signature_unparsable_payload_chain_id_mismatch() -> None:
    """Lines 273-274: signed_payload is not valid JSON → '<unparsable>' in reason."""
    chain = _build_chain(2)
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    # Build a record that passes signature verification but has non-JSON payload
    provider = InMemoryKeyProvider(seed=_SEED_00)
    mat = provider.get_signing_material()
    bad_payload = b"not json at all {{{{"
    sig = mat.private_key.sign(bad_payload)

    bad_record = _tamper_record(
        _make_valid_record(_SEED_00, chain, 1),
        signed_payload=bad_payload,
        signature=sig,
        signature_mode="segment_head",
    )

    result = _verify_single_signature(
        bad_record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert result.status == "invalid"
    # Lines 273-274: JSON parse failed, chain_id should be '<unparsable>'
    assert "<unparsable>" in (result.reason or "")


# ---------------------------------------------------------------------------
# Lines 287->301 (elif per_event True) + line 290 (per_event payload mismatch)
# ---------------------------------------------------------------------------


def test_verify_per_event_payload_mismatch() -> None:
    """Lines 287->301 + 290: per_event signed_payload doesn't match canonicalize(event)."""
    chain = _build_chain(3)
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    # Sign a different event's canonicalized bytes but claim it covers seq=2
    provider = InMemoryKeyProvider(seed=_SEED_00)
    mat = provider.get_signing_material()
    wrong_payload = b'{"wrong": "payload"}'
    sig = mat.private_key.sign(wrong_payload)

    bad_record = _tamper_record(
        _make_valid_record(_SEED_00, chain, 2, mode="per_event"),
        signed_payload=wrong_payload,
        signature=sig,
        signature_mode="per_event",
    )

    result = _verify_single_signature(
        bad_record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert result.status == "invalid"
    assert "per_event" in (result.reason or "")


def test_verify_per_event_payload_valid_path() -> None:
    """Line 287->301: per_event mode with correct payload → valid (covers the elif branch)."""
    chain = _build_chain(3)
    record = _make_valid_record(_SEED_00, chain, 2, mode="per_event")
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    status, results, count, first_bad = verify_chain_with_signatures(
        chain,
        [record],
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert status == "valid"
    assert count == 1
    assert first_bad is None


# ---------------------------------------------------------------------------
# Line 380: verify_chain_with_signatures empty chain_id raises
# ---------------------------------------------------------------------------


def test_verify_chain_with_signatures_empty_chain_id_raises() -> None:
    """Line 380: chain_id empty → SigningError."""
    chain = _build_chain(2)
    tr = _trust_roots(_trust_root_entry(_SEED_00))
    with pytest.raises(SigningError, match="non-empty chain_id"):
        verify_chain_with_signatures(chain, [], chain_id="", trust_roots=tr, verification_time=_NOW)


# ---------------------------------------------------------------------------
# Line 383: verify_chain_with_signatures naive verification_time raises
# ---------------------------------------------------------------------------


def test_verify_chain_with_signatures_naive_verification_time_raises() -> None:
    """Line 383: naive verification_time → SigningError."""
    chain = _build_chain(2)
    tr = _trust_roots(_trust_root_entry(_SEED_00))
    naive = datetime(2026, 5, 17, 12, 0, 0)  # no tzinfo
    with pytest.raises(SigningError, match="UTC-aware"):
        verify_chain_with_signatures(chain, [], chain_id="x", trust_roots=tr, verification_time=naive)


# ---------------------------------------------------------------------------
# Line 406: verify_chain_full signatures but trust_roots is None
# ---------------------------------------------------------------------------


def test_verify_chain_full_signatures_without_trust_roots_raises() -> None:
    """Line 406: signatures present but trust_roots=None → SigningError."""
    chain = _build_chain(2)
    signer = Signer(chain_id="x", key_provider=InMemoryKeyProvider(seed=_SEED_00), now=lambda: _NOW)
    records = signer.sign_segment_head(ChainHead(seq=1, event_hash=chain[1].event_hash))
    with pytest.raises(SigningError, match="trust_roots"):
        verify_chain_full(chain, signatures=records, chain_id="x", trust_roots=None)


# ---------------------------------------------------------------------------
# Line 406: verify_chain_with_signatures with empty signatures list → "unsigned"
# ---------------------------------------------------------------------------


def test_verify_chain_with_signatures_empty_list_returns_unsigned() -> None:
    """Line 406: empty signatures list → signature_status 'unsigned', count 0."""
    chain = _build_chain(3)
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    status, results, count, first_bad = verify_chain_with_signatures(
        chain,
        [],  # empty signatures list
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    assert status == "unsigned"
    assert results == ()
    assert count == 0
    assert first_bad is None


# ---------------------------------------------------------------------------
# Lines 287->301: per_event matching payload → valid (branch coverage)
# ---------------------------------------------------------------------------


def test_verify_single_signature_per_event_matching_payload_valid() -> None:
    """Lines 287->301: per_event mode, payload matches → returns valid at line 301."""
    chain = _build_chain(3)
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    # Build a per_event record with the correct payload
    record = _make_valid_record(_SEED_00, chain, 2, mode="per_event")

    result = _verify_single_signature(
        record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    # Should reach the valid return at line 301 via the elif per_event branch (287->301)
    assert result.status == "valid"
    assert result.reason is None


def test_verify_single_signature_unknown_mode_falls_through_to_valid() -> None:
    """Branch 287->301: signature_mode is neither segment_head nor per_event.

    This branch is labeled unreachable in the source comment (Literal types),
    but we trigger it via _tamper_record to achieve branch coverage.
    The record is cryptographically valid (correct signature over signed_payload),
    the seq is in chain, and event_hash matches → returns valid.
    """
    chain = _build_chain(3)
    tr = _trust_roots(_trust_root_entry(_SEED_00))

    # Build a segment_head record but change mode to something else after signing
    provider = InMemoryKeyProvider(seed=_SEED_00)
    mat = provider.get_signing_material()

    # Build a payload and signature but set an unexpected mode string
    from attestplane.signing.signer import _build_segment_head_payload
    head = ChainHead(seq=2, event_hash=chain[2].event_hash)
    payload = _build_segment_head_payload("test-chain", head)
    sig = mat.private_key.sign(payload)

    base_record = _tamper_record(
        _make_valid_record(_SEED_00, chain, 2),
        signed_payload=payload,
        signature=sig,
        signature_mode="segment_head",  # must be valid Literal for post_init
    )

    # Now forcefully set to unknown mode bypassing Literal check
    bad_record = _tamper_record(base_record, signature_mode="unknown_mode")  # type: ignore[arg-type]

    result = _verify_single_signature(
        bad_record,
        index=0,
        events_by_seq={ev.seq: ev for ev in chain},
        chain_id="test-chain",
        trust_roots=tr,
        verification_time=_NOW,
    )
    # Falls through the if/elif without entering either body → valid at line 301
    assert result.status == "valid"
