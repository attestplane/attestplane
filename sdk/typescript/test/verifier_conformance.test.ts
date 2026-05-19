// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { chainExtend, genesisHead } from '../src/hashchain.js';
import { type ProofBundle, ProofBundleBuilder } from '../src/proof_bundle.js';
import { buildDeletionProof } from '../src/retention.js';
import { type ChainHead, type ChainedEvent, makeEventDraft } from '../src/types.js';
import { verifyProofBundle } from '../src/verifier.js';
import type { VerifyErrorCode } from '../src/verify_errors.js';

interface VectorCase {
  readonly case_id: string;
  readonly expected_error_code: VerifyErrorCode;
  readonly expected_ok: boolean;
}

const fixture = JSON.parse(
  readFileSync(
    join(
      process.cwd(),
      '..',
      'python',
      'tests',
      'conformance',
      'verifier_conformance_vectors.json',
    ),
    'utf-8',
  ),
) as { cases: VectorCase[] };

function baseBundle(): ProofBundle {
  const events: ChainedEvent[] = [];
  let head: ChainHead = genesisHead();
  for (let i = 0; i < 2; i++) {
    const ev = chainExtend(
      head,
      makeEventDraft({ actor: 'agent', event_type: 'eval_event', payload: { i } }),
      {
        event_id: `00000000-0000-7000-8000-${i.toString().padStart(12, '0')}`,
        now: new Date(`2026-05-19T00:00:00.00${i}Z`),
      },
    );
    events.push(ev);
    head = { event_hash: ev.event_hash, seq: ev.seq };
  }
  const builder = new ProofBundleBuilder({ chain_id: 'conf', producer_runtime: 'test' });
  builder.extend(events);
  return builder.build({ now: new Date('2026-05-19T00:00:00.000Z') });
}

function caseBundle(caseId: string): Record<string, unknown> {
  const bundle = JSON.parse(JSON.stringify(baseBundle())) as Record<string, unknown>;
  if (caseId === 'valid_minimal') return bundle;
  if (caseId === 'tampered_event_hash') {
    const events = bundle.events as Array<Record<string, unknown>>;
    const event0 = events[0]?.event as Record<string, unknown>;
    event0.payload = { i: 999 };
    return bundle;
  }
  if (caseId === 'dangling_policy_trace_ref') {
    bundle.policy_trace_refs = ['f'.repeat(64)];
    return bundle;
  }
  if (caseId === 'forged_deletion_proof') {
    const events = bundle.events as Array<Record<string, unknown>>;
    bundle.retention_proofs = [
      buildDeletionProof({
        commit_event_hash_hex: String(events[1]?.event_hash_hex),
        proof_id: 'forged',
        reason: 'forged',
        redacted_event_hash_hex: 'f'.repeat(64),
        target_event_hash_hex: String(events[0]?.event_hash_hex),
      }),
    ];
    return bundle;
  }
  throw new Error(`unknown caseId=${caseId}`);
}

describe('verifier conformance vectors', () => {
  for (const vector of fixture.cases) {
    it(vector.case_id, () => {
      const result = verifyProofBundle(caseBundle(vector.case_id));
      expect(result.ok).toBe(vector.expected_ok);
      expect(result.error_code).toBe(vector.expected_error_code);
    });
  }
});
