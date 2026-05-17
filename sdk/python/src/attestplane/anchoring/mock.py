# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Deterministic in-process TSA provider for tests.

:class:`MockTSAProvider` does NOT contact any external service. It
produces an :class:`AnchorRecord` whose ``tsa_token``,
``tsa_cert_chain``, and ``ocsp_responses`` fields are deterministic
synthetic bytes derived from the request's digest. This is sufficient
to exercise the anchorer worker, the verifier flow, and the policy
logic without depending on a live TSA.

The mock provider is **not** RFC-3161 compliant — its synthetic
``tsa_token`` will not parse as a real TimeStampToken. Real conformance
testing against an actual TSA ships in a follow-up PR alongside
``anchor_vectors.json``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from attestplane.anchoring.base import (
    ANCHOR_SCHEMA_VERSION,
    AnchorRecord,
    TimestampRequest,
    TSAProvider,
    TSAUnavailableError,
)


class MockTSAProvider(TSAProvider):
    """Deterministic mock TSA. Does not contact any external service.

    :param provider_id: identifier embedded in the resulting
        :class:`AnchorRecord`; defaults to ``"mock.tsa.local"``.
    :param fixed_time: if set, every issued anchor reports this time
        as its ``issued_at_claimed``. Default is to use the
        ``now`` parameter passed to :meth:`request_timestamp` or the
        wall clock as fallback.
    :param fail_with: if set, every :meth:`request_timestamp` call
        raises this exception. Useful for simulating
        :class:`TSAUnavailableError` in tests.
    """

    schema_version = ANCHOR_SCHEMA_VERSION

    def __init__(
        self,
        *,
        provider_id: str = "mock.tsa.local",
        fixed_time: datetime | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        if not provider_id:
            raise ValueError("MockTSAProvider provider_id must be non-empty")
        self.provider_id = provider_id
        self._fixed_time = fixed_time
        self._fail_with = fail_with

    def request_timestamp(
        self,
        request: TimestampRequest,
        *,
        anchored_seq: int = 0,
        now: datetime | None = None,
    ) -> AnchorRecord:
        """Return a deterministic :class:`AnchorRecord` for ``request``.

        ``anchored_seq`` records which chain seq this anchor is for; it
        is passed through to the resulting :class:`AnchorRecord`. (Real
        TSA providers do not see ``anchored_seq`` — only the digest.
        The seq is carried out-of-band by the anchorer worker. The
        mock accepts it directly to keep tests concise.)
        """
        if self._fail_with is not None:
            raise self._fail_with

        when = self._fixed_time or now or datetime.now(UTC)
        if when.tzinfo is None:
            raise TSAUnavailableError("MockTSAProvider requires UTC-aware datetime")

        # Synthesize deterministic but distinguishable bytes for each field.
        token = hashlib.sha256(b"mock-token:" + request.digest).digest()
        cert = hashlib.sha256(b"mock-cert:" + request.digest).digest()
        ocsp = hashlib.sha256(b"mock-ocsp:" + request.digest).digest()

        return AnchorRecord(
            anchor_schema_version=ANCHOR_SCHEMA_VERSION,
            anchored_seq=anchored_seq,
            anchored_event_hash=request.digest,
            tsa_provider_id=self.provider_id,
            tsa_token=token,
            tsa_cert_chain=(cert,),
            ocsp_responses=(ocsp,),
            issued_at_claimed=when,
        )


__all__ = ["MockTSAProvider"]
