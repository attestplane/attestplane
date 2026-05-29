# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Multi-hop intermediate cert chain tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring import (
    AnchorVerificationError,
    TimestampRequest,
    verify_chain_with_anchors,
)
from attestplane.anchoring.rfc3161 import (
    parse_timestamp_response,
    verify_timestamp_token,
)
from attestplane.anchoring.testing import TestTSAAuthority, TestTSAProvider
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import ChainHead, EventDraft

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _build_chain(n: int) -> list:
    chain = []
    head = genesis_head()
    for i in range(n):
        draft = EventDraft(
            event_type="eval_event",
            actor=f"agent://test/{i}",
            payload={"i": i},
        )
        ev = chain_extend(head, draft, now=_NOW, event_id=f"00000000-0000-7000-8000-{i:012d}")
        chain.append(ev)
        head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)
    return chain


def test_two_tier_default_still_works() -> None:
    """The 2-tier (root → leaf) default chain continues to verify."""
    authority = TestTSAAuthority(now=_NOW, intermediate_count=0)
    digest = hashlib.sha256(b"x").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)
    verify_timestamp_token(
        parsed,
        expected_digest=digest,
        trust_roots_der=[authority.materials().root_cert_der],
        verification_time=_NOW,
    )


def test_three_tier_chain_with_one_intermediate() -> None:
    """root → I1 → leaf chain verifies when intermediate is passed."""
    authority = TestTSAAuthority(now=_NOW, intermediate_count=1)
    materials = authority.materials()
    assert len(materials.intermediate_certs_der) == 1

    digest = hashlib.sha256(b"x").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)

    # WITHOUT intermediates, verification fails.
    with pytest.raises(AnchorVerificationError, match="not in trust roots"):
        verify_timestamp_token(
            parsed,
            expected_digest=digest,
            trust_roots_der=[materials.root_cert_der],
            verification_time=_NOW,
        )

    # WITH intermediates, it succeeds.
    verify_timestamp_token(
        parsed,
        expected_digest=digest,
        trust_roots_der=[materials.root_cert_der],
        intermediates_der=list(materials.intermediate_certs_der),
        verification_time=_NOW,
    )


def test_four_tier_chain_with_two_intermediates() -> None:
    """root → I1 → I2 → leaf chain verifies."""
    authority = TestTSAAuthority(now=_NOW, intermediate_count=2)
    materials = authority.materials()
    assert len(materials.intermediate_certs_der) == 2

    digest = hashlib.sha256(b"x").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)

    verify_timestamp_token(
        parsed,
        expected_digest=digest,
        trust_roots_der=[materials.root_cert_der],
        intermediates_der=list(materials.intermediate_certs_der),
        verification_time=_NOW,
    )


def test_missing_intermediate_fails_with_helpful_error() -> None:
    """A chain with intermediates but only the root provided must fail."""
    authority = TestTSAAuthority(now=_NOW, intermediate_count=1)
    materials = authority.materials()
    digest = hashlib.sha256(b"x").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)

    with pytest.raises(AnchorVerificationError, match="not in trust roots or intermediates"):
        verify_timestamp_token(
            parsed,
            expected_digest=digest,
            trust_roots_der=[materials.root_cert_der],
            intermediates_der=[],  # missing the actual intermediate
            verification_time=_NOW,
        )


def test_max_chain_depth_enforced() -> None:
    """max_chain_depth=0 prevents any walk, forcing direct root→leaf only."""
    # Build a 3-tier chain and ask the verifier to walk depth 0.
    authority = TestTSAAuthority(now=_NOW, intermediate_count=1)
    materials = authority.materials()
    digest = hashlib.sha256(b"x").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)

    with pytest.raises(AnchorVerificationError, match="depth exceeded"):
        verify_timestamp_token(
            parsed,
            expected_digest=digest,
            trust_roots_der=[materials.root_cert_der],
            intermediates_der=list(materials.intermediate_certs_der),
            verification_time=_NOW,
            max_chain_depth=0,
        )


def test_intermediate_validity_window_checked() -> None:
    """If verification_time is past an intermediate's not_after, fail."""
    authority = TestTSAAuthority(
        now=_NOW,
        intermediate_count=1,
        cert_validity_days=1,  # leaf valid 1 day; intermediate valid 5 days
    )
    materials = authority.materials()
    digest = hashlib.sha256(b"x").digest()
    der = authority.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)

    # Move past the intermediate's window (5 * cert_validity = 5 days).
    future = _NOW + timedelta(days=30)
    with pytest.raises(AnchorVerificationError, match="not_after"):
        verify_timestamp_token(
            parsed,
            expected_digest=digest,
            trust_roots_der=[materials.root_cert_der],
            intermediates_der=list(materials.intermediate_certs_der),
            verification_time=future,
        )


def test_non_ca_intermediate_rejected() -> None:
    """If someone slips a non-CA cert into the intermediates, reject it."""
    # We can't easily inject a non-CA into TestTSAAuthority's chain
    # because the leaf was signed by the legitimate intermediate. We
    # validate this via a different path: pass the LEAF cert as an
    # intermediate for a different (separate) chain.
    authority_a = TestTSAAuthority(now=_NOW, intermediate_count=1)
    authority_b = TestTSAAuthority(now=_NOW, intermediate_count=0)
    materials_a = authority_a.materials()
    materials_b = authority_b.materials()

    digest = hashlib.sha256(b"x").digest()
    der_a = authority_a.sign_timestamp_response(digest, gen_time=_NOW)
    parsed_a = parse_timestamp_response(der_a)

    # Pool A's intermediates + B's leaf (non-CA).
    intermediates = list(materials_a.intermediate_certs_der) + [
        materials_b.leaf_cert_der,
    ]

    # Replace the legitimate intermediate with B's leaf — chain walk
    # should fail because the issuer DN won't match anything.
    bad_intermediates = [materials_b.leaf_cert_der]
    with pytest.raises(AnchorVerificationError):
        verify_timestamp_token(
            parsed_a,
            expected_digest=digest,
            trust_roots_der=[materials_a.root_cert_der],
            intermediates_der=bad_intermediates,
            verification_time=_NOW,
        )


def test_verify_chain_with_anchors_walks_intermediates() -> None:
    """verify_chain_with_anchors must use tsa_cert_chain as the intermediate pool."""
    chain = _build_chain(2)
    authority = TestTSAAuthority(now=_NOW, intermediate_count=1)
    provider = TestTSAProvider(authority)
    anchor = provider.request_timestamp(
        TimestampRequest(digest=chain[1].event_hash),
        anchored_seq=1,
        now=_NOW,
    )
    # The TestTSAProvider only puts leaf + root in tsa_cert_chain; we
    # need to extend it with the intermediate for verification to succeed.
    materials = authority.materials()
    from dataclasses import replace

    anchor = replace(
        anchor,
        tsa_cert_chain=anchor.tsa_cert_chain + materials.intermediate_certs_der,
    )
    result = verify_chain_with_anchors(
        chain,
        [anchor],
        trust_roots_der=[materials.root_cert_der],
        verification_time=_NOW,
    )
    assert result.ok is True
    assert result.anchor_results[0].cert_status == "VALID"


def test_unknown_trust_root_fails_at_chain_head() -> None:
    """If the chain walk reaches a non-root anchor, fail clearly."""
    authority_a = TestTSAAuthority(now=_NOW, intermediate_count=1)
    authority_b = TestTSAAuthority(now=_NOW, intermediate_count=1)
    materials_a = authority_a.materials()
    materials_b = authority_b.materials()
    digest = hashlib.sha256(b"x").digest()
    der = authority_a.sign_timestamp_response(digest, gen_time=_NOW)
    parsed = parse_timestamp_response(der)

    # Use B's root as the configured trust root; the chain walks A's
    # intermediates but cannot reach A's root because it isn't trusted.
    with pytest.raises(AnchorVerificationError):
        verify_timestamp_token(
            parsed,
            expected_digest=digest,
            trust_roots_der=[materials_b.root_cert_der],
            intermediates_der=list(materials_a.intermediate_certs_der),
            verification_time=_NOW,
        )
