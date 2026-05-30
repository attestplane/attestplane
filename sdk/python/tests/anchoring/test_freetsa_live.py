# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Claim-safe FreeTSA live-path coverage.

The live path is exercised without hitting the network by monkeypatching the
stdlib transport constructor. This keeps the test deterministic while still
proving the provider can route through the live code path when explicitly
enabled.
"""

from __future__ import annotations

import hashlib
import json
from base64 import b64decode
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring import AnchorVerificationError, TimestampRequest
from attestplane.anchoring.http import FreeTSAProvider, RecordedHttpTransport
from attestplane.anchoring.rfc3161 import parse_timestamp_response
from attestplane.anchoring.testing import TestTSAAuthority

NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parent.parent / "conformance" / "anchor_vectors.json"


def _load_vector() -> tuple[dict[str, object], bytes]:
    vectors = json.loads(ROOT.read_text(encoding="utf-8"))
    return dict(vectors["entries"][0]), b64decode(str(vectors["test_tsa_root_cert_b64"]))


def test_freetsa_live_mode_uses_stdlib_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    authority = TestTSAAuthority(now=NOW)
    digest = hashlib.sha256(b"chain-head").digest()
    response_der = authority.sign_timestamp_response(digest, gen_time=NOW)
    fake_transport = RecordedHttpTransport(response_der)

    monkeypatch.setattr("attestplane.anchoring.http.UrllibHttpTransport", lambda: fake_transport)

    provider = FreeTSAProvider(
        live=True,
        trust_roots_der=[authority.materials().root_cert_der],
        ocsp_responses_der=[b"ocsp"],
    )
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=NOW)

    assert anchor.tsa_provider_id == "freetsa.org"
    assert anchor.tsa_token == response_der
    parsed = parse_timestamp_response(anchor.tsa_token)
    assert parsed.message_imprint == digest


def test_freetsa_live_mode_accepts_pinned_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    vector, root_der = _load_vector()
    digest = bytes.fromhex(str(vector["anchored_event_hash_hex"]))
    response_der = b64decode(str(vector["tsa_token_b64"]))
    ocsp_der = b64decode(cast(list[str], vector["ocsp_responses_b64"])[0])
    fake_transport = RecordedHttpTransport(response_der)

    monkeypatch.setattr("attestplane.anchoring.http.UrllibHttpTransport", lambda: fake_transport)

    provider = FreeTSAProvider(
        live=True,
        trust_roots_der=[root_der],
        ocsp_responses_der=[ocsp_der],
    )
    anchor = provider.request_timestamp(TimestampRequest(digest=digest), now=NOW)

    assert anchor.tsa_provider_id == "freetsa.org"
    assert anchor.tsa_token == response_der
    assert anchor.tsa_cert_chain[-1] == root_der
    parsed = parse_timestamp_response(anchor.tsa_token)
    assert parsed.message_imprint == digest


def test_freetsa_live_mode_rejects_untrusted_pinned_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    vector, _root_der = _load_vector()
    digest = bytes.fromhex(str(vector["anchored_event_hash_hex"]))
    response_der = b64decode(str(vector["tsa_token_b64"]))
    ocsp_der = b64decode(cast(list[str], vector["ocsp_responses_b64"])[0])
    wrong_root = TestTSAAuthority(now=NOW, common_name="Different TSA").materials().root_cert_der
    fake_transport = RecordedHttpTransport(response_der)

    monkeypatch.setattr("attestplane.anchoring.http.UrllibHttpTransport", lambda: fake_transport)

    provider = FreeTSAProvider(
        live=True,
        trust_roots_der=[wrong_root],
        ocsp_responses_der=[ocsp_der],
    )
    with pytest.raises(AnchorVerificationError, match=r"trust root|signature does not verify|issuer DN"):
        provider.request_timestamp(TimestampRequest(digest=digest), now=NOW)


def test_freetsa_live_mode_rejects_transport_override() -> None:
    with pytest.raises(ValueError, match="live mode does not accept"):
        FreeTSAProvider(live=True, transport=RecordedHttpTransport(b"ignored"))


def test_freetsa_recorded_mode_requires_transport() -> None:
    with pytest.raises(ValueError, match="recorded-fixture mode requires a transport"):
        FreeTSAProvider()
