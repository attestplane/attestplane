# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.signing.base` (T1 ticket).

Pins:
- SIGNATURE_SCHEMA_VERSION = 1.
- SignatureRecord invariants (32-byte hash, 64-byte sig, key_id
  derives from public_key_der).
- SignaturePolicy defaults + invariants.
- KeyProvider __init_subclass__ forbidden-verb gate (4 verbs).
- derive_key_id stability + format.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from attestplane.signing.base import (
    SIGNATURE_SCHEMA_VERSION,
    KeyBoundaryError,
    KeyProvider,
    SignatureRecord,
    SignaturePolicy,
    SigningError,
    SigningMaterial,
    derive_key_id,
)


def _fresh_signing_material() -> SigningMaterial:
    key = Ed25519PrivateKey.generate()
    return SigningMaterial(private_key=key)


def _public_der(mat: SigningMaterial) -> bytes:
    return mat.public_key_der


# --- Constants -------------------------------------------------------------


def test_signature_schema_version_is_one() -> None:
    assert SIGNATURE_SCHEMA_VERSION == 1


# --- SigningMaterial -------------------------------------------------------


def test_signing_material_exposes_public_key() -> None:
    mat = _fresh_signing_material()
    assert mat.public_key is not None
    assert isinstance(mat.public_key_der, bytes)
    assert len(mat.public_key_der) > 32  # SPKI overhead on top of 32-byte raw key
    assert mat.signing_cert_chain == ()


def test_signing_material_key_id_is_16_byte_hex() -> None:
    mat = _fresh_signing_material()
    kid = mat.key_id
    assert len(kid) == 32  # 16 bytes hex = 32 chars
    int(kid, 16)  # must parse as hex
    assert kid == kid.lower()


def test_signing_material_key_id_stable_for_same_key() -> None:
    seed = bytes(32)  # all zeros for deterministic test
    key = Ed25519PrivateKey.from_private_bytes(seed)
    a = SigningMaterial(private_key=key)
    b = SigningMaterial(private_key=key)
    assert a.key_id == b.key_id


# --- derive_key_id ---------------------------------------------------------


def test_derive_key_id_rejects_empty_input() -> None:
    with pytest.raises(SigningError, match="non-empty"):
        derive_key_id(b"")


def test_derive_key_id_first_16_sha256_bytes() -> None:
    import hashlib
    der = _public_der(_fresh_signing_material())
    expected = hashlib.sha256(der).digest()[:16].hex()
    assert derive_key_id(der) == expected


# --- SignatureRecord -------------------------------------------------------


def _good_record(**overrides) -> SignatureRecord:
    mat = _fresh_signing_material()
    der = _public_der(mat)
    base = dict(
        signature_schema_version=SIGNATURE_SCHEMA_VERSION,
        signed_seq=0,
        signed_event_hash=b"\x00" * 32,
        signature=b"\x00" * 64,
        key_id=derive_key_id(der),
        public_key_der=der,
        signing_cert_chain=(),
        signed_at=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC),
        signature_mode="segment_head",
        signed_payload=b"canonical-bytes",
    )
    base.update(overrides)
    return SignatureRecord(**base)


def test_signature_record_constructs_with_defaults() -> None:
    r = _good_record()
    assert r.signature_mode == "segment_head"
    assert r.signing_cert_chain == ()


def test_signature_record_rejects_wrong_schema_version() -> None:
    with pytest.raises(SigningError, match="signature_schema_version"):
        _good_record(signature_schema_version=2)


def test_signature_record_rejects_negative_seq() -> None:
    with pytest.raises(SigningError, match="signed_seq"):
        _good_record(signed_seq=-1)


def test_signature_record_rejects_wrong_hash_length() -> None:
    with pytest.raises(SigningError, match="32 bytes"):
        _good_record(signed_event_hash=b"\x00" * 16)


def test_signature_record_rejects_wrong_signature_length() -> None:
    with pytest.raises(SigningError, match="64 bytes"):
        _good_record(signature=b"\x00" * 32)


def test_signature_record_rejects_empty_key_id() -> None:
    with pytest.raises(SigningError, match="key_id"):
        _good_record(key_id="")


def test_signature_record_rejects_empty_public_key() -> None:
    with pytest.raises(SigningError, match="public_key_der"):
        _good_record(public_key_der=b"")


def test_signature_record_rejects_bad_mode() -> None:
    with pytest.raises(SigningError, match="signature_mode"):
        _good_record(signature_mode="weird_mode")


def test_signature_record_rejects_empty_signed_payload() -> None:
    with pytest.raises(SigningError, match="signed_payload"):
        _good_record(signed_payload=b"")


def test_signature_record_rejects_key_id_mismatch() -> None:
    """key_id MUST be derivable from public_key_der; mismatch is a tamper signal."""
    with pytest.raises(SigningError, match="does not match"):
        _good_record(key_id="ff" * 16)


def test_signature_record_per_event_mode_accepted() -> None:
    r = _good_record(signature_mode="per_event")
    assert r.signature_mode == "per_event"


# --- SignaturePolicy --------------------------------------------------------


def test_signature_policy_defaults() -> None:
    p = SignaturePolicy()
    assert p.batch_size == 64
    assert p.max_idle_seconds == 60
    assert p.per_event is False


def test_signature_policy_rejects_zero_batch() -> None:
    with pytest.raises(SigningError, match="batch_size"):
        SignaturePolicy(batch_size=0)


def test_signature_policy_rejects_zero_idle() -> None:
    with pytest.raises(SigningError, match="max_idle_seconds"):
        SignaturePolicy(max_idle_seconds=0)


def test_signature_policy_per_event_opt_in() -> None:
    p = SignaturePolicy(per_event=True)
    assert p.per_event is True


# --- KeyProvider abstract + forbidden verbs -------------------------------


def test_key_provider_abstract_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        KeyProvider()  # type: ignore[abstract]


@pytest.mark.parametrize(
    "verb",
    ["revoke", "rotate", "delete", "replace"],
)
def test_key_provider_subclass_rejects_forbidden_verb(verb: str) -> None:
    def make_bad() -> None:
        namespace = {
            "provider_id": "bad",
            "schema_version": SIGNATURE_SCHEMA_VERSION,
            "get_signing_material": lambda self: None,
            verb: lambda self, *a, **kw: None,
        }
        type("BadProvider", (KeyProvider,), namespace)

    with pytest.raises(KeyBoundaryError, match="forbidden mutating method"):
        make_bad()


def test_key_provider_private_helper_with_forbidden_stem_allowed() -> None:
    """Leading underscore exempts; only public names are gated."""
    class GoodProvider(KeyProvider):
        provider_id = "good"
        schema_version = SIGNATURE_SCHEMA_VERSION

        def get_signing_material(self) -> SigningMaterial:
            self._rotate_internal_buffer()
            return _fresh_signing_material()

        def _rotate_internal_buffer(self) -> None:
            return

    p = GoodProvider()
    mat = p.get_signing_material()
    assert mat is not None
