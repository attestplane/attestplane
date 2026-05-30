// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';

import { chainExtend, genesisHead } from '../src/hashchain.js';
import { ProofBundleBuilder } from '../src/proof_bundle.js';
import { buildDeletionProof } from '../src/retention.js';
import { type ChainedEvent, type ChainHead, makeEventDraft } from '../src/types.js';
import { verifyProofBundle } from '../src/verifier.js';

function chain(): ChainedEvent[] {
  const out: ChainedEvent[] = [];
  let head: ChainHead = genesisHead();
  for (let i = 0; i < 3; i++) {
    const ev = chainExtend(
      head,
      makeEventDraft({
        actor: 'controller',
        event_type: i === 2 ? 'deletion_marker_event' : 'eval_event',
        payload: { i },
      }),
      {
        event_id: `00000000-0000-7000-8000-${i.toString().padStart(12, '0')}`,
        now: new Date(`2026-05-19T00:00:00.00${i}Z`),
      },
    );
    out.push(ev);
    head = { event_hash: ev.event_hash, seq: ev.seq };
  }
  return out;
}

describe('retention proofs', () => {
  it('accepts commit-then-redact markers that reference bundle events', () => {
    const events = chain();
    const builder = new ProofBundleBuilder({ chain_id: 'retention', producer_runtime: 'test' });
    builder.extend(events);
    builder.extendRetentionProofs([
      buildDeletionProof({
        commit_event_hash_hex: Buffer.from(events[1]?.event_hash ?? new Uint8Array()).toString(
          'hex',
        ),
        proof_id: 'proof-1',
        reason: 'controller_policy_redaction',
        redacted_event_hash_hex: Buffer.from(events[2]?.event_hash ?? new Uint8Array()).toString(
          'hex',
        ),
        target_event_hash_hex: Buffer.from(events[0]?.event_hash ?? new Uint8Array()).toString(
          'hex',
        ),
      }),
    ]);

    const result = verifyProofBundle(builder.build({ now: new Date('2026-05-19T00:00:00.000Z') }));

    expect(result.ok).toBe(true);
    expect(result.retention_proofs_ok).toBe(true);
    expect(result.error_code).toBe('VERIFY_OK');
  });

  it('fails closed on dangling retention refs', () => {
    const events = chain();
    const builder = new ProofBundleBuilder({ chain_id: 'retention', producer_runtime: 'test' });
    builder.extend(events);
    builder.extendRetentionProofs([
      buildDeletionProof({
        commit_event_hash_hex: Buffer.from(events[1]?.event_hash ?? new Uint8Array()).toString(
          'hex',
        ),
        proof_id: 'proof-1',
        reason: 'controller_policy_redaction',
        redacted_event_hash_hex: 'f'.repeat(64),
        target_event_hash_hex: Buffer.from(events[0]?.event_hash ?? new Uint8Array()).toString(
          'hex',
        ),
      }),
    ]);

    const result = verifyProofBundle(builder.build({ now: new Date('2026-05-19T00:00:00.000Z') }));

    expect(result.ok).toBe(false);
    expect(result.retention_proofs_ok).toBe(false);
    expect(result.error_code).toBe('VERIFY_RETENTION_PROOF_FAILED');
  });
});
