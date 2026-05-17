# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Settlement-precondition verifier predicate — read-only walker, NEVER settles.

ADR-0009 § B.3 + P2.3. Given a :class:`SettlementPreconditionClaim`
asserting "lease X was consumed before settlement Y was requested in
this chain", this module's :func:`check_settlement_precondition`
function walks the supplied chain and confirms (or rejects) the claim.

**Hard constraint** (per ADR-0009 § B.3 + invariant 7 + REDLINE C.3
+ C.8): this module NEVER executes settlement, NEVER allocates budget,
NEVER mutates state. It only walks the chain looking for an ordered
pair of observations (lease consumed, then settlement requested) and
returns a structured result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class SettlementPreconditionClaim:
    """A claim that the chain satisfies verify-before-settle.

    Mirrors schemas/v1/settlement_precondition_claim.schema.json.
    The verifier walks for:

    - A ``lease_lifecycle_event`` with payload.lifecycle == "consumed"
      and payload.lease_id_hash == self.lease_id_hash.
    - A ``settlement_event`` with payload.settlement_run_id ==
      self.settlement_run_id.
    - The lease-consumed event MUST have a strictly lower seq than the
      settlement_event.
    """

    claim_kind: str  # always "settlement_precondition" in v1
    lease_id_hash: str
    settlement_run_id: str
    expected_settlement_amount_hash: str | None = None
    claim_observed_at: str | None = None


@dataclass(frozen=True, slots=True)
class SettlementVerificationResult:
    """Outcome of :func:`check_settlement_precondition`.

    - ``ok=True``: both observations present and correctly ordered.
    - ``ok=False`` with reason:
      * "lease_consumed_not_observed"
      * "settlement_event_not_observed"
      * "settlement_precedes_lease_consumed" (ordering violation)
      * "claim_kind_unsupported"
      * "amount_hash_mismatch" (if claim provided expected_settlement_amount_hash
        and the settlement_event's amount_hash field differs)
    """

    ok: bool
    reason: str | None
    lease_consumed_seq: int | None
    settlement_event_seq: int | None


def check_settlement_precondition(
    chain_events: list[dict[str, Any]],
    claim: SettlementPreconditionClaim,
    *,
    verification_time: datetime | None = None,
) -> SettlementVerificationResult:
    """Verify the claim against the supplied chain. Read-only. Never settles.

    :param chain_events: list of event dicts. Each MUST contain
        ``seq``, ``event_type``, ``payload``. (This matches the
        JSONL backend's serialised form and ProofBundle's events array.)
    :param claim: the claim to verify.
    :param verification_time: reserved for future window checks; v1
        ignores. Must be UTC-aware if supplied (defensive check).
    """
    if claim.claim_kind != "settlement_precondition":
        return SettlementVerificationResult(
            ok=False,
            reason=f"claim_kind_unsupported: {claim.claim_kind!r}",
            lease_consumed_seq=None,
            settlement_event_seq=None,
        )
    if verification_time is not None and verification_time.tzinfo is None:
        return SettlementVerificationResult(
            ok=False,
            reason="verification_time must be UTC-aware",
            lease_consumed_seq=None,
            settlement_event_seq=None,
        )
    if not isinstance(chain_events, list):
        return SettlementVerificationResult(
            ok=False,
            reason=f"chain_events must be list, got {type(chain_events).__name__}",
            lease_consumed_seq=None,
            settlement_event_seq=None,
        )

    lease_consumed_seq: int | None = None
    settlement_event_seq: int | None = None
    settlement_amount_hash: str | None = None

    for ev in chain_events:
        if not isinstance(ev, dict):
            continue
        seq = ev.get("seq")
        if not isinstance(seq, int):
            continue
        event_type = ev.get("event_type")
        payload = ev.get("payload")
        if not isinstance(payload, dict):
            continue

        if event_type == "lease_lifecycle_event":
            if (
                payload.get("lifecycle") == "consumed"
                and payload.get("lease_id_hash") == claim.lease_id_hash
            ):
                if lease_consumed_seq is None or seq < lease_consumed_seq:
                    lease_consumed_seq = seq
        elif event_type == "settlement_event":
            if payload.get("settlement_run_id") == claim.settlement_run_id:
                if settlement_event_seq is None or seq < settlement_event_seq:
                    settlement_event_seq = seq
                    settlement_amount_hash = payload.get("amount_hash")

    if lease_consumed_seq is None:
        return SettlementVerificationResult(
            ok=False,
            reason="lease_consumed_not_observed",
            lease_consumed_seq=None,
            settlement_event_seq=settlement_event_seq,
        )
    if settlement_event_seq is None:
        return SettlementVerificationResult(
            ok=False,
            reason="settlement_event_not_observed",
            lease_consumed_seq=lease_consumed_seq,
            settlement_event_seq=None,
        )
    if lease_consumed_seq >= settlement_event_seq:
        return SettlementVerificationResult(
            ok=False,
            reason=(
                f"settlement_precedes_lease_consumed: "
                f"lease consumed at seq={lease_consumed_seq}, "
                f"settlement requested at seq={settlement_event_seq}"
            ),
            lease_consumed_seq=lease_consumed_seq,
            settlement_event_seq=settlement_event_seq,
        )
    if (
        claim.expected_settlement_amount_hash is not None
        and settlement_amount_hash is not None
        and settlement_amount_hash != claim.expected_settlement_amount_hash
    ):
        return SettlementVerificationResult(
            ok=False,
            reason=(
                f"amount_hash_mismatch: claim expected "
                f"{claim.expected_settlement_amount_hash}, settlement "
                f"event reports {settlement_amount_hash}"
            ),
            lease_consumed_seq=lease_consumed_seq,
            settlement_event_seq=settlement_event_seq,
        )

    return SettlementVerificationResult(
        ok=True,
        reason=None,
        lease_consumed_seq=lease_consumed_seq,
        settlement_event_seq=settlement_event_seq,
    )


__all__ = [
    "SettlementPreconditionClaim",
    "SettlementVerificationResult",
    "check_settlement_precondition",
]
