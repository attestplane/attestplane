// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';

import { chainExtend, genesisHead } from '../../src/hashchain.js';
import { type ChainHead, type ChainedEvent, makeEventDraft } from '../../src/types.js';

import { InMemoryKeyProvider, MultiSignerProvider } from '../../src/signing/providers.js';
import { Signer } from '../../src/signing/signer.js';
import { parseTrustRoots } from '../../src/signing/trust_roots.js';
import {
  STATUS_RANK,
  verifyChainFull,
  verifyChainWithSignatures,
} from '../../src/signing/verifier_ext.js';

const NOW = new Date('2026-05-17T12:00:00Z');

function buildChain(): ChainedEvent[] {
  const out: ChainedEvent[] = [];
  let head: ChainHead = genesisHead();
  for (let i = 0; i < 5; i++) {
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

function trustRootsFor(
  provider: InMemoryKeyProvider,
  options: {
    valid_from?: string;
    valid_until?: string;
  } = {},
) {
  const mat = provider.getSigningMaterial();
  return parseTrustRoots({
    version: 1,
    keys: [
      {
        key_id: mat.keyId,
        public_key_der_b64: Buffer.from(mat.publicKeyDer).toString('base64'),
        valid_from: options.valid_from ?? '2026-01-01T00:00:00Z',
        valid_until: options.valid_until ?? '2027-01-01T00:00:00Z',
      },
    ],
  });
}

describe('STATUS_RANK', () => {
  it('ranks valid < expired_key < invalid < unknown_key < unsigned', () => {
    expect(STATUS_RANK.valid).toBe(0);
    expect(STATUS_RANK.expired_key).toBe(1);
    expect(STATUS_RANK.invalid).toBe(2);
    expect(STATUS_RANK.unknown_key).toBe(3);
    expect(STATUS_RANK.unsigned).toBe(4);
  });
});

describe('verifyChainWithSignatures', () => {
  const chain = buildChain();

  it('returns unsigned for empty record list', () => {
    const provider = new InMemoryKeyProvider({ seed: new Uint8Array(32) });
    const trustRoots = trustRootsFor(provider);
    const result = verifyChainWithSignatures(chain, [], {
      chain_id: 'c',
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    expect(result.signature_status).toBe('unsigned');
    expect(result.signed_segment_count).toBe(0);
    expect(result.first_bad_signature_index).toBeNull();
  });

  it('returns expired_key when verification_time is past valid_until', () => {
    const provider = new InMemoryKeyProvider({ seed: new Uint8Array(32) });
    const signer = new Signer({
      chain_id: 'c',
      key_provider: provider,
      now: () => NOW,
    });
    const records = signer.signSegmentHead({
      seq: 4,
      event_hash: (chain[4] as ChainedEvent).event_hash,
    });
    const trustRoots = trustRootsFor(provider, {
      valid_from: '2026-01-01T00:00:00Z',
      valid_until: '2026-02-01T00:00:00Z',
    });
    const result = verifyChainWithSignatures(chain, records, {
      chain_id: 'c',
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    expect(result.signature_status).toBe('expired_key');
    expect(result.first_bad_signature_index).toBe(0);
  });

  it('returns expired_key when verification_time precedes valid_from', () => {
    const provider = new InMemoryKeyProvider({ seed: new Uint8Array(32) });
    const signer = new Signer({
      chain_id: 'c',
      key_provider: provider,
      now: () => NOW,
    });
    const records = signer.signSegmentHead({
      seq: 4,
      event_hash: (chain[4] as ChainedEvent).event_hash,
    });
    const trustRoots = trustRootsFor(provider, {
      valid_from: '2030-01-01T00:00:00Z',
      valid_until: '2031-01-01T00:00:00Z',
    });
    const result = verifyChainWithSignatures(chain, records, {
      chain_id: 'c',
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    expect(result.signature_status).toBe('expired_key');
  });

  it('returns invalid when chain_id used by verifier differs from signed payload', () => {
    const provider = new InMemoryKeyProvider({ seed: new Uint8Array(32) });
    const signer = new Signer({
      chain_id: 'original-chain',
      key_provider: provider,
      now: () => NOW,
    });
    const records = signer.signSegmentHead({
      seq: 4,
      event_hash: (chain[4] as ChainedEvent).event_hash,
    });
    const trustRoots = trustRootsFor(provider);
    const result = verifyChainWithSignatures(chain, records, {
      chain_id: 'wrong-chain',
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    expect(result.signature_status).toBe('invalid');
    expect(result.signature_results[0]?.reason ?? '').toContain('chain_id');
  });

  it('plurality lifts a seq covered by any valid signature', () => {
    const good = new InMemoryKeyProvider({
      seed: new Uint8Array(32),
      provider_id: 'good',
    });
    const ghost = new InMemoryKeyProvider({
      seed: new Uint8Array(32).fill(0x99),
      provider_id: 'ghost',
    });
    const multi = new MultiSignerProvider([good, ghost]);
    const signer = new Signer({
      chain_id: 'c',
      key_provider: multi,
      now: () => NOW,
    });
    const records = signer.signSegmentHead({
      seq: 4,
      event_hash: (chain[4] as ChainedEvent).event_hash,
    });
    // Trust roots include only the good provider's key.
    const trustRoots = trustRootsFor(good);
    const result = verifyChainWithSignatures(chain, records, {
      chain_id: 'c',
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    // Per-seq plurality merge lifts seq=4 to 'valid' (any valid lifts
    // the seq). Bundle status is computed from the merged per-seq map,
    // so the only seq with signatures (seq=4) → 'valid' → bundle 'valid'.
    expect(result.signature_status).toBe('valid');
    expect(result.signed_segment_count).toBe(5);
    // Individual record statuses still expose the unknown_key case.
    const statuses = result.signature_results.map((r) => r.status).sort();
    expect(statuses).toEqual(['unknown_key', 'valid']);
  });
});

describe('verifyChainFull', () => {
  const chain = buildChain();

  it('returns unsigned when no signatures provided', () => {
    const result = verifyChainFull(chain, {});
    expect(result.signature_status).toBe('unsigned');
    expect(result.signed_segment_count).toBe(0);
    expect(result.ok).toBe(true); // chain itself OK; no anchors required.
  });

  it('throws when signatures provided without chain_id/trust_roots', () => {
    const provider = new InMemoryKeyProvider({ seed: new Uint8Array(32) });
    const signer = new Signer({
      chain_id: 'c',
      key_provider: provider,
      now: () => NOW,
    });
    const records = signer.signSegmentHead({
      seq: 4,
      event_hash: (chain[4] as ChainedEvent).event_hash,
    });
    expect(() => verifyChainFull(chain, { signatures: records })).toThrow(
      /chain_id or trust_roots/,
    );
  });

  it('returns valid signature_status when everything checks out', () => {
    const provider = new InMemoryKeyProvider({ seed: new Uint8Array(32) });
    const signer = new Signer({
      chain_id: 'c',
      key_provider: provider,
      now: () => NOW,
    });
    const records = signer.signSegmentHead({
      seq: 4,
      event_hash: (chain[4] as ChainedEvent).event_hash,
    });
    const trustRoots = trustRootsFor(provider);
    const result = verifyChainFull(chain, {
      signatures: records,
      chain_id: 'c',
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    expect(result.signature_status).toBe('valid');
    expect(result.signed_segment_count).toBe(5);
  });
});
