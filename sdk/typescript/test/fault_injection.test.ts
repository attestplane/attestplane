// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Deterministic fail-closed fault-injection tests.
 *
 * These tests lock high-risk mutation cases from
 * tests/fault_injection/fault_matrix_v1.json. They are not a mutation
 * engine and do not claim formal verification.
 */

import { describe, expect, it } from 'vitest';

import {
  ANCHOR_SCHEMA_VERSION,
  type AnchorRecord,
  verifyChainWithAnchors,
} from '../src/anchoring.js';
import { CanonicalizationError, canonicalize } from '../src/canonical.js';
import {
  type LeaseLifecycleEventPayload,
  validateLeaseLifecycleEventPayload,
} from '../src/event_payloads.js';
import { chainExtend, genesisHead, verifyChain } from '../src/hashchain.js';
import { ProofBundleBuilder } from '../src/proof_bundle.js';
import { isKnownReasonCode, reasonCodeMatchesFormat } from '../src/reason_codes.js';
import {
  type SettlementPreconditionClaim,
  checkSettlementPrecondition,
} from '../src/settlement_verifier.js';
import { type ChainedEvent, type ChainHead, makeEventDraft } from '../src/types.js';
import { BundleSchemaError, verifyProofBundle } from '../src/verifier.js';

const NOW = new Date('2026-05-17T12:00:00.000Z');

function buildChain(count: number, eventType = 'eval_event'): ChainedEvent[] {
  const chain: ChainedEvent[] = [];
  let head: ChainHead = genesisHead();
  for (let i = 0; i < count; i++) {
    const event = chainExtend(
      head,
      makeEventDraft({ event_type: eventType, actor: 'agent://fault', payload: { i } }),
      {
        now: new Date(NOW.getTime() + i),
        event_id: `00000000-0000-7000-8000-${i.toString().padStart(12, '0')}`,
      },
    );
    chain.push(event);
    head = { seq: event.seq, event_hash: event.event_hash };
  }
  return chain;
}

function bundleForPolicyEvents(): Record<string, unknown> {
  const builder = new ProofBundleBuilder({
    chain_id: 'fault-policy',
    producer_runtime: 'fault-test',
  });
  builder.extend(buildChain(1, 'policy_check_event'));
  return JSON.parse(JSON.stringify(builder.build({ now: NOW }))) as Record<string, unknown>;
}

describe('fault matrix / canonical', () => {
  const rejectCases: Array<readonly [string, () => unknown]> = [
    ['canonical.reject_nan', () => canonicalize(Number.NaN)],
    ['canonical.reject_infinity', () => canonicalize(Number.POSITIVE_INFINITY)],
    ['canonical.reject_undefined_top_level', () => canonicalize(undefined)],
    ['canonical.reject_undefined_object_value', () => canonicalize({ a: undefined })],
    [
      'canonical.reject_sparse_array_hole',
      () => {
        const sparse = new Array<number>(3);
        sparse[0] = 1;
        sparse[2] = 3;
        return canonicalize(sparse);
      },
    ],
    ['canonical.reject_unsafe_integer', () => canonicalize(Number.MAX_SAFE_INTEGER + 1)],
    ['canonical.reject_lone_surrogate', () => canonicalize('\ud800')],
    ['canonical.reject_date_object', () => canonicalize(new Date())],
  ];

  for (const [faultId, run] of rejectCases) {
    it(`${faultId} fails closed`, () => {
      expect(run).toThrow(CanonicalizationError);
    });
  }

  it('canonical.key_ordering_changed remains deterministic', () => {
    const left = canonicalize({ z: 1, a: 2, m: { b: 1, a: 2 } });
    const right = canonicalize({ m: { a: 2, b: 1 }, a: 2, z: 1 });
    expect(left).toEqual(right);
  });

  it('canonical.negative_zero_behavior_drift remains canonical zero', () => {
    expect(new TextDecoder().decode(canonicalize(-0))).toBe('0');
  });
});

describe('fault matrix / hashchain', () => {
  const cases = [
    'hashchain.previous_hash_tampered',
    'hashchain.event_hash_tampered',
    'hashchain.payload_tampered_after_chaining',
    'hashchain.reordered_events',
    'hashchain.missing_chain_link',
    'hashchain.duplicate_chain_index',
  ];

  for (const faultId of cases) {
    it(`${faultId} fails closed`, () => {
      let chain = buildChain(3);
      if (faultId === 'hashchain.previous_hash_tampered') {
        chain[1] = { ...(chain[1] as ChainedEvent), prev_hash: new Uint8Array(32).fill(0xff) };
      } else if (faultId === 'hashchain.event_hash_tampered') {
        chain[1] = { ...(chain[1] as ChainedEvent), event_hash: new Uint8Array(32).fill(0x01) };
      } else if (faultId === 'hashchain.payload_tampered_after_chaining') {
        const original = chain[1] as ChainedEvent;
        chain[1] = { ...original, event: { ...original.event, payload: { i: 999 } } };
      } else if (faultId === 'hashchain.reordered_events') {
        chain = [chain[0] as ChainedEvent, chain[2] as ChainedEvent, chain[1] as ChainedEvent];
      } else if (faultId === 'hashchain.missing_chain_link') {
        chain = [chain[0] as ChainedEvent, chain[2] as ChainedEvent];
      } else if (faultId === 'hashchain.duplicate_chain_index') {
        chain = [chain[0] as ChainedEvent, chain[1] as ChainedEvent, chain[1] as ChainedEvent];
      }
      expect(verifyChain(chain).ok).toBe(false);
    });
  }
});

describe('fault matrix / payload and reason codes', () => {
  const validPayload: LeaseLifecycleEventPayload = {
    lease_event_schema_version: 1,
    lease_id_hash: 'a'.repeat(64),
    lifecycle: 'consumed',
    observed_at: '2026-05-17T12:00:00Z',
  };
  const cases: Array<readonly [string, Record<string, unknown>]> = [
    ['payload.missing_schema_version', {}],
    ['payload.unsupported_schema_version', { ...validPayload, lease_event_schema_version: 2 }],
    ['payload.unknown_top_level_field', { ...validPayload, unexpected: 'x' }],
    ['payload.forbidden_field', { ...validPayload, token: 'secret' }],
    ['payload.null_required_field', { ...validPayload, lease_id_hash: null }],
    ['payload.unknown_enum', { ...validPayload, lifecycle: 'settled' }],
  ];

  for (const [faultId, payload] of cases) {
    it(`${faultId} fails closed`, () => {
      expect(() => validateLeaseLifecycleEventPayload(payload)).toThrow();
    });
  }

  it('payload.invalid_reason_code_format fails closed', () => {
    expect(() =>
      validateLeaseLifecycleEventPayload({ ...validPayload, reason_code: 'bad-code' }),
    ).toThrow();
    expect(reasonCodeMatchesFormat('bad-code')).toBe(false);
  });

  it('payload.unknown_reason_code is not a known v1 verifier reason', () => {
    expect(isKnownReasonCode('NOT_A_V1_REASON_CODE')).toBe(false);
  });
});

describe('fault matrix / proof bundle', () => {
  const cases = [
    'proof_bundle.unsupported_proof_type',
    'proof_bundle.missing_required_metadata',
    'proof_bundle.unknown_critical_metadata',
    'proof_bundle.embedded_report_mismatch',
    'proof_bundle.chain_head_mismatch',
    'proof_bundle.dangling_policy_trace_ref',
    'proof_bundle.policy_trace_ref_hash_mismatch',
    'proof_bundle.duplicate_policy_trace_ref',
  ];

  for (const faultId of cases) {
    it(`${faultId} fails closed`, () => {
      const bundle = bundleForPolicyEvents();
      if (faultId === 'proof_bundle.unsupported_proof_type') {
        (bundle.verification_report as Record<string, unknown>).verification_method =
          'full-production-verifier';
        expect(() => verifyProofBundle(bundle)).toThrow(BundleSchemaError);
        return;
      }
      if (faultId === 'proof_bundle.missing_required_metadata') {
        const metadata = bundle.chain_metadata as Record<string, unknown>;
        bundle.chain_metadata = Object.fromEntries(
          Object.entries(metadata).filter(([key]) => key !== 'head_hash_hex'),
        );
        expect(() => verifyProofBundle(bundle)).toThrow(BundleSchemaError);
        return;
      }
      if (faultId === 'proof_bundle.unknown_critical_metadata') {
        bundle.critical_extension = { must_understand: true };
        expect(() => verifyProofBundle(bundle)).toThrow(BundleSchemaError);
        return;
      }
      if (faultId === 'proof_bundle.embedded_report_mismatch') {
        (bundle.verification_report as Record<string, unknown>).reason = 'forged';
      } else if (faultId === 'proof_bundle.chain_head_mismatch') {
        (bundle.chain_metadata as Record<string, unknown>).head_hash_hex = 'f'.repeat(64);
      } else if (
        faultId === 'proof_bundle.dangling_policy_trace_ref' ||
        faultId === 'proof_bundle.policy_trace_ref_hash_mismatch'
      ) {
        bundle.policy_trace_refs = ['a'.repeat(64)];
      } else if (faultId === 'proof_bundle.duplicate_policy_trace_ref') {
        const refs = bundle.policy_trace_refs as string[];
        bundle.policy_trace_refs = [refs[0], refs[0]];
      }
      expect(verifyProofBundle(bundle).ok).toBe(false);
    });
  }
});

describe('fault matrix / settlement and anchors', () => {
  const amountCases: Array<readonly [string, string | null]> = [
    ['settlement.missing_amount_hash', null],
    ['settlement.empty_amount_hash', ''],
    ['settlement.wrong_format_amount_hash', 'not-a-hash'],
    ['settlement.amount_hash_mismatch', 'b'.repeat(64)],
  ];

  for (const [faultId, amountHash] of amountCases) {
    it(`${faultId} fails closed`, () => {
      const payload: Record<string, unknown> = { settlement_run_id: 's' };
      if (amountHash !== null) payload.amount_hash = amountHash;
      const claim: SettlementPreconditionClaim = {
        claim_kind: 'settlement_precondition',
        lease_id_hash: 'a'.repeat(64),
        settlement_run_id: 's',
        expected_settlement_amount_hash: 'c'.repeat(64),
      };
      const result = checkSettlementPrecondition(
        [
          {
            seq: 0,
            event_type: 'lease_lifecycle_event',
            payload: { lifecycle: 'consumed', lease_id_hash: 'a'.repeat(64) },
          },
          { seq: 1, event_type: 'settlement_event', payload },
        ],
        claim,
      );
      expect(result.ok).toBe(false);
    });
  }

  it('settlement.accepted_without_precondition fails closed', () => {
    const result = checkSettlementPrecondition(
      [{ seq: 0, event_type: 'settlement_event', payload: { settlement_run_id: 's' } }],
      {
        claim_kind: 'settlement_precondition',
        lease_id_hash: 'a'.repeat(64),
        settlement_run_id: 's',
      },
    );
    expect(result.ok).toBe(false);
  });

  it('anchoring.empty_anchor_treated_as_success fails closed', () => {
    const result = verifyChainWithAnchors(buildChain(1), []);
    expect(result.ok).toBe(false);
    expect(result.verification_status).toBe('not_performed');
  });

  it('anchoring.malformed_anchor_evidence_accepted fails closed', () => {
    const chain = buildChain(1);
    const bad: AnchorRecord = {
      anchor_schema_version: ANCHOR_SCHEMA_VERSION,
      anchored_seq: 0,
      anchored_event_hash: new Uint8Array(32).fill(0xff),
      tsa_provider_id: 'mock.tsa.local',
      tsa_token: new Uint8Array(1),
      tsa_cert_chain: [new Uint8Array(1)],
      ocsp_responses: [new Uint8Array(1)],
      issued_at_claimed: NOW,
    };
    expect(verifyChainWithAnchors(chain, [bad]).ok).toBe(false);
  });
});
