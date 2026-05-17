# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Live RFC-3161 HTTP transport for TSA providers.

Two layers:

- :class:`HttpTransport` (abstract) + :class:`UrllibHttpTransport`
  (concrete, stdlib-only) — submits a DER-encoded TimeStampReq via
  HTTP and returns the DER response.
- :class:`Rfc3161HttpProvider` — concrete :class:`TSAProvider` that
  builds the request, calls the transport, parses + verifies the
  response, and constructs the :class:`AnchorRecord`.

Two pre-configured providers ship: :class:`FreeTSAProvider` and
:class:`DigiCertProvider`. Each is a thin :class:`Rfc3161HttpProvider`
with the right URL + ``provider_id`` and (optionally) ``trust_roots_der``
captured at construction time so the verifier can later validate the
signature.

Production deployments inject a real :class:`UrllibHttpTransport` (or a
``requests``-based transport in a subclass). Tests inject a recorded /
mock transport via the ``transport`` parameter — the
:func:`make_replay_transport` helper builds one from a captured DER
response.
"""

from __future__ import annotations

import urllib.request
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Callable, Final

try:
    from asn1crypto import algos, tsp
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attestplane.anchoring.http requires the 'anchor' extras. "
        "Install with: pip install attestplane[anchor]"
    ) from exc

from attestplane.anchoring.base import (
    ANCHOR_SCHEMA_VERSION,
    AnchorRecord,
    AnchorVerificationError,
    TimestampRequest,
    TSAProvider,
    TSAUnavailableError,
)
from attestplane.anchoring.rfc3161 import (
    parse_timestamp_response,
    verify_timestamp_token,
)


RFC3161_CONTENT_TYPE_REQUEST: Final[str] = "application/timestamp-query"
RFC3161_CONTENT_TYPE_RESPONSE: Final[str] = "application/timestamp-reply"


class HttpTransport(ABC):
    """Abstract HTTP transport — submits an RFC-3161 request blob.

    Concrete transports MUST return the raw response body (DER bytes),
    or raise :class:`TSAUnavailableError` on network failure, timeout,
    5xx, or non-RFC-3161 content type. Returning malformed DER is
    permitted (the parser raises :class:`AnchorVerificationError`
    downstream); transports should NOT attempt to parse the body.
    """

    @abstractmethod
    def submit(self, url: str, request_der: bytes, *, timeout_seconds: float = 30.0) -> bytes:
        """POST ``request_der`` to ``url`` and return the response body."""
        raise NotImplementedError


class UrllibHttpTransport(HttpTransport):
    """Stdlib-only HTTP transport.

    Suitable for production for low-volume use cases; for high-volume
    deployments wrap a connection-pooling client (``requests``,
    ``httpx``) in a subclass.
    """

    def __init__(self, *, user_agent: str = "attestplane/0.0.2-alpha") -> None:
        self._user_agent = user_agent

    def submit(self, url: str, request_der: bytes, *, timeout_seconds: float = 30.0) -> bytes:
        req = urllib.request.Request(
            url,
            data=request_der,
            method="POST",
            headers={
                "Content-Type": RFC3161_CONTENT_TYPE_REQUEST,
                "Accept": RFC3161_CONTENT_TYPE_RESPONSE,
                "User-Agent": self._user_agent,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if RFC3161_CONTENT_TYPE_RESPONSE not in content_type:
                    raise TSAUnavailableError(
                        f"TSA at {url} returned unexpected Content-Type: {content_type!r}"
                    )
                body = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TSAUnavailableError(
                f"TSA at {url} unreachable: {exc}"
            ) from exc
        if not body:
            raise TSAUnavailableError(f"TSA at {url} returned empty body")
        body_bytes: bytes = body
        return body_bytes


class RecordedHttpTransport(HttpTransport):
    """Test-only transport that replays a captured DER blob.

    Useful for taking one real TSA response, freezing it as a fixture,
    and replaying it deterministically. Ignores the request bytes
    entirely (the digest does NOT need to match what's inside the
    captured response — the verifier catches that).
    """

    def __init__(self, response_der: bytes) -> None:
        self._response_der = response_der

    def submit(self, url: str, request_der: bytes, *, timeout_seconds: float = 30.0) -> bytes:
        return self._response_der


def make_replay_transport(response_der: bytes) -> HttpTransport:
    """Convenience constructor — wraps :class:`RecordedHttpTransport`."""
    return RecordedHttpTransport(response_der)


def _build_request_der(digest: bytes, *, nonce: bytes | None = None) -> bytes:
    """Build a DER-encoded :class:`asn1crypto.tsp.TimeStampReq` payload."""
    body: dict[str, object] = {
        "version": "v1",
        "message_imprint": tsp.MessageImprint({
            "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
            "hashed_message": digest,
        }),
        "cert_req": True,
    }
    if nonce is not None:
        body["nonce"] = int.from_bytes(nonce, "big")
    der_bytes: bytes = tsp.TimeStampReq(body).dump()
    return der_bytes


class Rfc3161HttpProvider(TSAProvider):
    """TSA provider that submits requests to a live RFC-3161 endpoint.

    :param provider_id: stable id embedded in :class:`AnchorRecord`.
    :param url: RFC-3161 endpoint URL.
    :param transport: HTTP transport implementation.
    :param trust_roots_der: optional list of DER-encoded trust-root
        certs. When provided, the provider verifies the TSA's signature
        against these roots **before** returning the
        :class:`AnchorRecord`; verification failures raise
        :class:`AnchorVerificationError`. When ``None``, the provider
        returns an :class:`AnchorRecord` whose ``tsa_cert_chain`` is
        captured from the response (or empty if none was included) and
        defers signature verification to the caller's
        :func:`~attestplane.anchoring.verify_chain_with_anchors` call.
    :param ocsp_responses_der: optional list of pre-fetched OCSP
        responses to attach to every issued :class:`AnchorRecord`.
        Required to satisfy ADR-0003 § 6 CAdES-A invariant; without
        these, downstream verifiers reject the anchor as missing LTV.
    :param timeout_seconds: per-request HTTP timeout.
    """

    schema_version = ANCHOR_SCHEMA_VERSION

    def __init__(
        self,
        provider_id: str,
        *,
        url: str,
        transport: HttpTransport,
        trust_roots_der: list[bytes] | None = None,
        ocsp_responses_der: list[bytes] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not provider_id:
            raise ValueError("Rfc3161HttpProvider provider_id must be non-empty")
        if not url:
            raise ValueError("Rfc3161HttpProvider url must be non-empty")
        self.provider_id = provider_id
        self._url = url
        self._transport = transport
        self._trust_roots_der = list(trust_roots_der) if trust_roots_der else None
        self._ocsp_responses_der = list(ocsp_responses_der) if ocsp_responses_der else []
        self._timeout = timeout_seconds

    def request_timestamp(
        self,
        request: TimestampRequest,
        *,
        anchored_seq: int = 0,
        now: datetime | None = None,
    ) -> AnchorRecord:
        request_der = _build_request_der(request.digest, nonce=request.nonce)
        response_der = self._transport.submit(
            self._url, request_der, timeout_seconds=self._timeout,
        )
        try:
            parsed = parse_timestamp_response(response_der)
        except AnchorVerificationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AnchorVerificationError(
                f"failed to parse TSA response from {self._url}: {exc}"
            ) from exc

        if parsed.message_imprint != request.digest:
            raise AnchorVerificationError(
                f"TSA at {self._url} returned wrong messageImprint"
            )
        if request.nonce is not None:
            expected_nonce = int.from_bytes(request.nonce, "big")
            if parsed.nonce != expected_nonce:
                raise AnchorVerificationError(
                    "TSA response nonce does not match request nonce"
                )

        # If trust roots were configured, verify the signature before
        # producing an AnchorRecord — fail fast at request time.
        if self._trust_roots_der is not None:
            verify_timestamp_token(
                parsed,
                expected_digest=request.digest,
                trust_roots_der=self._trust_roots_der,
                verification_time=now or datetime.now(UTC),
            )

        gen_time = parsed.gen_time
        # cert chain: at minimum the leaf cert extracted from the
        # response. Production deployments may extend this with
        # intermediates captured from elsewhere (eIDAS Trusted List, the
        # TSA's published chain page, etc.); for v0.0.2-alpha we ship
        # just the leaf from the response, callers extend via subclass.
        cert_chain: tuple[bytes, ...] = (parsed.leaf_cert_der,)
        if self._trust_roots_der:
            # Append configured roots so downstream verifiers find them.
            cert_chain = cert_chain + tuple(self._trust_roots_der)

        return AnchorRecord(
            anchor_schema_version=ANCHOR_SCHEMA_VERSION,
            anchored_seq=anchored_seq,
            anchored_event_hash=request.digest,
            tsa_provider_id=self.provider_id,
            tsa_token=response_der,
            tsa_cert_chain=cert_chain,
            ocsp_responses=tuple(self._ocsp_responses_der),
            issued_at_claimed=gen_time,
        )


# ----- Pre-configured providers for well-known TSAs --------------------------


class FreeTSAProvider(Rfc3161HttpProvider):
    """FreeTSA.org public TSA (no SLA, suitable for OSS / dev / self-host).

    ADR-0003 § 2: default for OSS / dev / self-host deployments. Has no
    SLA; in production, plurality is recommended via
    :class:`MultiTSAProvider`.
    """

    DEFAULT_URL: Final[str] = "https://freetsa.org/tsr"
    DEFAULT_PROVIDER_ID: Final[str] = "freetsa.org"

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        trust_roots_der: list[bytes] | None = None,
        ocsp_responses_der: list[bytes] | None = None,
        url: str | None = None,
        provider_id: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(
            provider_id or self.DEFAULT_PROVIDER_ID,
            url=url or self.DEFAULT_URL,
            transport=transport or UrllibHttpTransport(),
            trust_roots_der=trust_roots_der,
            ocsp_responses_der=ocsp_responses_der,
            timeout_seconds=timeout_seconds,
        )


class DigiCertProvider(Rfc3161HttpProvider):
    """DigiCert paid TSA (enterprise SLA).

    ADR-0003 § 2: recommended for commercial deployments. Plurality
    (≥ 2 independent TSAs) is the recommended posture; pair with
    :class:`FreeTSAProvider` or another commercial TSA via
    :class:`MultiTSAProvider`.
    """

    DEFAULT_URL: Final[str] = "http://timestamp.digicert.com"
    DEFAULT_PROVIDER_ID: Final[str] = "digicert.tsa-2026"

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        trust_roots_der: list[bytes] | None = None,
        ocsp_responses_der: list[bytes] | None = None,
        url: str | None = None,
        provider_id: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(
            provider_id or self.DEFAULT_PROVIDER_ID,
            url=url or self.DEFAULT_URL,
            transport=transport or UrllibHttpTransport(),
            trust_roots_der=trust_roots_der,
            ocsp_responses_der=ocsp_responses_der,
            timeout_seconds=timeout_seconds,
        )


__all__ = [
    "DigiCertProvider",
    "FreeTSAProvider",
    "HttpTransport",
    "RFC3161_CONTENT_TYPE_REQUEST",
    "RFC3161_CONTENT_TYPE_RESPONSE",
    "RecordedHttpTransport",
    "Rfc3161HttpProvider",
    "UrllibHttpTransport",
    "make_replay_transport",
]
