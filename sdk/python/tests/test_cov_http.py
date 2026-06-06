# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""Coverage-completion tests for attestplane.anchoring.http (≥98%)."""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring.base import (
    AnchorVerificationError,
    TimestampRequest,
    TSAUnavailableError,
)
from attestplane.anchoring.http import (
    FreeTSAProvider,
    HttpTransport,
    RecordedHttpTransport,
    Rfc3161HttpProvider,
    UrllibHttpTransport,
)
from attestplane.anchoring.testing import TestTSAAuthority

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _make_response(digest: bytes, *, nonce: bytes | None = None) -> tuple[bytes, bytes]:
    authority = TestTSAAuthority(now=_NOW)
    der = authority.sign_timestamp_response(digest, gen_time=_NOW, nonce=nonce)
    materials = authority.materials()
    return der, materials.root_cert_der


# ---------------------------------------------------------------------------
# HttpTransport abstract base — NotImplementedError (line 71)
# ---------------------------------------------------------------------------

def test_http_transport_abstract_submit_raises() -> None:
    """Line 71: calling submit on a concrete subclass that hits super raises NotImplementedError."""

    class BareTransport(HttpTransport):
        def submit(self, url: str, request_der: bytes, *, timeout_seconds: float = 30.0) -> bytes:
            return super().submit(url, request_der, timeout_seconds=timeout_seconds)  # type: ignore[safe-super]

    t = BareTransport()
    with pytest.raises(NotImplementedError):
        t.submit("https://example.invalid", b"bytes")


# ---------------------------------------------------------------------------
# UrllibHttpTransport — successful submit (lines 98-107: happy path)
# ---------------------------------------------------------------------------

def test_urllib_transport_success() -> None:
    """Lines 98-107: successful urlopen returns body bytes."""

    class _FakeResponse:
        @property
        def headers(self) -> dict[str, str]:
            return {"Content-Type": "application/timestamp-reply; charset=binary"}

        def read(self) -> bytes:
            return b"\x30\x03\x01\x01\x00"  # minimal non-empty DER-like bytes

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    transport = UrllibHttpTransport()
    with patch("urllib.request.urlopen", return_value=_FakeResponse()):
        result = transport.submit("https://example.invalid/tsr", b"request")
    assert result == b"\x30\x03\x01\x01\x00"


# ---------------------------------------------------------------------------
# UrllibHttpTransport — wrong Content-Type response (lines 98-100)
# ---------------------------------------------------------------------------

def test_urllib_transport_wrong_content_type() -> None:
    """Lines 98-100: server returns wrong Content-Type raises TSAUnavailableError."""

    class _FakeResponse:
        def __init__(self) -> None:
            self._headers: dict[str, str] = {"Content-Type": "text/html"}
            self.status = 200

        @property
        def headers(self) -> dict[str, str]:
            return self._headers

        def read(self) -> bytes:
            return b"<html></html>"

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    transport = UrllibHttpTransport()
    with patch("urllib.request.urlopen", return_value=_FakeResponse()), pytest.raises(
        TSAUnavailableError, match="unexpected Content-Type"
    ):
        transport.submit("https://example.invalid/tsr", b"request-bytes")


# ---------------------------------------------------------------------------
# UrllibHttpTransport — URLError (lines 102-103)
# ---------------------------------------------------------------------------

def test_urllib_transport_url_error() -> None:
    """Lines 102-103: URLError is caught and re-raised as TSAUnavailableError."""
    transport = UrllibHttpTransport()
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ), pytest.raises(TSAUnavailableError, match="unreachable"):
        transport.submit("https://example.invalid/tsr", b"bytes")


# ---------------------------------------------------------------------------
# UrllibHttpTransport — TimeoutError (lines 102-103)
# ---------------------------------------------------------------------------

def test_urllib_transport_timeout_error() -> None:
    """Lines 102-103: TimeoutError is caught and re-raised as TSAUnavailableError."""
    transport = UrllibHttpTransport()
    with patch(
        "urllib.request.urlopen",
        side_effect=TimeoutError("timed out"),
    ), pytest.raises(TSAUnavailableError, match="unreachable"):
        transport.submit("https://example.invalid/tsr", b"bytes")


# ---------------------------------------------------------------------------
# UrllibHttpTransport — OSError (lines 102-103)
# ---------------------------------------------------------------------------

def test_urllib_transport_os_error() -> None:
    """Lines 102-103: OSError is caught and re-raised as TSAUnavailableError."""
    transport = UrllibHttpTransport()
    with patch(
        "urllib.request.urlopen",
        side_effect=OSError("broken pipe"),
    ), pytest.raises(TSAUnavailableError, match="unreachable"):
        transport.submit("https://example.invalid/tsr", b"bytes")


# ---------------------------------------------------------------------------
# UrllibHttpTransport — empty body (lines 104-105)
# ---------------------------------------------------------------------------

def test_urllib_transport_empty_body() -> None:
    """Lines 104-105: server returns empty body raises TSAUnavailableError."""

    class _FakeResponse:
        @property
        def headers(self) -> dict[str, str]:
            return {"Content-Type": "application/timestamp-reply"}

        def read(self) -> bytes:
            return b""

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    transport = UrllibHttpTransport()
    with patch("urllib.request.urlopen", return_value=_FakeResponse()), pytest.raises(
        TSAUnavailableError, match="empty body"
    ):
        transport.submit("https://example.invalid/tsr", b"request")


# ---------------------------------------------------------------------------
# Rfc3161HttpProvider — parse exception other than AnchorVerificationError (lines 214-217)
# ---------------------------------------------------------------------------

def test_rfc3161_provider_parse_generic_exception() -> None:
    """Lines 214-217: if parse_timestamp_response raises a generic Exception
    (not AnchorVerificationError), it is wrapped in AnchorVerificationError."""
    digest = hashlib.sha256(b"x").digest()
    der, root = _make_response(digest)
    provider = Rfc3161HttpProvider(
        "test-p",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
    )
    with patch(
        "attestplane.anchoring.http.parse_timestamp_response",
        side_effect=RuntimeError("something broke"),
    ), pytest.raises(AnchorVerificationError, match="failed to parse"):
        provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)


# ---------------------------------------------------------------------------
# Rfc3161HttpProvider — AnchorVerificationError from parse is re-raised (lines 213-215)
# ---------------------------------------------------------------------------

def test_rfc3161_provider_parse_anchor_verification_error_propagates() -> None:
    """Lines 213-215: AnchorVerificationError from parse_timestamp_response propagates as-is."""
    digest = hashlib.sha256(b"x").digest()

    provider = Rfc3161HttpProvider(
        "test-p",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(b"not-valid-der"),
    )

    sentinel_error = AnchorVerificationError("sentinel from parse")

    with patch(
        "attestplane.anchoring.http.parse_timestamp_response", side_effect=sentinel_error
    ), pytest.raises(AnchorVerificationError, match="sentinel from parse"):
        provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)


# ---------------------------------------------------------------------------
# FreeTSAProvider — live mode rejects transport override (line 286)
# ---------------------------------------------------------------------------

def test_freetsa_live_mode_rejects_transport_override() -> None:
    """Line 286: live=True with transport override raises ValueError."""
    with pytest.raises(ValueError, match="live mode does not accept a transport"):
        FreeTSAProvider(
            live=True,
            transport=RecordedHttpTransport(b"any"),
        )


# ---------------------------------------------------------------------------
# FreeTSAProvider — recorded-fixture mode requires transport (line 288)
# ---------------------------------------------------------------------------

def test_freetsa_recorded_mode_requires_transport() -> None:
    """Line 288: live=False (default) with no transport raises ValueError."""
    with pytest.raises(ValueError, match="recorded-fixture mode requires a transport"):
        FreeTSAProvider(live=False, transport=None)


# ---------------------------------------------------------------------------
# FreeTSAProvider — live=True creates UrllibHttpTransport (line 291)
# ---------------------------------------------------------------------------

def test_freetsa_live_mode_creates_urllib_transport() -> None:
    """Line 291: live=True creates an internal UrllibHttpTransport."""
    provider = FreeTSAProvider(live=True)
    assert isinstance(provider._transport, UrllibHttpTransport)


# ---------------------------------------------------------------------------
# make_replay_transport — wraps RecordedHttpTransport (line 128)
# ---------------------------------------------------------------------------

def test_make_replay_transport_returns_recorded() -> None:
    """Line 128: make_replay_transport returns a RecordedHttpTransport."""
    from attestplane.anchoring.http import RecordedHttpTransport, make_replay_transport

    t = make_replay_transport(b"some-bytes")
    assert isinstance(t, RecordedHttpTransport)
    assert t.submit("https://x.invalid", b"req") == b"some-bytes"


# ---------------------------------------------------------------------------
# _build_request_der — nonce branch (line 149)
# ---------------------------------------------------------------------------

def test_build_request_der_with_nonce() -> None:
    """Line 149: _build_request_der includes nonce when provided."""
    from attestplane.anchoring.http import _build_request_der

    digest = hashlib.sha256(b"nonce-test").digest()
    der_with_nonce = _build_request_der(digest, nonce=b"\xde\xad\xbe\xef")
    der_without_nonce = _build_request_der(digest)
    # DER with nonce is longer than without
    assert len(der_with_nonce) > len(der_without_nonce)


# ---------------------------------------------------------------------------
# Rfc3161HttpProvider — full round trip (lines 216-247: success path)
# ---------------------------------------------------------------------------

def test_rfc3161_full_round_trip_with_trust_roots() -> None:
    """Lines 216-247: full round trip with trust_roots_der triggers verify_timestamp_token."""
    digest = hashlib.sha256(b"round-trip").digest()
    der, root = _make_response(digest)
    provider = Rfc3161HttpProvider(
        "rt-provider",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
    )
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
    assert anchor.anchored_event_hash == digest
    assert anchor.tsa_provider_id == "rt-provider"
    # cert chain should include leaf + trust root
    assert len(anchor.tsa_cert_chain) >= 2


def test_rfc3161_full_round_trip_without_trust_roots() -> None:
    """Lines 236-247: round trip without trust roots returns anchor with just leaf cert."""
    digest = hashlib.sha256(b"no-roots").digest()
    der, _root = _make_response(digest)
    provider = Rfc3161HttpProvider(
        "no-roots-provider",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
        trust_roots_der=None,
    )
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
    assert anchor.anchored_event_hash == digest
    # cert chain has only leaf (no trust roots)
    assert len(anchor.tsa_cert_chain) == 1


def test_rfc3161_nonce_round_trip() -> None:
    """Lines 221-224: nonce comparison path."""
    digest = hashlib.sha256(b"nonce").digest()
    nonce = b"\x01\x02\x03\x04"
    der, root = _make_response(digest, nonce=nonce)
    provider = Rfc3161HttpProvider(
        "nonce-provider",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
    )
    anchor = provider.request_timestamp(TimestampRequest(digest=digest, nonce=nonce), now=_NOW)
    assert anchor.anchored_event_hash == digest


def test_rfc3161_nonce_mismatch() -> None:
    """Lines 221-224: nonce mismatch raises AnchorVerificationError."""
    digest = hashlib.sha256(b"x").digest()
    der, root = _make_response(digest, nonce=b"\xaa\xaa\xaa\xaa")
    provider = Rfc3161HttpProvider(
        "nonce-mm",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
    )
    with pytest.raises(AnchorVerificationError, match="nonce"):
        provider.request_timestamp(TimestampRequest(digest=digest, nonce=b"\xbb\xbb\xbb\xbb"), now=_NOW)


def test_rfc3161_digest_mismatch() -> None:
    """Line 219-220: messageImprint mismatch raises AnchorVerificationError."""
    real_digest = hashlib.sha256(b"real").digest()
    der, root = _make_response(real_digest)
    provider = Rfc3161HttpProvider(
        "digest-mm",
        url="https://example.invalid/tsr",
        transport=RecordedHttpTransport(der),
    )
    other = hashlib.sha256(b"other").digest()
    with pytest.raises(AnchorVerificationError, match="wrong messageImprint"):
        provider.request_timestamp(TimestampRequest(digest=other), now=_NOW)


def test_rfc3161_empty_provider_id_raises() -> None:
    """Lines 188-189: empty provider_id raises ValueError."""
    with pytest.raises(ValueError, match="provider_id"):
        Rfc3161HttpProvider(
            "",
            url="https://x.invalid",
            transport=RecordedHttpTransport(b""),
        )


def test_rfc3161_empty_url_raises() -> None:
    """Lines 190-191: empty url raises ValueError."""
    with pytest.raises(ValueError, match="url"):
        Rfc3161HttpProvider(
            "p",
            url="",
            transport=RecordedHttpTransport(b""),
        )


# ---------------------------------------------------------------------------
# FreeTSAProvider — default construction with recorded transport (lines 293-302)
# ---------------------------------------------------------------------------

def test_freetsa_recorded_mode_basic() -> None:
    """Lines 293-302: FreeTSAProvider with recorded transport instantiates correctly."""
    digest = hashlib.sha256(b"freetsa").digest()
    der, root = _make_response(digest)
    provider = FreeTSAProvider(
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
    )
    assert provider.provider_id == "freetsa.org"
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
    assert anchor.tsa_provider_id == "freetsa.org"


# ---------------------------------------------------------------------------
# attestplane.anchoring.__init__ — _HTTP_AVAILABLE=False branch (line 135->148)
# and _SIGSTORE_AVAILABLE=False branch (line 148->exit)
# ---------------------------------------------------------------------------

def test_init_http_unavailable_skips_all_extend() -> None:
    """Lines 135->148, 148->exit: when http/sigstore imports fail at module load,
    __all__ does not include the conditional symbols."""
    import importlib

    import attestplane.anchoring as anchoring_mod

    with (
        patch.dict("sys.modules", {
            "attestplane.anchoring.http": None,
            "attestplane.anchoring.sigstore": None,
        })
    ):
        importlib.reload(anchoring_mod)
        try:
            assert not anchoring_mod._HTTP_AVAILABLE
            assert not anchoring_mod._SIGSTORE_AVAILABLE
            assert "DigiCertProvider" not in anchoring_mod.__all__
            assert "SigstoreRekorAnchor" not in anchoring_mod.__all__
        finally:
            # Restore to original state so other tests are not affected
            importlib.reload(anchoring_mod)


# ---------------------------------------------------------------------------
# DigiCertProvider — construction (line 327)
# ---------------------------------------------------------------------------

def test_digicert_provider_basic() -> None:
    """Line 327: DigiCertProvider instantiates with defaults."""
    from attestplane.anchoring.http import DigiCertProvider

    digest = hashlib.sha256(b"digicert").digest()
    der, root = _make_response(digest)
    provider = DigiCertProvider(
        transport=RecordedHttpTransport(der),
        trust_roots_der=[root],
    )
    assert provider.provider_id == "digicert.tsa-2026"
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=_NOW)
    assert anchor.tsa_provider_id == "digicert.tsa-2026"
