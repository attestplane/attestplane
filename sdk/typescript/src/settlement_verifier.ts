// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Settlement-precondition verifier predicate — read-only walker, NEVER settles.
 *
 * ADR-0009 § B.3 + P2.3. Walks the chain for an ordered pair of
 * observations: lease consumed → settlement requested (same lease &
 * settlement IDs). Returns yes/no/reason. NEVER executes settlement.
 *
 * **Hard constraint** (per ADR-0009 § B.3 + invariant 7 + REDLINE C.3
 * + C.8): no settlement execution, no budget allocation, no state
 * mutation. Pure function.
 */

export interface SettlementPreconditionClaim {
  readonly claim_kind: 'settlement_precondition' | string;
  readonly lease_id_hash: string;
  readonly settlement_run_id: string;
  readonly expected_settlement_amount_hash?: string;
  readonly claim_observed_at?: string;
}

export interface SettlementVerificationResult {
  readonly ok: boolean;
  readonly reason: string | null;
  readonly lease_consumed_seq: number | null;
  readonly settlement_event_seq: number | null;
}

/** Minimal chain-event shape this verifier needs. */
export interface ChainEventForSettlement {
  readonly seq: number;
  readonly event_type: string;
  readonly payload: Record<string, unknown>;
}

const HEX64 = /^[0-9a-f]{64}$/;

export function checkSettlementPrecondition(
  chainEvents: readonly ChainEventForSettlement[],
  claim: SettlementPreconditionClaim,
  options: { readonly verification_time?: Date } = {},
): SettlementVerificationResult {
  if (claim.claim_kind !== 'settlement_precondition') {
    return {
      ok: false,
      reason: `claim_kind_unsupported: ${JSON.stringify(claim.claim_kind)}`,
      lease_consumed_seq: null,
      settlement_event_seq: null,
    };
  }
  if (
    options.verification_time !== undefined &&
    Number.isNaN(options.verification_time.getTime())
  ) {
    return {
      ok: false,
      reason: 'verification_time must be a valid Date',
      lease_consumed_seq: null,
      settlement_event_seq: null,
    };
  }
  if (!Array.isArray(chainEvents)) {
    return {
      ok: false,
      reason: `chain_events must be array, got ${typeof chainEvents}`,
      lease_consumed_seq: null,
      settlement_event_seq: null,
    };
  }

  let leaseConsumedSeq: number | null = null;
  let settlementEventSeq: number | null = null;
  let settlementAmountHash: string | null = null;

  for (const ev of chainEvents) {
    if (ev === null || typeof ev !== 'object') continue;
    const seq = ev.seq;
    if (typeof seq !== 'number' || !Number.isInteger(seq)) continue;
    const payload = ev.payload;
    if (payload === null || typeof payload !== 'object') continue;

    if (ev.event_type === 'lease_lifecycle_event') {
      if (
        (payload as Record<string, unknown>).lifecycle === 'consumed' &&
        (payload as Record<string, unknown>).lease_id_hash === claim.lease_id_hash
      ) {
        if (leaseConsumedSeq === null || seq < leaseConsumedSeq) {
          leaseConsumedSeq = seq;
        }
      }
    } else if (ev.event_type === 'settlement_event') {
      if ((payload as Record<string, unknown>).settlement_run_id === claim.settlement_run_id) {
        if (settlementEventSeq === null || seq < settlementEventSeq) {
          settlementEventSeq = seq;
          settlementAmountHash =
            (typeof (payload as Record<string, unknown>).amount_hash === 'string'
              ? ((payload as Record<string, unknown>).amount_hash as string)
              : null) ?? null;
        }
      }
    }
  }

  if (leaseConsumedSeq === null) {
    return {
      ok: false,
      reason: 'lease_consumed_not_observed',
      lease_consumed_seq: null,
      settlement_event_seq: settlementEventSeq,
    };
  }
  if (settlementEventSeq === null) {
    return {
      ok: false,
      reason: 'settlement_event_not_observed',
      lease_consumed_seq: leaseConsumedSeq,
      settlement_event_seq: null,
    };
  }
  if (leaseConsumedSeq >= settlementEventSeq) {
    return {
      ok: false,
      reason: `settlement_precedes_lease_consumed: lease consumed at seq=${leaseConsumedSeq}, settlement requested at seq=${settlementEventSeq}`,
      lease_consumed_seq: leaseConsumedSeq,
      settlement_event_seq: settlementEventSeq,
    };
  }
  if (
    claim.expected_settlement_amount_hash !== undefined &&
    !HEX64.test(claim.expected_settlement_amount_hash)
  ) {
    return {
      ok: false,
      reason: 'expected_settlement_amount_hash_malformed',
      lease_consumed_seq: leaseConsumedSeq,
      settlement_event_seq: settlementEventSeq,
    };
  }
  if (claim.expected_settlement_amount_hash !== undefined) {
    if (settlementAmountHash === null) {
      return {
        ok: false,
        reason: 'amount_hash_missing',
        lease_consumed_seq: leaseConsumedSeq,
        settlement_event_seq: settlementEventSeq,
      };
    }
    if (!HEX64.test(settlementAmountHash)) {
      return {
        ok: false,
        reason: `amount_hash_malformed: settlement event reports ${JSON.stringify(settlementAmountHash)}`,
        lease_consumed_seq: leaseConsumedSeq,
        settlement_event_seq: settlementEventSeq,
      };
    }
    if (settlementAmountHash !== claim.expected_settlement_amount_hash) {
      return {
        ok: false,
        reason: `amount_hash_mismatch: claim expected ${claim.expected_settlement_amount_hash}, settlement event reports ${settlementAmountHash}`,
        lease_consumed_seq: leaseConsumedSeq,
        settlement_event_seq: settlementEventSeq,
      };
    }
  }

  return {
    ok: true,
    reason: null,
    lease_consumed_seq: leaseConsumedSeq,
    settlement_event_seq: settlementEventSeq,
  };
}
