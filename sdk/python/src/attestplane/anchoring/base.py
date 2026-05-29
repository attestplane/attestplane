# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Abstract types for RFC-3161 anchoring per ADR-0003.

This module ships the **design skeleton** for the v0.1 / M5 anchoring
work. It contains:

- :class:`AnchorRecord` — the persistent anchor row (ADR-0003 § 1)
- :class:`AnchorPolicy` — anchor-trigger policy (ADR-0003 § 3)
- :class:`TSAProvider` — abstract base for TSA implementations
- Error hierarchy

It does **not** ship:

- Real ASN.1 / RFC-3161 parsing (depends on the ``cryptography``
  library; ships in a follow-up PR alongside conformance vectors)
- Live TSA HTTP clients (FreeTSA, DigiCert)
- OCSP / CRL responder integration

The skeleton is sufficient to wire :class:`TSAProvider` subclasses
into the substrate, run the M5 anchorer worker design through
unit tests using :class:`~attestplane.anchoring.mock.MockTSAProvider`,
and verify the boundary discipline (no forbidden mutating verbs).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal

ANCHOR_SCHEMA_VERSION: Final[int] = 1
"""Anchor schema version. Independent of ``chain.schema_version`` per ADR-0003 § 7."""


AnchorStatus = Literal["unanchored", "pending", "anchored", "failed_permanent"]


class AnchorError(Exception):
    """Base class for anchoring errors."""


class TSAUnavailableError(AnchorError):
    """TSA endpoint is unreachable, timed out, or returned a 5xx.

    The :class:`Anchorer` worker retries on this error with exponential
    backoff per ADR-0003 § 4 ("Anchoring is never on the ``append()``
    critical path").
    """


class AnchorVerificationError(AnchorError):
    """An anchor failed verification.

    Distinct from :class:`TSAUnavailableError`: the TSA was reachable,
    but the resulting :class:`AnchorRecord` does not match the chain
    it claims to anchor (hash mismatch, cardinality mismatch,
    timestamp regression, expired cert at issuance, etc.).
    """


class AnchorQuarantineError(TSAUnavailableError, AnchorVerificationError):
    """A live anchor could not be claim-safely verified.

    This is the quarantine branch for transport / CA / trust-root
    failures where the caller must not emit a hard anchoring claim.
    It intentionally subclasses both :class:`TSAUnavailableError` and
    :class:`AnchorVerificationError` so existing live-nightly callers
    can keep treating it as a neutral TSA-side outcome, while the
    verifier surface can distinguish it from tamper or structural
    failures.
    """


class AnchorBoundaryError(TypeError):
    """A :class:`TSAProvider` subclass defines a forbidden mutating verb."""


@dataclass(frozen=True, slots=True)
class AnchorRecord:
    """One anchor for one chain head, per ADR-0003 § 1.

    Anchors are **sidecar** records — never inputs to the canonical-JSON
    encoding used for ``event_hash``. ``ChainedEvent.schema_version``
    stays at ``1`` regardless of anchor state.

    :param anchor_schema_version: matches :data:`ANCHOR_SCHEMA_VERSION`
    :param anchored_seq: the ``seq`` of the chain head this anchor refers to
    :param anchored_event_hash: the ``event_hash`` of that head (32 bytes)
    :param tsa_provider_id: short stable id of the TSA, e.g., ``"freetsa.org"``
    :param tsa_token: RFC-3161 TimeStampToken DER bytes
    :param tsa_cert_chain: full cert chain bytes (DER) frozen at issuance
        for CAdES-A long-term validation (ADR-0003 § 6)
    :param ocsp_responses: OCSP responses for the cert chain, also
        frozen at issuance
    :param issued_at_claimed: the TSA's claimed ``genTime``, parsed from
        the token. Informational; the authoritative time is inside the
        signed ``tsa_token``.
    """

    anchor_schema_version: int
    anchored_seq: int
    anchored_event_hash: bytes
    tsa_provider_id: str
    tsa_token: bytes
    tsa_cert_chain: tuple[bytes, ...]
    ocsp_responses: tuple[bytes, ...]
    issued_at_claimed: datetime

    def __post_init__(self) -> None:
        if self.anchor_schema_version != ANCHOR_SCHEMA_VERSION:
            raise AnchorError(
                f"AnchorRecord.anchor_schema_version must be {ANCHOR_SCHEMA_VERSION}, got {self.anchor_schema_version}"
            )
        if len(self.anchored_event_hash) != 32:
            raise AnchorError(f"AnchorRecord.anchored_event_hash must be 32 bytes, got {len(self.anchored_event_hash)}")
        if self.anchored_seq < 0:
            raise AnchorError("AnchorRecord.anchored_seq must be ≥ 0")
        if not self.tsa_provider_id:
            raise AnchorError("AnchorRecord.tsa_provider_id must be non-empty")


@dataclass(frozen=True, slots=True)
class AnchorPolicy:
    """When the Anchorer worker fires an anchor request, per ADR-0003 § 3.

    Default policy: anchor whenever ``batch_size`` events have
    accumulated OR ``max_idle_seconds`` have elapsed since the last
    unanchored append, whichever fires first.

    Per-event anchoring (``per_event=True``) is opt-in for high-value
    low-volume cases like signing ceremonies or irreversible legal
    actions.
    """

    batch_size: int = 64
    max_idle_seconds: int = 60
    per_event: bool = False

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise AnchorError("AnchorPolicy.batch_size must be ≥ 1")
        if self.max_idle_seconds < 1:
            raise AnchorError("AnchorPolicy.max_idle_seconds must be ≥ 1")


@dataclass(frozen=True, slots=True)
class TimestampRequest:
    """One TSA request: a hash to be stamped.

    Per RFC-3161, a TimestampRequest carries the hash algorithm OID
    and the hash digest. Attestplane v1 always uses SHA-256, so the
    algorithm is implicit.
    """

    digest: bytes
    """SHA-256 digest of the chain head (or per-event hash) to be anchored."""

    nonce: bytes | None = None
    """Optional client-side nonce per RFC-3161 § 2.4.1; included in the
    response if set, providing client-side replay protection."""

    def __post_init__(self) -> None:
        if len(self.digest) != 32:
            raise AnchorError(f"TimestampRequest.digest must be 32 bytes (SHA-256), got {len(self.digest)}")


class TSAProvider(ABC):
    """Abstract base for any TSA provider implementation.

    The contract is intentionally narrow:

    1. :meth:`request_timestamp` is the only abstract method.
    2. Implementations are **stateless** with respect to the chain:
       they hash a request, hand it to the TSA, and return the
       resulting :class:`AnchorRecord` shell. They do not know about
       events, runs, sessions, or any substrate-level state beyond
       the digest.
    3. Implementations MUST snapshot ``tsa_cert_chain`` and
       ``ocsp_responses`` at request time per ADR-0003 § 6
       (CAdES-A long-term validation). A provider that defers cert /
       OCSP capture is non-conforming.

    Implementations declare two metadata properties:

    - :attr:`provider_id` — short stable id of the TSA service, e.g.
      ``"freetsa.org"`` or ``"digicert.tsa-2026"``. Used in the
      ``tsa_provider_id`` field of :class:`AnchorRecord`.
    - :attr:`schema_version` — the anchor schema version this provider
      targets. v0.1 providers MUST emit ``schema_version == 1``.

    The ``__init_subclass__`` hook rejects forbidden mutating verb
    names mirroring :class:`~attestplane.adapters.GenericRuntimeAdapter`
    and :class:`~attestplane.storage.AbstractStorageBackend`. The
    forbidden set for TSA providers covers:

    - ``mutate``, ``rewrite``, ``replace``
    - ``revoke``, ``retract``
    - ``delete``, ``remove``

    These imply the provider has authority over the timestamp's
    validity, which it does not — the TSA controls revocation, and
    anchor verification reads OCSP at verification time.
    """

    provider_id: str
    schema_version: int

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        forbidden = {
            "mutate",
            "rewrite",
            "replace",
            "revoke",
            "retract",
            "delete",
            "remove",
        }
        offenders = sorted(name for name in vars(cls) if not name.startswith("_") and name in forbidden)
        if offenders:
            raise AnchorBoundaryError(
                f"{cls.__name__} defines forbidden mutating method(s) {offenders}; "
                f"TSA providers do not own anchor validity. See ADR-0003 § 4."
            )

    @abstractmethod
    def request_timestamp(self, request: TimestampRequest) -> AnchorRecord:
        """Submit a TimestampRequest to the TSA and return the anchor.

        Implementations MUST:

        - Raise :class:`TSAUnavailableError` on network errors, 5xx
          responses, or non-RFC-3161 response bodies.
        - Validate the returned token's structure before constructing
          the :class:`AnchorRecord`. Malformed responses raise
          :class:`AnchorVerificationError`, not
          :class:`TSAUnavailableError` — the distinction matters because
          the Anchorer worker retries on the former and quarantines on
          the latter (ADR-0003 § 4 failure-mode table).
        - Capture ``tsa_cert_chain`` and ``ocsp_responses`` at request
          time. A provider that returns an empty cert chain or empty
          OCSP list is non-conforming.
        - Be safe to call from multiple threads if the implementation
          advertises thread-safety; otherwise document the contract.
        """
        raise NotImplementedError


__all__ = [
    "ANCHOR_SCHEMA_VERSION",
    "AnchorBoundaryError",
    "AnchorError",
    "AnchorPolicy",
    "AnchorRecord",
    "AnchorStatus",
    "AnchorVerificationError",
    "TSAProvider",
    "TSAUnavailableError",
    "TimestampRequest",
]
