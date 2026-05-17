// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Settlement-precondition verifier tests (ADR-0009 § B.3 + P2.3).
 * Replays sdk/python/tests/conformance/settlement_precondition_vectors.json.
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  type SettlementPreconditionClaim,
  checkSettlementPrecondition,
} from '../src/settlement_verifier.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const VECTORS_PATH = resolve(
  __dirname,
  '..',
  '..',
  'python',
  'tests',
  'conformance',
  'settlement_precondition_vectors.json',
);

interface VerifierVector {
  name: string;
  description?: string;
  chain: { seq: number; event_type: string; payload: Record<string, unknown> }[];
  claim: {
    claim_kind: string;
    lease_id_hash: string;
    settlement_run_id: string;
    expected_settlement_amount_hash?: string;
  };
  expected: {
    ok: boolean;
    reason?: string | null;
    reason_contains?: string;
    lease_consumed_seq: number | null;
    settlement_event_seq: number | null;
  };
}

interface VectorsFile {
  $schema_version: number;
  verifier_vectors: VerifierVector[];
}

const VECTORS: VectorsFile = JSON.parse(readFileSync(VECTORS_PATH, 'utf-8')) as VectorsFile;

describe('checkSettlementPrecondition — ADR-0009 § B.3 / P2.3', () => {
  it('vectors file loads', () => {
    expect(VECTORS.$schema_version).toBe(1);
    expect(VECTORS.verifier_vectors.length).toBe(8);
  });

  for (const vec of VECTORS.verifier_vectors) {
    it(`verifier vector: ${vec.name}`, () => {
      const claim: SettlementPreconditionClaim = {
        claim_kind: vec.claim.claim_kind,
        lease_id_hash: vec.claim.lease_id_hash,
        settlement_run_id: vec.claim.settlement_run_id,
        ...(vec.claim.expected_settlement_amount_hash !== undefined
          ? { expected_settlement_amount_hash: vec.claim.expected_settlement_amount_hash }
          : {}),
      };
      const result = checkSettlementPrecondition(vec.chain, claim);

      expect(result.ok).toBe(vec.expected.ok);
      expect(result.lease_consumed_seq).toBe(vec.expected.lease_consumed_seq);
      expect(result.settlement_event_seq).toBe(vec.expected.settlement_event_seq);
      if (vec.expected.ok) {
        expect(result.reason).toBeNull();
      } else if (vec.expected.reason_contains) {
        expect(result.reason).toMatch(new RegExp(vec.expected.reason_contains));
      }
    });
  }

  it('is pure (same input → same output)', () => {
    const chain = [
      {
        seq: 0,
        event_type: 'lease_lifecycle_event',
        payload: { lifecycle: 'consumed', lease_id_hash: 'a'.repeat(64) },
      },
      { seq: 1, event_type: 'settlement_event', payload: { settlement_run_id: 's' } },
    ];
    const claim: SettlementPreconditionClaim = {
      claim_kind: 'settlement_precondition',
      lease_id_hash: 'a'.repeat(64),
      settlement_run_id: 's',
    };
    const r1 = checkSettlementPrecondition(chain, claim);
    const r2 = checkSettlementPrecondition(chain, claim);
    expect(r1).toEqual(r2);
    expect(r1.ok).toBe(true);
  });

  it('handles malformed chain', () => {
    const result = checkSettlementPrecondition(
      'not an array' as unknown as Parameters<typeof checkSettlementPrecondition>[0],
      {
        claim_kind: 'settlement_precondition',
        lease_id_hash: '0'.repeat(64),
        settlement_run_id: 'x',
      },
    );
    expect(result.ok).toBe(false);
    expect(result.reason).toMatch(/must be array/);
  });

  it('rejects invalid verification_time', () => {
    const result = checkSettlementPrecondition(
      [],
      {
        claim_kind: 'settlement_precondition',
        lease_id_hash: '0'.repeat(64),
        settlement_run_id: 'x',
      },
      { verification_time: new Date('not a date') },
    );
    expect(result.ok).toBe(false);
    expect(result.reason).toMatch(/valid Date/);
  });
});
