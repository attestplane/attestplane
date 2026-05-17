# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Event-signing abstract base types per ADR-0005 architect plan.

Ticket **T1** of `docs/architecture/adr_0005_signing_plan_20260517.md`.

This module ships the **abstract surface** of the signing scheme:

- :data:`SIGNATURE_SCHEMA_VERSION` — independent of chain + anchor schemas.
- :class:`SigningMaterial` — value carrying the Ed25519 private key
  and an optional cert chain (Fulcio hook reserved).
- :class:`SignatureRecord` — sidecar dataclass (mirrors
  :class:`~attestplane.anchoring.AnchorRecord`).
- :class:`SignaturePolicy` — when the Signer fires.
- :class:`KeyProvider` — abstract base with
  ``__init_subclass__`` forbidden-verb gate.
- Error hierarchy rooted at :class:`SigningError`.

It does **not** ship concrete key providers (those live in
:mod:`attestplane.signing.providers`, ticket T2) nor the Signer
worker (T3) nor the verifier extension (T4).

Hard constraint preserved per architect plan § 1 hard constraint #1:
this module adds NO fields to :class:`~attestplane.types.AuditEvent`
and does NOT change canonical-JSON output. v0.0.1-alpha
``vectors.json`` continues to verify byte-for-byte regardless of
anything in this file.

ADR-0004 § 1 boundary preserved: KeyProvider subclasses MUST NOT
declare ``revoke`` / ``rotate`` / ``delete`` / ``replace`` public
methods. A KeyProvider holds key *access*, not key *authority*; key
lifecycle (creation, rotation, retirement) is the deployer's
operational responsibility, not the substrate's.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attestplane.signing requires the 'signing' extras. "
        "Install with: pip install attestplane[signing]"
    ) from exc


SIGNATURE_SCHEMA_VERSION: Final[int] = 1
"""Frozen at 1 for v1. Independent of ``chain.schema_version`` and
``anchor_schema_version``."""


SignatureMode = Literal["segment_head", "per_event"]
"""Distinguishes the two granularity modes locked in architect plan § 1 A."""


class SigningError(Exception):
    """Base class for signing-subsystem errors."""


class KeyProviderError(SigningError):
    """A KeyProvider failed to supply signing material (file missing,
    bad passphrase, env var unset, ...)."""


class SignatureVerificationError(SigningError):
    """A produced signature failed verification, OR a SignatureRecord
    cannot be verified against the configured trust roots."""


class KeyBoundaryError(TypeError):
    """A :class:`KeyProvider` subclass declares a forbidden mutating verb."""


# --- Data model -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SigningMaterial:
    """Bundles a signing key with optional Fulcio-cert support.

    v1: ``signing_cert_chain`` is always empty. ADR-0007 (Fulcio/OIDC)
    will fill it with short-lived OIDC certs without bumping
    :data:`SIGNATURE_SCHEMA_VERSION`.

    :class:`SigningMaterial` is intentionally NOT exposed to callers
    directly — :class:`KeyProvider` returns it, :class:`Signer` consumes
    it, and the private key bytes never leave this layer.
    """

    private_key: Ed25519PrivateKey
    signing_cert_chain: tuple[bytes, ...] = ()

    @property
    def public_key(self) -> Ed25519PublicKey:
        """Convenience accessor — same as ``private_key.public_key()``."""
        return self.private_key.public_key()

    @property
    def public_key_der(self) -> bytes:
        """SubjectPublicKeyInfo DER bytes of the public key."""
        der: bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return der

    @property
    def key_id(self) -> str:
        """Stable 16-byte key fingerprint (hex of first 16 SHA-256
        bytes over the public-key DER)."""
        return derive_key_id(self.public_key_der)


def derive_key_id(public_key_der: bytes) -> str:
    """Compute the stable 16-byte hex key_id per architect plan § 1 D.

    First 16 bytes of SHA-256(public_key_DER), lowercase hex.
    """
    if not public_key_der:
        raise SigningError("derive_key_id: public_key_der must be non-empty")
    return hashlib.sha256(public_key_der).digest()[:16].hex()


@dataclass(frozen=True, slots=True)
class SignatureRecord:
    """One signature for one event (or segment head).

    Sidecar per architect plan § 1 B (option B3). ``ChainedEvent``
    bytes are untouched; the v0.0.1-alpha conformance vectors continue
    to verify byte-for-byte.

    :param signature_schema_version: matches :data:`SIGNATURE_SCHEMA_VERSION`.
    :param signed_seq: chain seq of the event (or segment head) covered.
    :param signed_event_hash: the 32-byte SHA-256 ``event_hash`` of the
        covered event (or segment head). Verifier uses this to locate
        the corresponding :class:`~attestplane.types.ChainedEvent`.
    :param signature: Ed25519 signature bytes (64 bytes).
    :param key_id: 16-byte hex fingerprint of the signing public key.
    :param public_key_der: SubjectPublicKeyInfo DER bytes. Carried inside
        the record so signatures verify offline against the embedded
        pubkey; trust-roots lookup uses ``key_id`` to confirm authority.
    :param signing_cert_chain: optional X.509 cert chain (DER blobs).
        Empty in v1; ADR-0007 fills with Fulcio short certs.
    :param signed_at: when the signature was computed (caller clock,
        not authoritative).
    :param signature_mode: ``"segment_head"`` or ``"per_event"``.
    :param signed_payload: the canonical-JSON bytes that were signed.
        Stored alongside the signature so verifiers can re-hash and
        cross-check without re-canonicalising. ALL bytes here came
        from :func:`attestplane.canonical.canonicalize`; this field
        is what the architect plan § 1 C calls "the bytes signed".
    """

    signature_schema_version: int
    signed_seq: int
    signed_event_hash: bytes
    signature: bytes
    key_id: str
    public_key_der: bytes
    signing_cert_chain: tuple[bytes, ...]
    signed_at: datetime
    signature_mode: SignatureMode
    signed_payload: bytes

    def __post_init__(self) -> None:
        if self.signature_schema_version != SIGNATURE_SCHEMA_VERSION:
            raise SigningError(
                f"SignatureRecord.signature_schema_version must be "
                f"{SIGNATURE_SCHEMA_VERSION}, got {self.signature_schema_version}"
            )
        if self.signed_seq < 0:
            raise SigningError("SignatureRecord.signed_seq must be ≥ 0")
        if len(self.signed_event_hash) != 32:
            raise SigningError(
                f"SignatureRecord.signed_event_hash must be 32 bytes, "
                f"got {len(self.signed_event_hash)}"
            )
        if len(self.signature) != 64:
            raise SigningError(
                f"SignatureRecord.signature must be 64 bytes (Ed25519), "
                f"got {len(self.signature)}"
            )
        if not self.key_id:
            raise SigningError("SignatureRecord.key_id must be non-empty")
        if not self.public_key_der:
            raise SigningError("SignatureRecord.public_key_der must be non-empty")
        if self.signature_mode not in ("segment_head", "per_event"):
            raise SigningError(
                f"SignatureRecord.signature_mode must be 'segment_head' "
                f"or 'per_event', got {self.signature_mode!r}"
            )
        if not self.signed_payload:
            raise SigningError("SignatureRecord.signed_payload must be non-empty")
        # Cross-check: derived key_id matches what's stored.
        expected_key_id = derive_key_id(self.public_key_der)
        if self.key_id != expected_key_id:
            raise SigningError(
                f"SignatureRecord.key_id={self.key_id!r} does not match "
                f"derived from public_key_der ({expected_key_id!r})"
            )


@dataclass(frozen=True, slots=True)
class SignaturePolicy:
    """When the Signer worker fires.

    Mirrors :class:`~attestplane.anchoring.AnchorPolicy` shape per
    architect plan § 1 A. v1 defaults: segment-head signing every 64
    events OR 60 seconds idle, whichever fires first.

    Per-event signing is opt-in (``per_event=True``); recommended only
    for low-volume / high-value events (legal-grade individual proofs).
    """

    batch_size: int = 64
    max_idle_seconds: int = 60
    per_event: bool = False

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise SigningError("SignaturePolicy.batch_size must be ≥ 1")
        if self.max_idle_seconds < 1:
            raise SigningError("SignaturePolicy.max_idle_seconds must be ≥ 1")


# --- KeyProvider abstract base ----------------------------------------------


_FORBIDDEN_KEY_PROVIDER_VERBS: Final[frozenset[str]] = frozenset({
    "revoke", "rotate", "delete", "replace",
})


class KeyProvider(ABC):
    """Abstract base for any signing-key access strategy.

    Concrete providers ship in :mod:`attestplane.signing.providers`
    (T2 ticket): :class:`InMemoryKeyProvider`,
    :class:`FileKeyProvider`, :class:`EnvKeyProvider`,
    :class:`MultiSignerProvider`.

    The forbidden-verb gate (``__init_subclass__``) rejects subclasses
    that declare any of the four reserved mutating verbs (``revoke``,
    ``rotate``, ``delete``, ``replace``) at the public level. ADR-0004
    § 1 universal rule: substrate components hold *access*, not
    *authority*. Key lifecycle (creation / rotation / revocation /
    deletion) is the deployer's operational responsibility — exposing
    those verbs on a KeyProvider would invite callers to invoke them
    against the substrate, violating the boundary.

    Implementations declare two metadata properties:

    - :attr:`provider_id` — short stable id, e.g. ``"in-memory:dev"``,
      ``"file:/etc/attestplane/key.pem"``, ``"env:ATTESTPLANE_KEY"``.
      Embedded in :class:`SignatureRecord.public_key_der`-derived
      ``key_id`` provenance trails.
    - :attr:`schema_version` — matches :data:`SIGNATURE_SCHEMA_VERSION`.

    Concurrency: implementations MUST be safe for concurrent
    :meth:`get_signing_material` calls. The Signer worker (T3) calls
    this on its hot path.
    """

    provider_id: str
    schema_version: int

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        offenders = sorted(
            name
            for name in vars(cls)
            if not name.startswith("_") and name in _FORBIDDEN_KEY_PROVIDER_VERBS
        )
        if offenders:
            raise KeyBoundaryError(
                f"{cls.__name__} declares forbidden mutating method(s) {offenders}; "
                f"KeyProvider holds key access, not key authority. "
                f"See ADR-0004 § 1 + adr_0005_signing_plan_20260517 § 1 D."
            )

    @abstractmethod
    def get_signing_material(self) -> SigningMaterial:
        """Return the current :class:`SigningMaterial`.

        Implementations MUST be deterministic (same instance state →
        same key returned). MUST be safe for concurrent calls. MAY
        raise :class:`KeyProviderError` on transient unavailability
        (file moved, env var unset, KMS down) — caller decides whether
        to retry or fail.
        """
        raise NotImplementedError


__all__ = [
    "SIGNATURE_SCHEMA_VERSION",
    "KeyBoundaryError",
    "KeyProvider",
    "KeyProviderError",
    "SignatureMode",
    "SignaturePolicy",
    "SignatureRecord",
    "SignatureVerificationError",
    "SigningError",
    "SigningMaterial",
    "derive_key_id",
]
