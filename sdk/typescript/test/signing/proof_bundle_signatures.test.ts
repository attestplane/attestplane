// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';

import { chainExtend, genesisHead } from '../../src/hashchain.js';
import {
  ProofBundleBuilder,
  deserializeSignatureRecord,
  serializeSignatureRecord,
} from '../../src/proof_bundle.js';
import { InMemoryKeyProvider } from '../../src/signing/providers.js';
import { Signer } from '../../src/signing/signer.js';
import { type ChainHead, type ChainedEvent, makeEventDraft } from '../../src/types.js';

const NOW = new Date('2026-05-17T12:00:00Z');

function buildChain(): ChainedEvent[] {
  const out: ChainedEvent[] = [];
  let head: ChainHead = genesisHead();
  for (let i = 0; i < 3; i++) {
    const ev = chainExtend(
      head,
      makeEventDraft({ event_type: 'eval_event', actor: `a${i}`, payload: { i } }),
      {
        now: NOW,
        event_id: `00000000-0000-7000-8000-${i.toString().padStart(12, '0')}`,
      },
    );
    out.push(ev);
    head = { seq: ev.seq, event_hash: ev.event_hash };
  }
  return out;
}

describe('ProofBundle signatures field', () => {
  const chain = buildChain();

  it('omits signatures field when no records added', () => {
    const b = new ProofBundleBuilder({
      chain_id: 'c',
      producer_runtime: 'r',
    });
    b.extend(chain);
    const bundle = b.build({ now: NOW });
    expect(bundle.signatures).toBeUndefined();
  });

  it('emits signatures field when records added', () => {
    const provider = new InMemoryKeyProvider({ seed: new Uint8Array(32) });
    const signer = new Signer({
      chain_id: 'c',
      key_provider: provider,
      now: () => NOW,
    });
    const records = signer.signSegmentHead({
      seq: 2,
      event_hash: (chain[2] as ChainedEvent).event_hash,
    });
    const b = new ProofBundleBuilder({
      chain_id: 'c',
      producer_runtime: 'r',
    });
    b.extend(chain);
    b.extendSignatures(records);
    const bundle = b.build({ now: NOW });
    expect(bundle.signatures).toBeDefined();
    expect(bundle.signatures?.length).toBe(1);
  });

  it('round-trips serialize → deserialize byte-equal', () => {
    const provider = new InMemoryKeyProvider({ seed: new Uint8Array(32) });
    const signer = new Signer({
      chain_id: 'c',
      key_provider: provider,
      now: () => NOW,
    });
    const [record] = signer.signSegmentHead({
      seq: 2,
      event_hash: (chain[2] as ChainedEvent).event_hash,
    });
    if (record === undefined) throw new Error('signer returned no records');
    const serialised = serializeSignatureRecord(record);
    const round = deserializeSignatureRecord(serialised);
    expect(round.signature_schema_version).toBe(record.signature_schema_version);
    expect(round.signed_seq).toBe(record.signed_seq);
    expect(round.key_id).toBe(record.key_id);
    expect(Buffer.from(round.signature).toString('hex')).toBe(
      Buffer.from(record.signature).toString('hex'),
    );
    expect(Buffer.from(round.public_key_der).toString('hex')).toBe(
      Buffer.from(record.public_key_der).toString('hex'),
    );
  });

  it('deserialize rejects missing field', () => {
    const provider = new InMemoryKeyProvider({ seed: new Uint8Array(32) });
    const signer = new Signer({
      chain_id: 'c',
      key_provider: provider,
      now: () => NOW,
    });
    const [record] = signer.signSegmentHead({
      seq: 2,
      event_hash: (chain[2] as ChainedEvent).event_hash,
    });
    if (record === undefined) throw new Error('signer returned no records');
    const serialised = serializeSignatureRecord(record) as unknown as Record<string, unknown>;
    const { signature_hex: _omitted, ...withoutSignature } = serialised;
    expect(() => deserializeSignatureRecord(withoutSignature as never)).toThrow(/missing field/);
  });
});
