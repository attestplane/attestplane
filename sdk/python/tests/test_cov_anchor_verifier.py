# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-completion tests for attestplane.anchoring.verifier, .composite, and .base.

Targets every uncovered line/branch:

verifier.py: 160-167, 178-191, 221-231, 263-298, 301-412, 438, 511-573
composite.py: 63
base.py: 235
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from attestplane.anchoring.base import (
    ANCHOR_SCHEMA_VERSION,
    AnchorRecord,
    AnchorVerificationError,
    TimestampRequest,
    TSAProvider,
    TSAUnavailableError,
)
from attestplane.anchoring.composite import MultiTSAProvider
from attestplane.anchoring.verifier import (
    LIVE_ANCHOR_QUARANTINE_EXIT_CODE,
    verify_chain_with_anchors,
    verify_live_anchor_with_provider,
)
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import ChainedEvent, ChainHead, EventDraft
from attestplane.verify_reason_codes import (
    VERIFY_REASON_ANCHOR_INVALID,
    VERIFY_REASON_ANCHOR_QUARANTINED,
)

# Skip the whole module if anchor extras are absent (TestTSAAuthority needs them)
pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring.testing import TestTSAAuthority  # noqa: E402

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_chain(n: int) -> list[ChainedEvent]:
    chain: list[ChainedEvent] = []
    head: ChainHead = genesis_head()
    for i in range(n):
        draft = EventDraft(
            event_type="eval_event",
            actor=f"agent://cov/{i}",
            payload={"i": i},
        )
        ev = chain_extend(head, draft, now=_NOW, event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


def _good_anchor(
    chain: list[ChainedEvent],
    seq: int,
    *,
    provider_id: str = "mock.tsa.local",
    cert_chain: tuple[bytes, ...] = (b"\x01" * 32,),
    ocsp: tuple[bytes, ...] = (b"\x02" * 32,),
) -> AnchorRecord:
    return AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=seq,
        anchored_event_hash=chain[seq].event_hash,
        tsa_provider_id=provider_id,
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=cert_chain,
        ocsp_responses=ocsp,
        issued_at_claimed=_NOW,
    )


def _real_anchor(
    chain: list[ChainedEvent],
    seq: int,
    *,
    authority: TestTSAAuthority,
    ocsp_mode: str = "real",
    revoked: bool = False,
) -> tuple[AnchorRecord, bytes]:
    """Return (anchor, root_cert_der) using real RFC-3161 token + real OCSP."""
    materials = authority.materials()
    token_der = authority.sign_timestamp_response(chain[seq].event_hash, gen_time=_NOW, serial_number=seq + 1)
    if ocsp_mode == "legacy":
        ocsp_bytes = authority.issue_ocsp_response(gen_time=_NOW)
    else:
        ocsp_bytes = authority.issue_real_ocsp_response(gen_time=_NOW, revoked=revoked)
    anchor = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=seq,
        anchored_event_hash=chain[seq].event_hash,
        tsa_provider_id=f"test.tsa:{authority.common_name}",
        tsa_token=token_der,
        tsa_cert_chain=(materials.leaf_cert_der, materials.root_cert_der),
        ocsp_responses=(ocsp_bytes,),
        issued_at_claimed=_NOW,
    )
    return anchor, materials.root_cert_der


# ---------------------------------------------------------------------------
# base.py lines 100, 104, 106, 108 — AnchorRecord.__post_init__ validations
# ---------------------------------------------------------------------------


def test_anchor_record_rejects_wrong_schema_version() -> None:
    """base.py 100 — wrong anchor_schema_version raises AnchorError."""
    from attestplane.anchoring.base import AnchorError

    with pytest.raises(AnchorError, match="anchor_schema_version"):
        AnchorRecord(
            anchor_schema_version=99,
            anchored_seq=0,
            anchored_event_hash=b"\x00" * 32,
            tsa_provider_id="tsa",
            tsa_token=b"\x00",
            tsa_cert_chain=(b"\x00",),
            ocsp_responses=(b"\x00",),
            issued_at_claimed=_NOW,
        )


def test_anchor_record_rejects_short_hash() -> None:
    """base.py 104 — anchored_event_hash not 32 bytes raises AnchorError."""
    from attestplane.anchoring.base import AnchorError

    with pytest.raises(AnchorError, match="32 bytes"):
        AnchorRecord(
            anchor_schema_version=ANCHOR_SCHEMA_VERSION,
            anchored_seq=0,
            anchored_event_hash=b"\x00" * 16,
            tsa_provider_id="tsa",
            tsa_token=b"\x00",
            tsa_cert_chain=(b"\x00",),
            ocsp_responses=(b"\x00",),
            issued_at_claimed=_NOW,
        )


def test_anchor_record_rejects_negative_seq() -> None:
    """base.py 106 — negative anchored_seq raises AnchorError."""
    from attestplane.anchoring.base import AnchorError

    with pytest.raises(AnchorError, match="anchored_seq"):
        AnchorRecord(
            anchor_schema_version=ANCHOR_SCHEMA_VERSION,
            anchored_seq=-1,
            anchored_event_hash=b"\x00" * 32,
            tsa_provider_id="tsa",
            tsa_token=b"\x00",
            tsa_cert_chain=(b"\x00",),
            ocsp_responses=(b"\x00",),
            issued_at_claimed=_NOW,
        )


def test_anchor_record_rejects_empty_provider_id() -> None:
    """base.py 108 — empty tsa_provider_id raises AnchorError."""
    from attestplane.anchoring.base import AnchorError

    with pytest.raises(AnchorError, match="tsa_provider_id"):
        AnchorRecord(
            anchor_schema_version=ANCHOR_SCHEMA_VERSION,
            anchored_seq=0,
            anchored_event_hash=b"\x00" * 32,
            tsa_provider_id="",
            tsa_token=b"\x00",
            tsa_cert_chain=(b"\x00",),
            ocsp_responses=(b"\x00",),
            issued_at_claimed=_NOW,
        )


# ---------------------------------------------------------------------------
# base.py lines 129-132 — AnchorPolicy.__post_init__ validations
# ---------------------------------------------------------------------------


def test_anchor_policy_rejects_zero_batch_size() -> None:
    """base.py 129-130 — batch_size < 1 raises AnchorError."""
    from attestplane.anchoring.base import AnchorError, AnchorPolicy

    with pytest.raises(AnchorError, match="batch_size"):
        AnchorPolicy(batch_size=0)


def test_anchor_policy_rejects_zero_idle_seconds() -> None:
    """base.py 131-132 — max_idle_seconds < 1 raises AnchorError."""
    from attestplane.anchoring.base import AnchorError, AnchorPolicy

    with pytest.raises(AnchorError, match="max_idle_seconds"):
        AnchorPolicy(max_idle_seconds=0)


# ---------------------------------------------------------------------------
# base.py line 153 — TimestampRequest.__post_init__ validation
# ---------------------------------------------------------------------------


def test_timestamp_request_rejects_wrong_digest_length() -> None:
    """base.py 153 — digest not 32 bytes raises AnchorError."""
    from attestplane.anchoring.base import AnchorError

    with pytest.raises(AnchorError, match="32 bytes"):
        TimestampRequest(digest=b"\x00" * 16)


# ---------------------------------------------------------------------------
# base.py line 210 — TSAProvider.__init_subclass__ rejects forbidden verbs
# ---------------------------------------------------------------------------


def test_tsa_provider_rejects_forbidden_verbs() -> None:
    """base.py 210 — forbidden mutating methods trigger AnchorBoundaryError."""
    from attestplane.anchoring.base import AnchorBoundaryError

    def make_bad_provider(method_name: str) -> None:
        namespace = {
            "provider_id": "bad",
            "schema_version": ANCHOR_SCHEMA_VERSION,
            "request_timestamp": lambda self, req, **kw: None,
            method_name: lambda self, *a, **kw: None,
        }
        type("BadProvider", (TSAProvider,), namespace)

    for verb in ("mutate", "rewrite", "replace", "revoke", "retract", "delete", "remove"):
        with pytest.raises(AnchorBoundaryError, match="forbidden mutating method"):
            make_bad_provider(verb)


# ---------------------------------------------------------------------------
# composite.py lines 57, 60, 62, 67-68, 73, 91-103 — MultiTSAProvider
# ---------------------------------------------------------------------------


def test_multi_provider_requires_at_least_one_provider() -> None:
    """composite.py line 57 — empty providers list raises ValueError."""
    with pytest.raises(ValueError, match="at least one"):
        MultiTSAProvider([])


def test_multi_provider_rejects_duplicate_provider_ids() -> None:
    """composite.py line 60 — duplicate provider_id values raise ValueError."""

    class _P(TSAProvider):
        provider_id = "dup"
        schema_version = ANCHOR_SCHEMA_VERSION

        def request_timestamp(self, request: TimestampRequest, **kwargs: Any) -> AnchorRecord:
            raise NotImplementedError

    with pytest.raises(ValueError, match="distinct provider_id"):
        MultiTSAProvider([_P(), _P()])


def test_multi_provider_provider_ids_property() -> None:
    """composite.py line 73 — provider_ids returns tuple of ids in order."""
    from attestplane.anchoring.mock import MockTSAProvider

    p1 = MockTSAProvider(provider_id="alpha")
    p2 = MockTSAProvider(provider_id="beta")
    multi = MultiTSAProvider([p1, p2])
    assert multi.provider_ids == ("alpha", "beta")


def test_multi_provider_fans_out_request() -> None:
    """composite.py lines 91-103 — request_timestamps fans out to all providers."""
    from attestplane.anchoring.mock import MockTSAProvider

    p1 = MockTSAProvider(provider_id="alpha", fixed_time=_NOW)
    p2 = MockTSAProvider(provider_id="beta", fixed_time=_NOW)
    multi = MultiTSAProvider([p1, p2])
    anchors = multi.request_timestamps(
        TimestampRequest(digest=b"\x00" * 32),
        anchored_seq=0,
    )
    assert len(anchors) == 2
    assert {a.tsa_provider_id for a in anchors} == {"alpha", "beta"}


def test_multi_provider_fails_fast_by_default() -> None:
    """composite.py line 97-98 — TSAUnavailableError re-raised when tolerate_partial=False."""
    from attestplane.anchoring.mock import MockTSAProvider

    good = MockTSAProvider(provider_id="alpha", fixed_time=_NOW)
    bad = MockTSAProvider(provider_id="beta", fail_with=TSAUnavailableError("down"))
    multi = MultiTSAProvider([good, bad])
    with pytest.raises(TSAUnavailableError, match="down"):
        multi.request_timestamps(TimestampRequest(digest=b"\x00" * 32))


def test_multi_provider_tolerate_partial_returns_partial_results() -> None:
    """composite.py lines 99-100 — tolerate_partial=True collects partial results."""
    from attestplane.anchoring.mock import MockTSAProvider

    good = MockTSAProvider(provider_id="alpha", fixed_time=_NOW)
    bad = MockTSAProvider(provider_id="beta", fail_with=TSAUnavailableError("down"))
    multi = MultiTSAProvider([good, bad], tolerate_partial=True)
    anchors = multi.request_timestamps(TimestampRequest(digest=b"\x00" * 32), anchored_seq=0)
    assert len(anchors) == 1
    assert anchors[0].tsa_provider_id == "alpha"


def test_multi_provider_tolerate_partial_all_fail_raises() -> None:
    """composite.py lines 101-102 — tolerate_partial=True but all fail -> re-raise first error."""
    from attestplane.anchoring.mock import MockTSAProvider

    p1 = MockTSAProvider(provider_id="alpha", fail_with=TSAUnavailableError("one"))
    p2 = MockTSAProvider(provider_id="beta", fail_with=TSAUnavailableError("two"))
    multi = MultiTSAProvider([p1, p2], tolerate_partial=True)
    with pytest.raises(TSAUnavailableError):
        multi.request_timestamps(TimestampRequest(digest=b"\x00" * 32))


# ---------------------------------------------------------------------------
# base.py line 235 — TSAProvider.request_timestamp() raises NotImplementedError
# ---------------------------------------------------------------------------


class _NakedProvider(TSAProvider):
    """Concrete subclass that calls super() to trigger base raise."""

    provider_id = "naked"
    schema_version = ANCHOR_SCHEMA_VERSION

    def request_timestamp(self, request: TimestampRequest, **kwargs: Any) -> AnchorRecord:
        # Deliberately calls super() to exercise the NotImplementedError in base.
        return super().request_timestamp(request)  # type: ignore[safe-super]


def test_tsa_provider_base_raises_not_implemented() -> None:
    """base.py line 235 — abstract base raises NotImplementedError."""
    provider = _NakedProvider()
    with pytest.raises(NotImplementedError):
        provider.request_timestamp(TimestampRequest(digest=b"\x00" * 32))


# ---------------------------------------------------------------------------
# composite.py line 63 — MultiTSAProvider rejects wrong schema_version
# ---------------------------------------------------------------------------


def test_multi_tsa_rejects_wrong_schema_version() -> None:
    """composite.py line 63 — schema_version mismatch rejected at construction."""

    class _WrongVersionProvider(TSAProvider):
        provider_id = "wrongver"
        schema_version = 99  # intentionally wrong

        def request_timestamp(self, request: TimestampRequest, **kwargs: Any) -> AnchorRecord:
            raise NotImplementedError

    with pytest.raises(ValueError, match="schema_version"):
        MultiTSAProvider([_WrongVersionProvider()])


# ---------------------------------------------------------------------------
# verifier.py 178-191 — wrong anchor_schema_version branch
# Uses object.__setattr__ to bypass AnchorRecord.__post_init__.
# ---------------------------------------------------------------------------


def _make_bad_schema_anchor(chain: list[ChainedEvent], seq: int, schema_version: int = 99) -> AnchorRecord:
    obj = object.__new__(AnchorRecord)
    for field, value in [
        ("anchor_schema_version", schema_version),
        ("anchored_seq", seq),
        ("anchored_event_hash", chain[seq].event_hash),
        ("tsa_provider_id", "mock.tsa.local"),
        ("tsa_token", b"\x00" * 32),
        ("tsa_cert_chain", (b"\x01" * 32,)),
        ("ocsp_responses", (b"\x02" * 32,)),
        ("issued_at_claimed", _NOW),
    ]:
        object.__setattr__(obj, field, value)
    return obj


def test_verify_wrong_schema_version_fails() -> None:
    """verifier.py 178-191 — wrong schema_version -> failed with reason."""
    chain = _build_chain(1)
    bad = _make_bad_schema_anchor(chain, 0, schema_version=99)
    result = verify_chain_with_anchors(chain, [bad])
    assert result.verification_status == "failed"
    ar = result.anchor_results[0]
    assert ar.valid is False
    assert ar.cert_status == "MISSING_LTV_ARTIFACTS"
    assert ar.ltv_artifacts_present is False
    assert "this verifier handles version" in (ar.reason or "")
    assert "99" in (ar.reason or "")


def test_verify_wrong_schema_version_schema2_fails() -> None:
    chain = _build_chain(1)
    bad = _make_bad_schema_anchor(chain, 0, schema_version=2)
    result = verify_chain_with_anchors(chain, [bad])
    ar = result.anchor_results[0]
    assert "anchor_schema_version=2" in (ar.reason or "")


# ---------------------------------------------------------------------------
# verifier.py 221-231 — naive datetime (no tzinfo) branch
# ---------------------------------------------------------------------------


def test_verify_naive_issued_at() -> None:
    """verifier.py 221-231 — naive datetime -> failed with reason."""
    chain = _build_chain(1)
    naive_time = datetime(2026, 5, 17, 12, 0, 0)  # no tzinfo
    bad = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain[0].event_hash,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(b"\x01" * 32,),
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=naive_time,
    )
    result = verify_chain_with_anchors(chain, [bad])
    ar = result.anchor_results[0]
    assert ar.valid is False
    assert "naive datetime" in (ar.reason or "")
    assert ar.cert_status == "MISSING_LTV_ARTIFACTS"


# ---------------------------------------------------------------------------
# verifier.py 263-298 — sigstore.rekor dispatch path
# Patching the real sigstore module functions.
# ---------------------------------------------------------------------------


def _rekor_anchor(chain: list[ChainedEvent], seq: int) -> AnchorRecord:
    return AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=seq,
        anchored_event_hash=chain[seq].event_hash,
        tsa_provider_id="sigstore.rekor:test-log",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(b"\x01" * 32,),
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=_NOW,
    )


def test_verify_rekor_dispatch_success() -> None:
    """verifier.py 287-298 — sigstore.rekor success path -> valid=True, cert_status=VALID."""
    chain = _build_chain(1)
    anchor = _rekor_anchor(chain, 0)

    with (
        patch("attestplane.anchoring.sigstore.parse_rekor_log_entry", return_value=MagicMock()),
        patch("attestplane.anchoring.sigstore.verify_rekor_signed_entry_timestamp", return_value=None),
    ):
        result = verify_chain_with_anchors(
            chain,
            [anchor],
            trust_roots_der=[b"\xca" * 32],
            verify_ocsp=False,
        )
    ar = result.anchor_results[0]
    assert ar.valid is True
    assert ar.cert_status == "VALID"
    assert ar.ltv_artifacts_present is True
    assert ar.reason is None
    assert result.verification_status == "verified"
    assert result.ok is True
    assert 0 in result.anchored_seqs


def test_verify_rekor_dispatch_failure() -> None:
    """verifier.py 275-286 — sigstore.rekor raises AnchorVerificationError -> failed anchor."""
    chain = _build_chain(1)
    anchor = _rekor_anchor(chain, 0)

    with (
        patch("attestplane.anchoring.sigstore.parse_rekor_log_entry", return_value=MagicMock()),
        patch(
            "attestplane.anchoring.sigstore.verify_rekor_signed_entry_timestamp",
            side_effect=AnchorVerificationError("bad rekor sig"),
        ),
    ):
        result = verify_chain_with_anchors(
            chain,
            [anchor],
            trust_roots_der=[b"\xca" * 32],
            verify_ocsp=False,
        )
    ar = result.anchor_results[0]
    assert ar.valid is False
    assert ar.cert_status == "MISSING_LTV_ARTIFACTS"
    assert ar.ltv_artifacts_present is True
    assert "bad rekor sig" in (ar.reason or "")
    assert result.verification_status == "failed"


def test_verify_rekor_dispatch_no_cert_chain_rejected_before_dispatch() -> None:
    """The rekor path requires ltv_present=True; empty tsa_cert_chain is blocked by ltv check.

    line 269 ``else b""`` is a defensive guard that is structurally unreachable:
    ltv_present requires bool(tsa_cert_chain) to be True.
    An anchor with empty tsa_cert_chain is rejected by the ltv_present check before sigstore dispatch.
    """
    chain = _build_chain(1)
    anchor_no_chain = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain[0].event_hash,
        tsa_provider_id="sigstore.rekor:test-log",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(),  # empty -> ltv_present=False -> rejected before sigstore dispatch
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=_NOW,
    )

    with (
        patch("attestplane.anchoring.sigstore.parse_rekor_log_entry", return_value=MagicMock()),
        patch("attestplane.anchoring.sigstore.verify_rekor_signed_entry_timestamp", return_value=None),
    ):
        result = verify_chain_with_anchors(
            chain,
            [anchor_no_chain],
            trust_roots_der=[b"\xca" * 32],
            verify_ocsp=False,
        )
    # Rejected by ltv_present check before reaching sigstore dispatch
    ar = result.anchor_results[0]
    assert ar.valid is False
    assert ar.cert_status == "MISSING_LTV_ARTIFACTS"
    assert "long-term validation" in (ar.reason or "")


# ---------------------------------------------------------------------------
# verifier.py 301-325 — rfc3161 verify path: success and AnchorVerificationError
# ---------------------------------------------------------------------------


def test_verify_rfc3161_token_full_success() -> None:
    """verifier.py 300-425 — real RFC-3161 + OCSP end-to-end verified (line 412)."""
    chain = _build_chain(1)
    authority = TestTSAAuthority(now=_NOW)
    anchor, root_der = _real_anchor(chain, 0, authority=authority)

    result = verify_chain_with_anchors(
        chain,
        [anchor],
        trust_roots_der=[root_der],
        verify_ocsp=True,
        verification_time=_NOW,
    )
    assert result.verification_status == "verified"
    assert result.ok is True
    ar = result.anchor_results[0]
    assert ar.valid is True
    assert ar.cert_status == "VALID"
    assert ar.ltv_artifacts_present is True


def test_verify_rfc3161_token_parse_failure() -> None:
    """verifier.py 314-325 — rfc3161.verify raises AnchorVerificationError -> failed."""
    chain = _build_chain(1)
    anchor = _good_anchor(chain, 0)  # synthetic (non-real) token -> parse fails

    result = verify_chain_with_anchors(
        chain,
        [anchor],
        trust_roots_der=[b"\xca" * 32],
        verify_ocsp=False,
    )
    ar = result.anchor_results[0]
    assert ar.valid is False
    assert ar.ltv_artifacts_present is True
    assert ar.cert_status == "MISSING_LTV_ARTIFACTS"
    assert ar.reason is not None


# ---------------------------------------------------------------------------
# verifier.py 335-386 — OCSP path: revoked, unknown, structural failure
# ---------------------------------------------------------------------------


def test_verify_ocsp_revoked_path() -> None:
    """verifier.py 387-398 — OCSP 'revoked' -> cert_status=REVOKED."""
    chain = _build_chain(1)
    authority = TestTSAAuthority(now=_NOW)
    anchor, root_der = _real_anchor(chain, 0, authority=authority, revoked=True)

    result = verify_chain_with_anchors(
        chain,
        [anchor],
        trust_roots_der=[root_der],
        verify_ocsp=True,
        verification_time=_NOW,
    )
    ar = result.anchor_results[0]
    assert ar.valid is False
    assert ar.cert_status == "REVOKED"
    assert "revoked" in (ar.reason or "")


def test_verify_ocsp_structural_failure_via_legacy_bytes() -> None:
    """verifier.py 368-386 — AnchorVerificationError from OCSP parse -> MISSING_LTV."""
    chain = _build_chain(1)
    authority = TestTSAAuthority(now=_NOW)
    materials = authority.materials()
    token_der = authority.sign_timestamp_response(chain[0].event_hash, gen_time=_NOW, serial_number=1)
    bad_ocsp = authority.issue_ocsp_response(gen_time=_NOW)  # legacy synthetic, triggers AnchorVerificationError

    anchor = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain[0].event_hash,
        tsa_provider_id=f"test.tsa:{authority.common_name}",
        tsa_token=token_der,
        tsa_cert_chain=(materials.leaf_cert_der, materials.root_cert_der),
        ocsp_responses=(bad_ocsp,),
        issued_at_claimed=_NOW,
    )

    result = verify_chain_with_anchors(
        chain,
        [anchor],
        trust_roots_der=[materials.root_cert_der],
        verify_ocsp=True,
        verification_time=_NOW,
    )
    ar = result.anchor_results[0]
    assert ar.valid is False
    assert ar.cert_status == "MISSING_LTV_ARTIFACTS"
    assert ar.ltv_artifacts_present is True
    assert "OCSP" in (ar.reason or "")


def test_verify_ocsp_unknown_status() -> None:
    """verifier.py 399-410 — OCSP 'unknown' -> reason='OCSP responder reports cert status unknown'."""
    chain = _build_chain(1)
    authority = TestTSAAuthority(now=_NOW)
    anchor, root_der = _real_anchor(chain, 0, authority=authority)

    ocsp_result = MagicMock()
    ocsp_result.cert_status = "unknown"

    with patch("attestplane.anchoring.ocsp.parse_and_verify_ocsp", return_value=ocsp_result):
        result = verify_chain_with_anchors(
            chain,
            [anchor],
            trust_roots_der=[root_der],
            verify_ocsp=True,
            verification_time=_NOW,
        )
    ar = result.anchor_results[0]
    assert ar.valid is False
    assert "unknown" in (ar.reason or "")
    assert ar.cert_status == "MISSING_LTV_ARTIFACTS"
    assert ar.ltv_artifacts_present is True


def test_verify_ocsp_good_via_mock() -> None:
    """verifier.py 412-421 — OCSP 'good' -> valid=True, cert_status=VALID."""
    chain = _build_chain(1)
    authority = TestTSAAuthority(now=_NOW)
    anchor, root_der = _real_anchor(chain, 0, authority=authority)

    ocsp_result = MagicMock()
    ocsp_result.cert_status = "good"

    with patch("attestplane.anchoring.ocsp.parse_and_verify_ocsp", return_value=ocsp_result):
        result = verify_chain_with_anchors(
            chain,
            [anchor],
            trust_roots_der=[root_der],
            verify_ocsp=True,
            verification_time=_NOW,
        )
    ar = result.anchor_results[0]
    assert ar.valid is True
    assert ar.cert_status == "VALID"


def test_verify_ocsp_no_issuer_available_empty_trust_roots() -> None:
    """verifier.py 355-356 — no issuer found + trust_roots_der=[] -> OCSP failure."""
    chain = _build_chain(1)
    # Build anchor with a cert chain that the OCSP logic cannot resolve an issuer from.
    # Use leaf-only chain, and trust_roots_der=[] so there's no fallback.
    # But rfc3161 verify_timestamp_token needs trust_roots_der too.
    # We patch verify_timestamp_token to succeed, then let OCSP run.
    authority = TestTSAAuthority(now=_NOW)
    materials = authority.materials()
    token_der = authority.sign_timestamp_response(chain[0].event_hash, gen_time=_NOW, serial_number=1)
    real_ocsp = authority.issue_real_ocsp_response(gen_time=_NOW)

    # Anchor with only a leaf cert (no root) and no trust_roots -> issuer_der is None
    anchor = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain[0].event_hash,
        tsa_provider_id=f"test.tsa:{authority.common_name}",
        tsa_token=token_der,
        tsa_cert_chain=(materials.leaf_cert_der,),  # leaf only, issuer (root) not in chain
        ocsp_responses=(real_ocsp,),
        issued_at_claimed=_NOW,
    )

    # trust_roots_der=[] -> no issuer fallback -> "no issuer cert available"
    # But rfc3161 verify would fail with empty trust roots too. Patch it to pass.
    from attestplane.anchoring import rfc3161 as _rfc3161_mod

    with patch.object(_rfc3161_mod, "verify_timestamp_token", return_value=None):
        result = verify_chain_with_anchors(
            chain,
            [anchor],
            trust_roots_der=[],
            verify_ocsp=True,
            verification_time=_NOW,
        )
    ar = result.anchor_results[0]
    assert ar.valid is False
    assert "no issuer cert available" in (ar.reason or "")
    assert ar.cert_status == "MISSING_LTV_ARTIFACTS"


def test_verify_ocsp_issuer_fallback_to_trust_root() -> None:
    """verifier.py 353-354 — no match in tsa_cert_chain -> fallback to trust_roots_der[0]."""
    chain = _build_chain(1)
    # Two separate authorities: token from auth1, but cert_chain only has leaf (no root).
    # The root from auth1 IS in trust_roots_der -> fallback path hit.
    authority = TestTSAAuthority(now=_NOW)
    anchor, root_der = _real_anchor(chain, 0, authority=authority)
    # Remove root from cert_chain so issuer search loop fails, then fallback to trust root
    anchor_leaf_only = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=anchor.anchored_event_hash,
        tsa_provider_id=anchor.tsa_provider_id,
        tsa_token=anchor.tsa_token,
        tsa_cert_chain=(anchor.tsa_cert_chain[0],),  # leaf only (no root)
        ocsp_responses=anchor.ocsp_responses,
        issued_at_claimed=anchor.issued_at_claimed,
    )

    result = verify_chain_with_anchors(
        chain,
        [anchor_leaf_only],
        trust_roots_der=[root_der],
        verify_ocsp=True,
        verification_time=_NOW,
    )
    # With root as fallback issuer, OCSP should pass and anchor verifies.
    ar = result.anchor_results[0]
    assert ar.valid is True
    assert ar.cert_status == "VALID"


def test_verify_ocsp_exception_in_cert_load_continues() -> None:
    """verifier.py 351-352 — Exception loading candidate cert -> continue (skipped in loop)."""
    chain = _build_chain(1)
    authority = TestTSAAuthority(now=_NOW)
    anchor, root_der = _real_anchor(chain, 0, authority=authority)

    # Inject a bad cert at the start of the chain; the real root follows.
    bad_chain_entry = b"\xff\xff\xff\xff"  # not valid DER -> Certificate.load raises -> continue
    anchor_with_bad = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=anchor.anchored_event_hash,
        tsa_provider_id=anchor.tsa_provider_id,
        tsa_token=anchor.tsa_token,
        tsa_cert_chain=(bad_chain_entry, *anchor.tsa_cert_chain),
        ocsp_responses=anchor.ocsp_responses,
        issued_at_claimed=anchor.issued_at_claimed,
    )

    result = verify_chain_with_anchors(
        chain,
        [anchor_with_bad],
        trust_roots_der=[root_der],
        verify_ocsp=True,
        verification_time=_NOW,
    )
    # Despite bad first entry, loop continues and finds issuer from the rest.
    ar = result.anchor_results[0]
    assert ar.valid is True


# ---------------------------------------------------------------------------
# verifier.py 438 — else branch: mixed anchors, not all VALID_UNVERIFIED
# ---------------------------------------------------------------------------


def test_verify_status_mixed_not_all_valid_unverified() -> None:
    """verifier.py 438 — else: some VALID_UNVERIFIED + some failed -> 'failed'."""
    chain = _build_chain(2)
    good_quarantined = _good_anchor(chain, 0)  # will be VALID_UNVERIFIED (no trust_roots)
    bad_hash = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=1,
        anchored_event_hash=b"\xff" * 32,  # wrong hash -> failed
        tsa_provider_id="other.tsa",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(b"\x01" * 32,),
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=_NOW,
    )
    result = verify_chain_with_anchors(chain, [good_quarantined, bad_hash])
    # good_quarantined -> VALID_UNVERIFIED (valid=False)
    # bad_hash -> hash mismatch (valid=False)
    # Not all VALID_UNVERIFIED, not all valid -> else branch -> 'failed'
    assert result.verification_status == "failed"


def test_verify_status_all_valid_unverified_is_quarantined() -> None:
    """verifier.py 439-440 — all VALID_UNVERIFIED (no trust_roots_der) -> 'quarantined'."""
    chain = _build_chain(2)
    anchors = [_good_anchor(chain, 0), _good_anchor(chain, 1, provider_id="tsa2")]
    result = verify_chain_with_anchors(chain, anchors)
    assert result.verification_status == "quarantined"
    assert all(a.cert_status == "VALID_UNVERIFIED" for a in result.anchor_results)


def test_verify_status_failed_with_trust_roots_but_bad_anchor() -> None:
    """verifier.py — when trust_roots given but anchor cross-ref fails, status='failed'."""
    chain = _build_chain(1)
    bad = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=b"\xff" * 32,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(b"\x01" * 32,),
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=_NOW,
    )
    result = verify_chain_with_anchors(chain, [bad], trust_roots_der=[b"\xca" * 32])
    assert result.verification_status == "failed"


# ---------------------------------------------------------------------------
# verifier.py seq_out_of_range ltv_artifacts_present branching
# ---------------------------------------------------------------------------


def test_verify_seq_out_of_range_ltv_present_when_cert_chain_nonempty() -> None:
    chain = _build_chain(1)
    anchor = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=99,
        anchored_event_hash=b"\x00" * 32,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(b"\x01" * 32,),
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=_NOW,
    )
    result = verify_chain_with_anchors(chain, [anchor])
    assert result.anchor_results[0].ltv_artifacts_present is True
    assert "not in chain" in (result.anchor_results[0].reason or "")


def test_verify_seq_out_of_range_ltv_absent_when_cert_chain_empty() -> None:
    chain = _build_chain(1)
    anchor = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=99,
        anchored_event_hash=b"\x00" * 32,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(),
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=_NOW,
    )
    result = verify_chain_with_anchors(chain, [anchor])
    assert result.anchor_results[0].ltv_artifacts_present is False


# ---------------------------------------------------------------------------
# verifier.py hash-mismatch ltv_artifacts_present branching
# ---------------------------------------------------------------------------


def test_verify_hash_mismatch_ltv_present() -> None:
    chain = _build_chain(1)
    anchor = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=b"\xff" * 32,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(b"\x01" * 32,),
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=_NOW,
    )
    result = verify_chain_with_anchors(chain, [anchor])
    assert result.anchor_results[0].ltv_artifacts_present is True


def test_verify_hash_mismatch_ltv_absent() -> None:
    chain = _build_chain(1)
    anchor = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=b"\xff" * 32,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(),
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=_NOW,
    )
    result = verify_chain_with_anchors(chain, [anchor])
    assert result.anchor_results[0].ltv_artifacts_present is False


# ---------------------------------------------------------------------------
# verifier.py 511-573 — verify_live_anchor_with_provider: three-state semantics
# ---------------------------------------------------------------------------


def test_live_anchor_tsa_unavailable_returns_quarantined() -> None:
    """verifier.py 520-528 — TSAUnavailableError -> quarantined (exit_code=2)."""
    chain = _build_chain(1)
    provider = MagicMock()
    provider.request_timestamp.side_effect = TSAUnavailableError("tsa down")

    result = verify_live_anchor_with_provider(chain[0], provider)

    assert result.status == "quarantined"
    assert result.exit_code == 2
    assert result.exit_code == LIVE_ANCHOR_QUARANTINE_EXIT_CODE
    assert result.reason_code == VERIFY_REASON_ANCHOR_QUARANTINED
    assert result.claim_verified is False
    assert result.anchor_record is None
    assert result.verification_result is None


def test_live_anchor_verified_ok() -> None:
    """verifier.py 538-546 — anchor verifies OK -> status='verified', exit_code=0."""
    chain = _build_chain(1)
    authority = TestTSAAuthority(now=_NOW)

    req_anchor, root_der = _real_anchor(chain, 0, authority=authority)
    provider = MagicMock()
    provider.request_timestamp.return_value = req_anchor

    result = verify_live_anchor_with_provider(
        chain[0],
        provider,
        trust_roots_der=[root_der],
        verify_ocsp=True,
        verification_time=_NOW,
    )

    assert result.status == "verified"
    assert result.exit_code == 0
    assert result.reason_code is None
    assert result.claim_verified is True
    assert result.anchor_record is req_anchor
    assert result.verification_result is not None
    assert result.verification_result.ok is True


def test_live_anchor_quarantined_when_no_ocsp_responses() -> None:
    """verifier.py 562-571 — empty ocsp_responses -> lacks_ltv_artifacts=True -> quarantined."""
    chain = _build_chain(1)
    anchor_no_ocsp = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain[0].event_hash,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(b"\x01" * 32,),
        ocsp_responses=(),  # empty
        issued_at_claimed=_NOW,
    )
    provider = MagicMock()
    provider.request_timestamp.return_value = anchor_no_ocsp

    result = verify_live_anchor_with_provider(chain[0], provider)

    assert result.status == "quarantined"
    assert result.exit_code == LIVE_ANCHOR_QUARANTINE_EXIT_CODE
    assert result.reason_code == VERIFY_REASON_ANCHOR_QUARANTINED
    assert result.claim_verified is False
    assert result.anchor_record is anchor_no_ocsp
    assert result.verification_result is not None


def test_live_anchor_quarantined_when_no_cert_chain() -> None:
    """verifier.py 562-571 — empty tsa_cert_chain -> lacks_ltv_artifacts=True -> quarantined."""
    chain = _build_chain(1)
    anchor_no_chain = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain[0].event_hash,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(),  # empty
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=_NOW,
    )
    provider = MagicMock()
    provider.request_timestamp.return_value = anchor_no_chain

    result = verify_live_anchor_with_provider(chain[0], provider)

    assert result.status == "quarantined"
    assert result.exit_code == 2
    assert result.reason_code == VERIFY_REASON_ANCHOR_QUARANTINED
    assert result.claim_verified is False


def test_live_anchor_failed_when_artifacts_present_but_invalid() -> None:
    """verifier.py 573-580 — LTV artifacts present + verification fails -> 'failed', exit_code=1."""
    chain = _build_chain(1)
    # Hash mismatch -> cross-ref fails -> verification.ok=False, lacks_ltv_artifacts=False
    anchor_bad = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=b"\xff" * 32,  # wrong hash
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(b"\x01" * 32,),
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=_NOW,
    )
    provider = MagicMock()
    provider.request_timestamp.return_value = anchor_bad

    result = verify_live_anchor_with_provider(chain[0], provider)

    assert result.status == "failed"
    assert result.exit_code == 1
    assert result.reason_code == VERIFY_REASON_ANCHOR_INVALID
    assert result.claim_verified is False
    assert result.anchor_record is anchor_bad
    assert result.verification_result is not None


def test_live_anchor_failed_when_valid_unverified_no_trust_roots() -> None:
    """verifier.py — VALID_UNVERIFIED with no trust_roots -> ok=False, artifacts present -> failed."""
    chain = _build_chain(1)
    # Anchor with full LTV artifacts but no trust_roots -> VALID_UNVERIFIED, ok=False
    # verification.ok=False, lacks_ltv_artifacts=False -> 'failed'
    anchor = _good_anchor(chain, 0)
    provider = MagicMock()
    provider.request_timestamp.return_value = anchor

    result = verify_live_anchor_with_provider(chain[0], provider)
    # VALID_UNVERIFIED -> ok=False; both cert_chain and ocsp_responses present -> lacks_ltv=False -> failed
    assert result.status == "failed"
    assert result.exit_code == 1
    assert result.reason_code == VERIFY_REASON_ANCHOR_INVALID


# ---------------------------------------------------------------------------
# verifier.py 233-243 — non-UTC timezone (aware but not UTC)
# ---------------------------------------------------------------------------


def test_verify_non_utc_timezone_rejected() -> None:
    """verifier.py 233-243 — UTC+5 timezone -> 'issued_at_claimed is not UTC'."""
    chain = _build_chain(1)
    tz_plus5 = timezone(timedelta(hours=5))
    non_utc_time = datetime(2026, 5, 17, 12, 0, 0, tzinfo=tz_plus5)
    bad = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain[0].event_hash,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(b"\x01" * 32,),
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=non_utc_time,
    )
    result = verify_chain_with_anchors(chain, [bad])
    ar = result.anchor_results[0]
    assert ar.valid is False
    assert "not UTC" in (ar.reason or "")
    assert ar.cert_status == "MISSING_LTV_ARTIFACTS"


def test_verify_non_utc_timezone_ltv_present_branch() -> None:
    """verifier.py 239 — non-UTC with cert chain present -> ltv_artifacts_present=True."""
    chain = _build_chain(1)
    tz_minus3 = timezone(timedelta(hours=-3))
    non_utc = datetime(2026, 5, 17, 12, 0, 0, tzinfo=tz_minus3)
    anchor = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain[0].event_hash,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00" * 32,
        tsa_cert_chain=(b"\x01" * 32,),  # non-empty
        ocsp_responses=(b"\x02" * 32,),
        issued_at_claimed=non_utc,
    )
    result = verify_chain_with_anchors(chain, [anchor])
    assert result.anchor_results[0].ltv_artifacts_present is True


# ---------------------------------------------------------------------------
# verifier.py 436 — verification_status='not_performed' when no anchors provided
# ---------------------------------------------------------------------------


def test_verify_empty_anchors_not_performed() -> None:
    """verifier.py 436 — empty anchor list -> verification_status='not_performed'."""
    chain = _build_chain(2)
    result = verify_chain_with_anchors(chain, [])
    assert result.verification_status == "not_performed"
    assert result.ok is False
    assert result.chain_ok is True
    assert len(result.anchor_results) == 0


def test_verify_completely_empty_inputs_not_performed() -> None:
    """verifier.py 436 — empty events AND empty anchors -> not_performed."""
    result = verify_chain_with_anchors([], [])
    assert result.verification_status == "not_performed"


def test_live_anchor_exit_code_constant_equals_two() -> None:
    """LIVE_ANCHOR_QUARANTINE_EXIT_CODE == 2 per ADR-0003 exit-code contract."""
    assert LIVE_ANCHOR_QUARANTINE_EXIT_CODE == 2


def test_live_anchor_uses_verification_time_param() -> None:
    """verifier.py 511-512 — verification_time forwarded as 'now' to provider."""
    chain = _build_chain(1)
    vtime = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
    anchor = _good_anchor(chain, 0)
    provider = MagicMock()
    provider.request_timestamp.return_value = anchor

    verify_live_anchor_with_provider(chain[0], provider, verification_time=vtime)

    provider.request_timestamp.assert_called_once()
    call_kwargs = provider.request_timestamp.call_args.kwargs
    assert call_kwargs.get("now") == vtime


def test_live_anchor_default_now_is_utc() -> None:
    """verifier.py 512 — when verification_time is None, now defaults to UTC."""
    chain = _build_chain(1)
    anchor = _good_anchor(chain, 0)
    provider = MagicMock()
    provider.request_timestamp.return_value = anchor

    before = datetime.now(UTC)
    verify_live_anchor_with_provider(chain[0], provider)
    after = datetime.now(UTC)

    call_kwargs = provider.request_timestamp.call_args.kwargs
    used_now = call_kwargs.get("now")
    assert used_now is not None
    assert before <= used_now <= after


def test_live_anchor_request_uses_event_hash() -> None:
    """verifier.py 511 — TimestampRequest.digest = event.event_hash."""
    chain = _build_chain(1)
    anchor = _good_anchor(chain, 0)
    provider = MagicMock()
    provider.request_timestamp.return_value = anchor

    verify_live_anchor_with_provider(chain[0], provider)

    call_args = provider.request_timestamp.call_args
    req: TimestampRequest = call_args.args[0]
    assert req.digest == chain[0].event_hash


def test_live_anchor_request_uses_event_seq() -> None:
    """verifier.py 515 — anchored_seq kwarg = event.seq (= 0 for first event)."""
    chain = _build_chain(1)  # single event, seq=0
    anchor = _good_anchor(chain, 0)
    provider = MagicMock()
    provider.request_timestamp.return_value = anchor

    verify_live_anchor_with_provider(chain[0], provider)

    call_kwargs = provider.request_timestamp.call_args.kwargs
    assert call_kwargs.get("anchored_seq") == chain[0].seq
    assert chain[0].seq == 0
