# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Verifier extension — T4 of the ADR-0005 plan per the
:doc:`T3+T4 architect review </architecture/adr_0005_t3_t4_review_20260517>`.

Adds two functions alongside the existing
:func:`~attestplane.anchoring.verify_chain_with_anchors`:

- :func:`verify_chain_with_signatures` — signature-only path.
- :func:`verify_chain_full` — unified chain + signature + anchor.

Pipeline ordering (review § 1 decision 8): chain → signature → anchor.
Each step always runs (no short-circuit) for forensic completeness.

``BundleVerificationResult`` carries four new fields per review § 1
decision 11: ``signature_status``, ``signature_results``,
``signed_segment_count``, ``first_bad_signature_index``. The ``ok``
property does NOT include signature status; callers requiring
fail-closed semantics check ``signature_status == "valid"`` themselves.

Plurality priority (review § 1 decision 10):
``valid > expired_key > invalid > unknown_key > unsigned``. Any single
``valid`` signature for a seq lifts that seq to ``valid``.

Coverage (review § 1 decision 12, option a): a ``valid`` segment-head
signature at seq=N covers seqs {previous-signed-head + 1 .. N} via
chain-integrity transitivity. Per-event signatures cover their
explicit ``signed_seq`` only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attestplane.signing.verifier_ext requires the 'signing' extras. Install with: pip install attestplane[signing]"
    ) from exc

from attestplane.anchoring.base import AnchorRecord
from attestplane.anchoring.verifier import (
    AnchorVerificationResult,
    SingleAnchorResult,
    verify_chain_with_anchors,
)
from attestplane.signing.base import (
    SIGNATURE_SCHEMA_VERSION,
    SignatureRecord,
    SigningError,
    derive_key_id,
)
from attestplane.signing.signer import (
    _build_per_event_payload,
    _build_segment_head_payload,
)
from attestplane.signing.trust_roots import TrustRootEntry, TrustRoots
from attestplane.types import ChainedEvent, ChainHead

SignatureStatus = Literal[
    "unsigned",
    "valid",
    "invalid",
    "unknown_key",
    "expired_key",
]
"""Per architect review § 1 decision 10 — the locked 5-value enum."""


# Plurality priority (lower index = better). Used to merge multiple
# signatures covering the same seq into a single per-seq status.
_STATUS_RANK: dict[SignatureStatus, int] = {
    "valid": 0,
    "expired_key": 1,
    "invalid": 2,
    "unknown_key": 3,
    "unsigned": 4,
}


@dataclass(frozen=True, slots=True)
class SingleSignatureResult:
    """One row in the per-record signature-verification report."""

    record_index: int
    signed_seq: int
    key_id: str
    status: SignatureStatus
    reason: str | None


@dataclass(frozen=True, slots=True)
class BundleVerificationResult:
    """Aggregate outcome of :func:`verify_chain_full`."""

    chain_ok: bool
    chain_reason: str | None
    anchored_seqs: frozenset[int]
    unanchored_seqs: frozenset[int]
    anchor_results: tuple[SingleAnchorResult, ...]
    signature_status: SignatureStatus
    signature_results: tuple[SingleSignatureResult, ...]
    signed_segment_count: int
    first_bad_signature_index: int | None

    @property
    def ok(self) -> bool:
        """``True`` iff chain integrity + every anchor verify.

        Signature status is deliberately NOT included per architect
        review § 1 decision 11. Callers wanting fail-closed signature
        semantics check ``signature_status == "valid"`` separately.
        """
        return self.chain_ok and all(a.valid for a in self.anchor_results)


def _verify_single_signature(
    record: SignatureRecord,
    *,
    index: int,
    events_by_seq: dict[int, ChainedEvent],
    chain_id: str,
    trust_roots: TrustRoots,
    verification_time: datetime,
) -> SingleSignatureResult:
    # 1. Schema version.
    if record.signature_schema_version != SIGNATURE_SCHEMA_VERSION:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="invalid",
            reason=(
                f"signature_schema_version={record.signature_schema_version!r} "
                f"unsupported (expected {SIGNATURE_SCHEMA_VERSION})"
            ),
        )

    # Defense-in-depth (post_init also enforces this).
    if not record.signed_payload:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="invalid",
            reason="signed_payload is empty",
        )

    # 2. Self-consistency: key_id derives from public_key_der.
    derived = derive_key_id(record.public_key_der)
    if derived != record.key_id:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="invalid",
            reason=(f"record.key_id ({record.key_id}) does not derive from public_key_der (got {derived})"),
        )

    # 3. TrustRoots lookup.
    entry: TrustRootEntry | None = trust_roots.lookup(record.key_id)
    if entry is None:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="unknown_key",
            reason=f"key_id {record.key_id!r} not in trust roots",
        )

    # 4. Validity window. valid_from <= verification_time <= valid_until.
    if verification_time < entry.valid_from:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="expired_key",
            reason=(
                f"verification_time {verification_time.isoformat()} precedes valid_from {entry.valid_from.isoformat()}"
            ),
        )
    if verification_time > entry.valid_until:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="expired_key",
            reason=(
                f"verification_time {verification_time.isoformat()} exceeds valid_until {entry.valid_until.isoformat()}"
            ),
        )

    # 5. Ed25519 signature verification against public_key_der.
    try:
        pubkey = serialization.load_der_public_key(record.public_key_der)
    except Exception as exc:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="invalid",
            reason=f"public_key_der not parseable: {exc}",
        )
    if not isinstance(pubkey, Ed25519PublicKey):
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="invalid",
            reason=(f"v1 supports Ed25519 keys only; got {type(pubkey).__name__}"),
        )
    # Also cross-check that the trust-root pubkey matches what's stored.
    if entry.public_key_der != record.public_key_der:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="invalid",
            reason=(
                "record.public_key_der does not match trust-root entry's "
                "public_key_der (same key_id, different bytes — tamper signal)"
            ),
        )

    try:
        pubkey.verify(record.signature, record.signed_payload)
    except InvalidSignature as exc:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="invalid",
            reason=f"Ed25519 verify failed: {exc}",
        )

    # 6. Payload semantics cross-check.
    target = events_by_seq.get(record.signed_seq)
    if target is None:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="invalid",
            reason=f"signed_seq={record.signed_seq} not in chain",
        )
    if target.event_hash != record.signed_event_hash:
        return SingleSignatureResult(
            record_index=index,
            signed_seq=record.signed_seq,
            key_id=record.key_id,
            status="invalid",
            reason=(f"signed_event_hash mismatch at seq={record.signed_seq}"),
        )

    # Reconstruct the expected canonical bytes for this mode.
    if record.signature_mode == "segment_head":
        expected = _build_segment_head_payload(
            chain_id,
            ChainHead(seq=target.seq, event_hash=target.event_hash),
        )
        if expected != record.signed_payload:
            # Surface the chain_id mismatch case (R2 footgun).
            try:
                import json

                payload_obj = json.loads(record.signed_payload)
                payload_chain_id = payload_obj.get("chain_id")
            except Exception:
                payload_chain_id = "<unparsable>"
            return SingleSignatureResult(
                record_index=index,
                signed_seq=record.signed_seq,
                key_id=record.key_id,
                status="invalid",
                reason=(
                    f"signed_payload does not match expected canonical bytes "
                    f"for segment_head at seq={record.signed_seq}; "
                    f"payload chain_id={payload_chain_id!r}, "
                    f"verifier chain_id={chain_id!r}"
                ),
            )
    elif record.signature_mode == "per_event":
        expected = _build_per_event_payload(target.event)
        if expected != record.signed_payload:
            return SingleSignatureResult(
                record_index=index,
                signed_seq=record.signed_seq,
                key_id=record.key_id,
                status="invalid",
                reason=(f"signed_payload does not match canonicalize(event) for per_event at seq={record.signed_seq}"),
            )
    # signature_mode is a Literal type validated at post_init; the
    # else branch above is unreachable in practice. Type-checker
    # treats Literal["segment_head", "per_event"] as exhaustive.

    return SingleSignatureResult(
        record_index=index,
        signed_seq=record.signed_seq,
        key_id=record.key_id,
        status="valid",
        reason=None,
    )


def _merge_status_at_seq(per_seq: dict[int, list[SignatureStatus]]) -> dict[int, SignatureStatus]:
    """Apply plurality priority per architect review § 1 decision 10."""
    result: dict[int, SignatureStatus] = {}
    for seq, statuses in per_seq.items():
        best = min(statuses, key=lambda s: _STATUS_RANK[s])
        result[seq] = best
    return result


def _compute_signed_segment_count(
    events: list[ChainedEvent],
    per_seq_status: dict[int, SignatureStatus],
    per_seq_modes: dict[int, set[Literal["segment_head", "per_event"]]],
) -> int:
    """Apply coverage transitivity per architect review § 1 decision 12 (option a).

    A ``valid`` segment-head signature at seq=N covers seqs
    {previous_signed_head + 1 .. N}. Per-event signatures cover only
    ``signed_seq``.
    """
    # Sort valid segment-head seqs ascending.
    valid_segment_heads = sorted(
        seq
        for seq, status in per_seq_status.items()
        if status == "valid" and "segment_head" in per_seq_modes.get(seq, set())
    )
    valid_per_events = {
        seq
        for seq, status in per_seq_status.items()
        if status == "valid" and "per_event" in per_seq_modes.get(seq, set())
    }

    covered_seqs: set[int] = set(valid_per_events)
    prev_head = -1
    for head_seq in valid_segment_heads:
        for s in range(prev_head + 1, head_seq + 1):
            covered_seqs.add(s)
        prev_head = head_seq

    # Restrict to actually-present chain seqs.
    chain_seqs = {ev.seq for ev in events}
    return len(covered_seqs & chain_seqs)


def verify_chain_with_signatures(
    events: list[ChainedEvent],
    signatures: list[SignatureRecord],
    *,
    chain_id: str,
    trust_roots: TrustRoots,
    verification_time: datetime | None = None,
) -> tuple[
    SignatureStatus,
    tuple[SingleSignatureResult, ...],
    int,
    int | None,
]:
    """Verify a chain's signatures against trust roots.

    Returns ``(signature_status, signature_results, signed_segment_count,
    first_bad_signature_index)``.

    :param chain_id: substrate identifier for segment-head payload
        reconstruction. MUST match the value the Signer was configured
        with; mismatch surfaces as an "invalid" result with the
        offending chain_id in the reason for diagnostic clarity.
    :param trust_roots: loaded via :func:`load_trust_roots`.
    :param verification_time: defaults to "now" (UTC).
    """
    if not chain_id:
        raise SigningError("verify_chain_with_signatures requires non-empty chain_id")
    actual_when = verification_time if verification_time is not None else datetime.now(UTC)
    if actual_when.tzinfo is None:
        raise SigningError("verify_chain_with_signatures requires UTC-aware verification_time")

    events_by_seq = {ev.seq: ev for ev in events}

    results: list[SingleSignatureResult] = []
    per_seq_statuses: dict[int, list[SignatureStatus]] = {}
    per_seq_modes: dict[int, set[Literal["segment_head", "per_event"]]] = {}
    for i, rec in enumerate(signatures):
        result = _verify_single_signature(
            rec,
            index=i,
            events_by_seq=events_by_seq,
            chain_id=chain_id,
            trust_roots=trust_roots,
            verification_time=actual_when,
        )
        results.append(result)
        per_seq_statuses.setdefault(rec.signed_seq, []).append(result.status)
        per_seq_modes.setdefault(rec.signed_seq, set()).add(rec.signature_mode)

    per_seq_status = _merge_status_at_seq(per_seq_statuses)

    if not signatures:
        signature_status: SignatureStatus = "unsigned"
    else:
        # Bundle-level = worst (highest rank) status across signed seqs.
        signature_status = max(per_seq_status.values(), key=lambda s: _STATUS_RANK[s])

    signed_segment_count = _compute_signed_segment_count(
        events,
        per_seq_status,
        per_seq_modes,
    )

    first_bad_idx: int | None = None
    for r in results:
        if r.status != "valid":
            first_bad_idx = r.record_index
            break

    return (
        signature_status,
        tuple(results),
        signed_segment_count,
        first_bad_idx,
    )


def verify_chain_full(
    events: list[ChainedEvent],
    *,
    anchors: list[AnchorRecord] | None = None,
    signatures: list[SignatureRecord] | None = None,
    chain_id: str | None = None,
    trust_roots: TrustRoots | None = None,
    trust_roots_der: list[bytes] | None = None,
    verification_time: datetime | None = None,
    verify_ocsp: bool = True,
) -> BundleVerificationResult:
    """Unified verifier: chain → signature → anchor (always all three).

    Mirrors :func:`~attestplane.anchoring.verify_chain_with_anchors` API
    but adds signature verification.

    :param events: the chain to verify.
    :param anchors: optional anchor records.
    :param signatures: optional signature records.
    :param chain_id: required when ``signatures`` is non-empty.
    :param trust_roots: required when ``signatures`` is non-empty.
    :param trust_roots_der: passthrough to anchor verifier.
    :param verification_time: applies to both signatures + anchors.
    :param verify_ocsp: passthrough to anchor verifier.
    """
    anchors = anchors or []
    signatures = signatures or []

    # Anchor verification (always run; never short-circuited by signature failure).
    anchor_result: AnchorVerificationResult = verify_chain_with_anchors(
        events,
        anchors,
        trust_roots_der=trust_roots_der,
        verification_time=verification_time,
        verify_ocsp=verify_ocsp,
    )

    # Signature verification.
    if signatures:
        if chain_id is None or trust_roots is None:
            raise SigningError("verify_chain_full: signatures provided but chain_id or trust_roots is None")
        sig_status, sig_results, signed_count, first_bad = verify_chain_with_signatures(
            events,
            signatures,
            chain_id=chain_id,
            trust_roots=trust_roots,
            verification_time=verification_time,
        )
    else:
        sig_status = "unsigned"
        sig_results = ()
        signed_count = 0
        first_bad = None

    return BundleVerificationResult(
        chain_ok=anchor_result.chain_ok,
        chain_reason=anchor_result.chain_reason,
        anchored_seqs=anchor_result.anchored_seqs,
        unanchored_seqs=anchor_result.unanchored_seqs,
        anchor_results=anchor_result.anchor_results,
        signature_status=sig_status,
        signature_results=sig_results,
        signed_segment_count=signed_count,
        first_bad_signature_index=first_bad,
    )


__all__ = [
    "BundleVerificationResult",
    "SignatureStatus",
    "SingleSignatureResult",
    "verify_chain_full",
    "verify_chain_with_signatures",
]
