# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.anchoring`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from attestplane.anchoring import (
    ANCHOR_SCHEMA_VERSION,
    AnchorBoundaryError,
    AnchorError,
    AnchorPolicy,
    AnchorRecord,
    MockTSAProvider,
    MultiTSAProvider,
    TimestampRequest,
    TSAProvider,
    TSAUnavailableError,
    verify_chain_with_anchors,
)
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import ChainedEvent, ChainHead, EventDraft

# --- Fixture helpers ---------------------------------------------------------


def _build_chain(n: int) -> list[ChainedEvent]:
    ts = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    chain: list[ChainedEvent] = []
    head: ChainHead = genesis_head()
    for i in range(n):
        draft = EventDraft(
            event_type="eval_event",
            actor=f"agent://test/{i}",
            payload={"i": i},
        )
        ev = chain_extend(head, draft, now=ts,
                          event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


# --- AnchorRecord invariants -------------------------------------------------


def test_anchor_record_rejects_wrong_schema_version() -> None:
    with pytest.raises(AnchorError, match="anchor_schema_version"):
        AnchorRecord(
            anchor_schema_version=99,
            anchored_seq=0,
            anchored_event_hash=b"\x00" * 32,
            tsa_provider_id="x",
            tsa_token=b"\x00",
            tsa_cert_chain=(b"\x00",),
            ocsp_responses=(b"\x00",),
            issued_at_claimed=datetime.now(UTC),
        )


def test_anchor_record_rejects_short_hash() -> None:
    with pytest.raises(AnchorError, match="32 bytes"):
        AnchorRecord(
            anchor_schema_version=ANCHOR_SCHEMA_VERSION,
            anchored_seq=0,
            anchored_event_hash=b"\x00" * 16,
            tsa_provider_id="x",
            tsa_token=b"\x00",
            tsa_cert_chain=(b"\x00",),
            ocsp_responses=(b"\x00",),
            issued_at_claimed=datetime.now(UTC),
        )


def test_anchor_record_rejects_negative_seq() -> None:
    with pytest.raises(AnchorError, match="anchored_seq"):
        AnchorRecord(
            anchor_schema_version=ANCHOR_SCHEMA_VERSION,
            anchored_seq=-1,
            anchored_event_hash=b"\x00" * 32,
            tsa_provider_id="x",
            tsa_token=b"\x00",
            tsa_cert_chain=(b"\x00",),
            ocsp_responses=(b"\x00",),
            issued_at_claimed=datetime.now(UTC),
        )


def test_anchor_record_rejects_empty_provider_id() -> None:
    with pytest.raises(AnchorError, match="tsa_provider_id"):
        AnchorRecord(
            anchor_schema_version=ANCHOR_SCHEMA_VERSION,
            anchored_seq=0,
            anchored_event_hash=b"\x00" * 32,
            tsa_provider_id="",
            tsa_token=b"\x00",
            tsa_cert_chain=(b"\x00",),
            ocsp_responses=(b"\x00",),
            issued_at_claimed=datetime.now(UTC),
        )


# --- AnchorPolicy invariants --------------------------------------------------


def test_anchor_policy_defaults() -> None:
    p = AnchorPolicy()
    assert p.batch_size == 64
    assert p.max_idle_seconds == 60
    assert p.per_event is False


def test_anchor_policy_rejects_zero_batch_size() -> None:
    with pytest.raises(AnchorError, match="batch_size"):
        AnchorPolicy(batch_size=0)


def test_anchor_policy_rejects_zero_idle() -> None:
    with pytest.raises(AnchorError, match="max_idle_seconds"):
        AnchorPolicy(max_idle_seconds=0)


# --- TimestampRequest --------------------------------------------------------


def test_timestamp_request_rejects_non_sha256_digest() -> None:
    with pytest.raises(AnchorError, match="32 bytes"):
        TimestampRequest(digest=b"\x00" * 16)


def test_timestamp_request_accepts_nonce() -> None:
    req = TimestampRequest(digest=b"\x00" * 32, nonce=b"random")
    assert req.nonce == b"random"


# --- TSAProvider forbidden-verb gate -----------------------------------------


@pytest.mark.parametrize(
    "forbidden_method",
    ["mutate", "rewrite", "replace", "revoke", "retract", "delete", "remove"],
)
def test_tsa_provider_subclass_rejects_forbidden_verb(forbidden_method: str) -> None:
    def make_bad() -> None:
        namespace = {
            "provider_id": "bad",
            "schema_version": ANCHOR_SCHEMA_VERSION,
            "request_timestamp": lambda self, req, **kw: None,
            forbidden_method: lambda self, *a, **kw: None,
        }
        type("BadProvider", (TSAProvider,), namespace)

    with pytest.raises(AnchorBoundaryError, match="forbidden mutating method"):
        make_bad()


def test_tsa_provider_abstract_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        TSAProvider()  # type: ignore[abstract]


# --- MockTSAProvider ---------------------------------------------------------


def test_mock_provider_produces_deterministic_anchor() -> None:
    provider = MockTSAProvider(fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    chain = _build_chain(1)
    req = TimestampRequest(digest=chain[0].event_hash)

    a1 = provider.request_timestamp(req, anchored_seq=0)
    a2 = provider.request_timestamp(req, anchored_seq=0)
    assert a1 == a2


def test_mock_provider_token_depends_on_digest() -> None:
    provider = MockTSAProvider(fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    a = provider.request_timestamp(TimestampRequest(digest=b"\x00" * 32))
    b = provider.request_timestamp(TimestampRequest(digest=b"\x01" * 32))
    assert a.tsa_token != b.tsa_token


def test_mock_provider_raises_when_configured_to_fail() -> None:
    provider = MockTSAProvider(fail_with=TSAUnavailableError("simulated outage"))
    with pytest.raises(TSAUnavailableError, match="simulated outage"):
        provider.request_timestamp(TimestampRequest(digest=b"\x00" * 32))


def test_mock_provider_rejects_empty_provider_id() -> None:
    with pytest.raises(ValueError, match="provider_id"):
        MockTSAProvider(provider_id="")


def test_mock_provider_rejects_naive_datetime() -> None:
    naive = datetime(2026, 5, 17, 12, 0, 0)  # no tzinfo
    provider = MockTSAProvider(fixed_time=naive)
    with pytest.raises(TSAUnavailableError, match="UTC"):
        provider.request_timestamp(TimestampRequest(digest=b"\x00" * 32))


def test_mock_provider_uses_explicit_now() -> None:
    provider = MockTSAProvider()
    explicit = datetime(2030, 1, 1, 0, 0, 0, tzinfo=UTC)
    anchor = provider.request_timestamp(
        TimestampRequest(digest=b"\x00" * 32), now=explicit,
    )
    assert anchor.issued_at_claimed == explicit


def test_mock_provider_writes_well_formed_anchor_record() -> None:
    provider = MockTSAProvider(fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    chain = _build_chain(1)
    anchor = provider.request_timestamp(
        TimestampRequest(digest=chain[0].event_hash), anchored_seq=0,
    )
    assert anchor.anchor_schema_version == ANCHOR_SCHEMA_VERSION
    assert anchor.anchored_seq == 0
    assert anchor.anchored_event_hash == chain[0].event_hash
    assert anchor.tsa_provider_id == "mock.tsa.local"
    assert len(anchor.tsa_cert_chain) == 1
    assert len(anchor.ocsp_responses) == 1


# --- MultiTSAProvider --------------------------------------------------------


def test_multi_provider_fans_out() -> None:
    p1 = MockTSAProvider(provider_id="alpha", fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    p2 = MockTSAProvider(provider_id="beta", fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    multi = MultiTSAProvider([p1, p2])

    anchors = multi.request_timestamps(
        TimestampRequest(digest=b"\x00" * 32), anchored_seq=0,
    )
    assert len(anchors) == 2
    assert {a.tsa_provider_id for a in anchors} == {"alpha", "beta"}


def test_multi_provider_requires_at_least_one() -> None:
    with pytest.raises(ValueError, match="at least one"):
        MultiTSAProvider([])


def test_multi_provider_rejects_duplicate_ids() -> None:
    p1 = MockTSAProvider(provider_id="same")
    p2 = MockTSAProvider(provider_id="same")
    with pytest.raises(ValueError, match="distinct provider_id"):
        MultiTSAProvider([p1, p2])


def test_multi_provider_fails_fast_by_default() -> None:
    good = MockTSAProvider(provider_id="alpha", fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    bad = MockTSAProvider(provider_id="beta", fail_with=TSAUnavailableError("dead"))
    multi = MultiTSAProvider([good, bad])
    with pytest.raises(TSAUnavailableError, match="dead"):
        multi.request_timestamps(TimestampRequest(digest=b"\x00" * 32))


def test_multi_provider_partial_when_tolerated() -> None:
    good = MockTSAProvider(provider_id="alpha", fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    bad = MockTSAProvider(provider_id="beta", fail_with=TSAUnavailableError("dead"))
    multi = MultiTSAProvider([good, bad], tolerate_partial=True)
    anchors = multi.request_timestamps(TimestampRequest(digest=b"\x00" * 32))
    assert len(anchors) == 1
    assert anchors[0].tsa_provider_id == "alpha"


def test_multi_provider_all_fail_partial_mode() -> None:
    p1 = MockTSAProvider(provider_id="alpha", fail_with=TSAUnavailableError("one"))
    p2 = MockTSAProvider(provider_id="beta", fail_with=TSAUnavailableError("two"))
    multi = MultiTSAProvider([p1, p2], tolerate_partial=True)
    with pytest.raises(TSAUnavailableError):
        multi.request_timestamps(TimestampRequest(digest=b"\x00" * 32))


def test_multi_provider_provider_ids_property() -> None:
    p1 = MockTSAProvider(provider_id="alpha")
    p2 = MockTSAProvider(provider_id="beta")
    assert MultiTSAProvider([p1, p2]).provider_ids == ("alpha", "beta")


# --- verify_chain_with_anchors -----------------------------------------------


def _good_anchor(chain: list[ChainedEvent], seq: int) -> AnchorRecord:
    provider = MockTSAProvider(fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    return provider.request_timestamp(
        TimestampRequest(digest=chain[seq].event_hash), anchored_seq=seq,
    )


def test_verify_empty_inputs() -> None:
    result = verify_chain_with_anchors([], [])
    assert result.ok is False
    assert result.chain_ok is True
    assert result.verification_status == "not_performed"
    assert result.anchored_seqs == frozenset()
    assert result.unanchored_seqs == frozenset()


def test_verify_unanchored_chain() -> None:
    chain = _build_chain(3)
    result = verify_chain_with_anchors(chain, [])
    assert result.chain_ok is True
    assert result.ok is False
    assert result.verification_status == "not_performed"
    assert result.unanchored_seqs == frozenset({0, 1, 2})
    assert result.anchored_seqs == frozenset()


def test_verify_chain_with_one_good_anchor() -> None:
    chain = _build_chain(3)
    anchors = [_good_anchor(chain, 2)]  # anchor the tip
    result = verify_chain_with_anchors(chain, anchors)
    assert result.ok is True
    assert result.verification_status == "verified"
    assert result.anchor_results[0].valid is True
    assert result.anchor_results[0].cert_status == "VALID_UNVERIFIED"
    assert result.anchor_results[0].ltv_artifacts_present is True
    assert result.anchored_seqs == frozenset({2})
    assert result.unanchored_seqs == frozenset({0, 1})


def test_verify_chain_with_multi_anchor_per_seq() -> None:
    """Plurality: two TSAs anchor the same tip."""
    chain = _build_chain(2)
    p1 = MockTSAProvider(provider_id="alpha", fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    p2 = MockTSAProvider(provider_id="beta", fixed_time=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC))
    multi = MultiTSAProvider([p1, p2])
    anchors = multi.request_timestamps(
        TimestampRequest(digest=chain[1].event_hash), anchored_seq=1,
    )
    result = verify_chain_with_anchors(chain, anchors)
    assert result.ok is True
    assert len(result.anchor_results) == 2
    assert all(a.valid for a in result.anchor_results)
    assert result.anchored_seqs == frozenset({1})


def test_verify_detects_hash_mismatch() -> None:
    chain = _build_chain(2)
    # Forge an anchor that points at seq=0 but has the wrong hash.
    bad = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=b"\xff" * 32,  # wrong
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00",
        tsa_cert_chain=(b"\x00",),
        ocsp_responses=(b"\x00",),
        issued_at_claimed=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC),
    )
    result = verify_chain_with_anchors(chain, [bad])
    assert result.ok is False
    assert result.verification_status == "failed"
    assert result.anchor_results[0].valid is False
    assert "anchored_event_hash mismatch" in (result.anchor_results[0].reason or "")


def test_verify_detects_seq_out_of_range() -> None:
    chain = _build_chain(2)
    bad = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=99,
        anchored_event_hash=b"\x00" * 32,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00",
        tsa_cert_chain=(b"\x00",),
        ocsp_responses=(b"\x00",),
        issued_at_claimed=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC),
    )
    result = verify_chain_with_anchors(chain, [bad])
    assert result.ok is False
    assert "not in chain" in (result.anchor_results[0].reason or "")


def test_verify_detects_missing_ltv_artifacts() -> None:
    chain = _build_chain(2)
    bad = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain[0].event_hash,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00",
        tsa_cert_chain=(),  # empty — violates CAdES-A
        ocsp_responses=(b"\x00",),
        issued_at_claimed=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC),
    )
    result = verify_chain_with_anchors(chain, [bad])
    assert result.ok is False
    assert result.anchor_results[0].cert_status == "MISSING_LTV_ARTIFACTS"
    assert "long-term validation" in (result.anchor_results[0].reason or "")


def test_verify_detects_non_utc_timestamp() -> None:
    chain = _build_chain(1)
    bad = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain[0].event_hash,
        tsa_provider_id="mock.tsa.local",
        tsa_token=b"\x00",
        tsa_cert_chain=(b"\x00",),
        ocsp_responses=(b"\x00",),
        issued_at_claimed=datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone(timedelta(hours=5))),
    )
    result = verify_chain_with_anchors(chain, [bad])
    assert result.ok is False
    assert "not UTC" in (result.anchor_results[0].reason or "")


def test_verify_propagates_chain_failure() -> None:
    """A broken chain causes ok=False even when anchors verify."""
    chain = _build_chain(2)
    # Mutate the chain so verify_chain fails.
    from dataclasses import replace
    chain[1] = replace(chain[1], prev_hash=b"\xff" * 32)
    anchor = _good_anchor(chain, 0)
    result = verify_chain_with_anchors(chain, [anchor])
    assert result.chain_ok is False
    assert result.ok is False
    # The anchor itself is still cross-reference-valid for seq=0.
    assert result.anchor_results[0].valid is True


def test_v1_cert_status_is_unverified() -> None:
    """v1 anchors with full LTV artifacts are 'VALID_UNVERIFIED' pending M5 ASN.1 work."""
    chain = _build_chain(1)
    result = verify_chain_with_anchors(chain, [_good_anchor(chain, 0)])
    assert result.anchor_results[0].cert_status == "VALID_UNVERIFIED"


def test_verify_chain_with_anchors_is_read_only() -> None:
    chain = _build_chain(2)
    anchors = [_good_anchor(chain, 1)]
    before_chain = list(chain)
    before_anchors = list(anchors)
    result = verify_chain_with_anchors(chain, anchors)
    assert result.ok is True
    assert chain == before_chain
    assert anchors == before_anchors
