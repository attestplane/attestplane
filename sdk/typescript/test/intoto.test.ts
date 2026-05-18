// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';

import { chainExtend, genesisHead } from '../src/hashchain.js';
import {
  DSSE_PAYLOAD_TYPE,
  IntotoError,
  PREDICATE_TYPE_V1,
  STATEMENT_TYPE,
  canonicalJsonBytes,
  dsseEnvelopeToStatement,
  proofBundleToInTotoStatement,
  statementToDsseEnvelope,
} from '../src/intoto.js';
import { ProofBundleBuilder } from '../src/proof_bundle.js';
import { type ChainHead, makeEventDraft } from '../src/types.js';

function buildBundle(count = 2) {
  const builder = new ProofBundleBuilder({ chain_id: 'test-chain', producer_runtime: 'test' });
  let head: ChainHead = genesisHead();
  const events = [];
  for (let i = 0; i < count; i++) {
    const event = chainExtend(
      head,
      makeEventDraft({ event_type: 'eval_event', actor: `a${i}`, payload: { i } }),
      {
        now: new Date('2026-05-17T12:00:00.000Z'),
        event_id: `00000000-0000-7000-8000-${i.toString().padStart(12, '0')}`,
      },
    );
    events.push(event);
    head = { seq: event.seq, event_hash: event.event_hash };
  }
  builder.extend(events);
  return builder.build();
}

describe('in-toto / DSSE shape helpers', () => {
  it('builds an in-toto Statement v1 for a ProofBundle', () => {
    const bundle = buildBundle(3);
    const statement = proofBundleToInTotoStatement(bundle);
    expect(statement._type).toBe(STATEMENT_TYPE);
    expect(statement.predicateType).toBe(PREDICATE_TYPE_V1);
    expect(statement.subject).toEqual([
      {
        name: bundle.chain_metadata.chain_id,
        digest: { sha256: bundle.chain_metadata.head_hash_hex },
      },
    ]);
    expect(statement.predicate.events).toEqual(bundle.events);
  });

  it('round-trips through an unsigned DSSE envelope', () => {
    const statement = proofBundleToInTotoStatement(buildBundle());
    const envelope = statementToDsseEnvelope(statement);
    expect(envelope.payloadType).toBe(DSSE_PAYLOAD_TYPE);
    expect(envelope.signatures).toEqual([]);
    expect(dsseEnvelopeToStatement(envelope)).toEqual(statement);
  });

  it('preserves caller-supplied DSSE signatures without verifying them', () => {
    const statement = proofBundleToInTotoStatement(buildBundle());
    const signatures = [{ keyid: 'test-key', sig: 'AABB' }];
    const envelope = statementToDsseEnvelope(statement, { signatures });
    expect(envelope.signatures).toEqual(signatures);
  });

  it('emits deterministic canonical JSON bytes for DSSE payload', () => {
    const a = canonicalJsonBytes({ b: 1, a: 2 });
    const b = canonicalJsonBytes({ a: 2, b: 1 });
    expect(a).toEqual(b);
    expect(new TextDecoder().decode(a)).toBe('{"a":2,"b":1}');
  });

  it('rejects malformed envelopes', () => {
    expect(() =>
      dsseEnvelopeToStatement({
        payloadType: 'application/wrong' as typeof DSSE_PAYLOAD_TYPE,
        payload: 'AA==',
        signatures: [],
      }),
    ).toThrow(IntotoError);
    expect(() =>
      dsseEnvelopeToStatement({
        payloadType: DSSE_PAYLOAD_TYPE,
        payload: '***not base64***',
        signatures: [],
      }),
    ).toThrow(IntotoError);
  });
});
