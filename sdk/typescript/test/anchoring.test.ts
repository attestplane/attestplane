// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Tests for src/anchoring.ts — TypeScript port of
 * sdk/python/tests/anchoring/test_anchoring.py.
 */

import { describe, expect, it } from 'vitest';

import {
  ANCHOR_SCHEMA_VERSION,
  AnchorError,
  type AnchorRecord,
  AnchorVerificationError,
  DEFAULT_ANCHOR_POLICY,
  MockTSAProvider,
  MultiTSAProvider,
  type SingleAnchorResult,
  TSAProvider,
  TSAUnavailableError,
  makeAnchorPolicy,
  makeTimestampRequest,
  validateAnchorRecord,
  verifyChainWithAnchors,
} from '../src/anchoring.js';
import { chainExtend, genesisHead } from '../src/hashchain.js';
import {
  type ChainHead,
  type ChainedEvent,
  type EventDraft,
  makeEventDraft,
} from '../src/types.js';

function buildChain(n: number): ChainedEvent[] {
  const ts = new Date('2026-05-17T12:00:00.000Z');
  const chain: ChainedEvent[] = [];
  let head: ChainHead = genesisHead();
  for (let i = 0; i < n; i++) {
    const draft = makeEventDraft({
      event_type: 'eval_event',
      actor: `agent://test/${i}`,
      payload: { i },
    });
    const ev = chainExtend(head, draft, {
      now: ts,
      event_id: `00000000-0000-7000-8000-${i.toString().padStart(12, '0')}`,
    });
    chain.push(ev);
    head = { seq: ev.seq, event_hash: ev.event_hash };
  }
  return chain;
}

describe('AnchorRecord invariants', () => {
  it('rejects wrong schema version', () => {
    expect(() =>
      validateAnchorRecord({
        anchor_schema_version: 99,
        anchored_seq: 0,
        anchored_event_hash: new Uint8Array(32),
        tsa_provider_id: 'x',
        tsa_token: new Uint8Array(1),
        tsa_cert_chain: [new Uint8Array(1)],
        ocsp_responses: [new Uint8Array(1)],
        issued_at_claimed: new Date(),
      }),
    ).toThrow(/anchor_schema_version/);
  });

  it('rejects short hash', () => {
    expect(() =>
      validateAnchorRecord({
        anchor_schema_version: ANCHOR_SCHEMA_VERSION,
        anchored_seq: 0,
        anchored_event_hash: new Uint8Array(16),
        tsa_provider_id: 'x',
        tsa_token: new Uint8Array(1),
        tsa_cert_chain: [new Uint8Array(1)],
        ocsp_responses: [new Uint8Array(1)],
        issued_at_claimed: new Date(),
      }),
    ).toThrow(/32 bytes/);
  });

  it('rejects negative seq', () => {
    expect(() =>
      validateAnchorRecord({
        anchor_schema_version: ANCHOR_SCHEMA_VERSION,
        anchored_seq: -1,
        anchored_event_hash: new Uint8Array(32),
        tsa_provider_id: 'x',
        tsa_token: new Uint8Array(1),
        tsa_cert_chain: [new Uint8Array(1)],
        ocsp_responses: [new Uint8Array(1)],
        issued_at_claimed: new Date(),
      }),
    ).toThrow(/anchored_seq/);
  });

  it('rejects empty provider id', () => {
    expect(() =>
      validateAnchorRecord({
        anchor_schema_version: ANCHOR_SCHEMA_VERSION,
        anchored_seq: 0,
        anchored_event_hash: new Uint8Array(32),
        tsa_provider_id: '',
        tsa_token: new Uint8Array(1),
        tsa_cert_chain: [new Uint8Array(1)],
        ocsp_responses: [new Uint8Array(1)],
        issued_at_claimed: new Date(),
      }),
    ).toThrow(/tsa_provider_id/);
  });
});

describe('AnchorPolicy', () => {
  it('default values', () => {
    expect(DEFAULT_ANCHOR_POLICY.batch_size).toBe(64);
    expect(DEFAULT_ANCHOR_POLICY.max_idle_seconds).toBe(60);
    expect(DEFAULT_ANCHOR_POLICY.per_event).toBe(false);
  });

  it('rejects zero batch_size', () => {
    expect(() => makeAnchorPolicy({ batch_size: 0 })).toThrow(/batch_size/);
  });

  it('rejects zero idle', () => {
    expect(() => makeAnchorPolicy({ max_idle_seconds: 0 })).toThrow(/max_idle/);
  });

  it('accepts custom values', () => {
    const p = makeAnchorPolicy({ batch_size: 1, max_idle_seconds: 5, per_event: true });
    expect(p.batch_size).toBe(1);
    expect(p.per_event).toBe(true);
  });
});

describe('TimestampRequest', () => {
  it('rejects non-SHA256 digest', () => {
    expect(() => makeTimestampRequest({ digest: new Uint8Array(16) })).toThrow(/32 bytes/);
  });

  it('accepts nonce', () => {
    const req = makeTimestampRequest({
      digest: new Uint8Array(32),
      nonce: new TextEncoder().encode('random'),
    });
    expect(req.nonce).toBeDefined();
  });
});

describe('TSAProvider forbidden-verb gate', () => {
  const forbidden = ['mutate', 'rewrite', 'replace', 'revoke', 'retract', 'delete', 'remove'];
  for (const verb of forbidden) {
    it(`rejects forbidden method "${verb}" at instantiation`, () => {
      class BadProvider extends TSAProvider {
        readonly provider_id = 'bad';
        readonly schema_version = ANCHOR_SCHEMA_VERSION;
        requestTimestamp(): AnchorRecord {
          throw new Error('unused');
        }
      }
      Object.defineProperty(BadProvider.prototype, verb, {
        value: () => undefined,
        enumerable: false,
        configurable: true,
        writable: true,
      });
      expect(() => new BadProvider()).toThrow(/forbidden mutating method/);
    });
  }

  it('rejects abstract instantiation indirectly (TS classes require subclass)', () => {
    // TSAProvider is abstract; TS prevents direct instantiation at compile time.
    // Runtime-wise, only a subclass missing required members would fail.
    class Stub extends TSAProvider {
      readonly provider_id = 'stub';
      readonly schema_version = ANCHOR_SCHEMA_VERSION;
      requestTimestamp(): AnchorRecord {
        throw new Error('not implemented');
      }
    }
    expect(() => new Stub()).not.toThrow();
  });
});

describe('MockTSAProvider', () => {
  it('produces deterministic anchor', () => {
    const provider = new MockTSAProvider({
      fixed_time: new Date('2026-05-17T12:00:00.000Z'),
    });
    const req = makeTimestampRequest({ digest: new Uint8Array(32) });
    const a1 = provider.requestTimestamp(req);
    const a2 = provider.requestTimestamp(req);
    expect(a1.tsa_token).toEqual(a2.tsa_token);
  });

  it('token depends on digest', () => {
    const provider = new MockTSAProvider({
      fixed_time: new Date('2026-05-17T12:00:00.000Z'),
    });
    const a = provider.requestTimestamp(makeTimestampRequest({ digest: new Uint8Array(32) }));
    const bDigest = new Uint8Array(32);
    bDigest[0] = 1;
    const b = provider.requestTimestamp(makeTimestampRequest({ digest: bDigest }));
    expect(a.tsa_token).not.toEqual(b.tsa_token);
  });

  it('raises when configured to fail', () => {
    const provider = new MockTSAProvider({
      fail_with: new TSAUnavailableError('simulated outage'),
    });
    expect(() =>
      provider.requestTimestamp(makeTimestampRequest({ digest: new Uint8Array(32) })),
    ).toThrow(/simulated outage/);
  });

  it('uses explicit now', () => {
    const provider = new MockTSAProvider();
    const explicit = new Date('2030-01-01T00:00:00.000Z');
    const a = provider.requestTimestamp(makeTimestampRequest({ digest: new Uint8Array(32) }), {
      now: explicit,
    });
    expect(a.issued_at_claimed.getTime()).toBe(explicit.getTime());
  });

  it('writes well-formed AnchorRecord', () => {
    const provider = new MockTSAProvider({
      fixed_time: new Date('2026-05-17T12:00:00.000Z'),
    });
    const chain = buildChain(1);
    const a = provider.requestTimestamp(makeTimestampRequest({ digest: chain[0]?.event_hash }), {
      anchoredSeq: 0,
    });
    expect(a.anchor_schema_version).toBe(ANCHOR_SCHEMA_VERSION);
    expect(a.anchored_seq).toBe(0);
    expect(a.tsa_provider_id).toBe('mock.tsa.local');
    expect(a.tsa_cert_chain.length).toBe(1);
    expect(a.ocsp_responses.length).toBe(1);
  });
});

describe('MultiTSAProvider', () => {
  const fixedTime = new Date('2026-05-17T12:00:00.000Z');

  it('fans out', () => {
    const p1 = new MockTSAProvider({ provider_id: 'alpha', fixed_time: fixedTime });
    const p2 = new MockTSAProvider({ provider_id: 'beta', fixed_time: fixedTime });
    const multi = new MultiTSAProvider({ providers: [p1, p2] });
    const anchors = multi.requestTimestamps(makeTimestampRequest({ digest: new Uint8Array(32) }));
    expect(anchors.length).toBe(2);
    expect(new Set(anchors.map((a) => a.tsa_provider_id))).toEqual(new Set(['alpha', 'beta']));
  });

  it('requires at least one provider', () => {
    expect(() => new MultiTSAProvider({ providers: [] })).toThrow(/at least one/);
  });

  it('rejects duplicate ids', () => {
    const p1 = new MockTSAProvider({ provider_id: 'same' });
    const p2 = new MockTSAProvider({ provider_id: 'same' });
    expect(() => new MultiTSAProvider({ providers: [p1, p2] })).toThrow(/distinct provider_id/);
  });

  it('fails fast by default', () => {
    const good = new MockTSAProvider({ provider_id: 'alpha', fixed_time: fixedTime });
    const bad = new MockTSAProvider({
      provider_id: 'beta',
      fail_with: new TSAUnavailableError('dead'),
    });
    const multi = new MultiTSAProvider({ providers: [good, bad] });
    expect(() =>
      multi.requestTimestamps(makeTimestampRequest({ digest: new Uint8Array(32) })),
    ).toThrow(/dead/);
  });

  it('tolerates partial success when enabled', () => {
    const good = new MockTSAProvider({ provider_id: 'alpha', fixed_time: fixedTime });
    const bad = new MockTSAProvider({
      provider_id: 'beta',
      fail_with: new TSAUnavailableError('dead'),
    });
    const multi = new MultiTSAProvider({ providers: [good, bad], tolerate_partial: true });
    const anchors = multi.requestTimestamps(makeTimestampRequest({ digest: new Uint8Array(32) }));
    expect(anchors.length).toBe(1);
    expect(anchors[0]?.tsa_provider_id).toBe('alpha');
  });

  it('all-fail partial mode re-raises', () => {
    const p1 = new MockTSAProvider({
      provider_id: 'alpha',
      fail_with: new TSAUnavailableError('one'),
    });
    const p2 = new MockTSAProvider({
      provider_id: 'beta',
      fail_with: new TSAUnavailableError('two'),
    });
    const multi = new MultiTSAProvider({ providers: [p1, p2], tolerate_partial: true });
    expect(() =>
      multi.requestTimestamps(makeTimestampRequest({ digest: new Uint8Array(32) })),
    ).toThrow(TSAUnavailableError);
  });

  it('providerIds property', () => {
    const p1 = new MockTSAProvider({ provider_id: 'alpha' });
    const p2 = new MockTSAProvider({ provider_id: 'beta' });
    const multi = new MultiTSAProvider({ providers: [p1, p2] });
    expect(multi.providerIds).toEqual(['alpha', 'beta']);
  });
});

describe('verifyChainWithAnchors', () => {
  const fixedTime = new Date('2026-05-17T12:00:00.000Z');

  function goodAnchor(chain: ChainedEvent[], seq: number): AnchorRecord {
    const provider = new MockTSAProvider({ fixed_time: fixedTime });
    return provider.requestTimestamp(makeTimestampRequest({ digest: chain[seq]?.event_hash }), {
      anchoredSeq: seq,
    });
  }

  it('empty inputs', () => {
    const result = verifyChainWithAnchors([], []);
    expect(result.ok).toBe(false);
    expect(result.chain_ok).toBe(true);
    expect(result.verification_status).toBe('not_performed');
    expect(result.anchored_seqs.size).toBe(0);
    expect(result.unanchored_seqs.size).toBe(0);
  });

  it('unanchored chain', () => {
    const chain = buildChain(3);
    const result = verifyChainWithAnchors(chain, []);
    expect(result.chain_ok).toBe(true);
    expect(result.ok).toBe(false);
    expect(result.verification_status).toBe('not_performed');
    expect(result.unanchored_seqs).toEqual(new Set([0, 1, 2]));
  });

  it('one good anchor', () => {
    const chain = buildChain(3);
    const result = verifyChainWithAnchors(chain, [goodAnchor(chain, 2)]);
    expect(result.ok).toBe(true);
    expect(result.verification_status).toBe('verified');
    expect(result.anchor_results[0]?.valid).toBe(true);
    expect(result.anchor_results[0]?.cert_status).toBe('VALID_UNVERIFIED');
    expect(result.anchored_seqs).toEqual(new Set([2]));
  });

  it('multi-anchor plurality', () => {
    const chain = buildChain(2);
    const p1 = new MockTSAProvider({ provider_id: 'alpha', fixed_time: fixedTime });
    const p2 = new MockTSAProvider({ provider_id: 'beta', fixed_time: fixedTime });
    const multi = new MultiTSAProvider({ providers: [p1, p2] });
    const anchors = multi.requestTimestamps(
      makeTimestampRequest({ digest: chain[1]?.event_hash }),
      { anchoredSeq: 1 },
    );
    const result = verifyChainWithAnchors(chain, anchors);
    expect(result.ok).toBe(true);
    expect(result.anchor_results.length).toBe(2);
    expect(result.anchor_results.every((a) => a.valid)).toBe(true);
  });

  it('detects hash mismatch', () => {
    const chain = buildChain(2);
    const bad: AnchorRecord = {
      anchor_schema_version: ANCHOR_SCHEMA_VERSION,
      anchored_seq: 0,
      anchored_event_hash: new Uint8Array(32).fill(0xff),
      tsa_provider_id: 'mock.tsa.local',
      tsa_token: new Uint8Array(1),
      tsa_cert_chain: [new Uint8Array(1)],
      ocsp_responses: [new Uint8Array(1)],
      issued_at_claimed: fixedTime,
    };
    const result = verifyChainWithAnchors(chain, [bad]);
    expect(result.ok).toBe(false);
    expect(result.verification_status).toBe('failed');
    expect(result.anchor_results[0]?.valid).toBe(false);
    expect(result.anchor_results[0]?.reason).toMatch(/event_hash mismatch/);
  });

  it('detects seq out of range', () => {
    const chain = buildChain(2);
    const bad: AnchorRecord = {
      anchor_schema_version: ANCHOR_SCHEMA_VERSION,
      anchored_seq: 99,
      anchored_event_hash: new Uint8Array(32),
      tsa_provider_id: 'mock.tsa.local',
      tsa_token: new Uint8Array(1),
      tsa_cert_chain: [new Uint8Array(1)],
      ocsp_responses: [new Uint8Array(1)],
      issued_at_claimed: fixedTime,
    };
    const result = verifyChainWithAnchors(chain, [bad]);
    expect(result.ok).toBe(false);
    expect(result.anchor_results[0]?.reason).toMatch(/not in chain/);
  });

  it('detects missing LTV artifacts', () => {
    const chain = buildChain(2);
    const bad: AnchorRecord = {
      anchor_schema_version: ANCHOR_SCHEMA_VERSION,
      anchored_seq: 0,
      anchored_event_hash: chain[0]?.event_hash,
      tsa_provider_id: 'mock.tsa.local',
      tsa_token: new Uint8Array(1),
      tsa_cert_chain: [],
      ocsp_responses: [new Uint8Array(1)],
      issued_at_claimed: fixedTime,
    };
    const result = verifyChainWithAnchors(chain, [bad]);
    expect(result.ok).toBe(false);
    expect(result.anchor_results[0]?.cert_status).toBe('MISSING_LTV_ARTIFACTS');
  });

  it('quarantines live verification failures', () => {
    const chain = buildChain(1);
    const anchor = goodAnchor(chain, 0);
    const tamperedToken = anchor.tsa_token.slice();
    tamperedToken[tamperedToken.length - 1] ^= 0x01;
    const result = verifyChainWithAnchors(chain, [
      { ...anchor, tsa_token: tamperedToken },
    ], {
      trustRootsDer: [anchor.tsa_cert_chain[0] ?? new Uint8Array(0)],
      verificationTime: fixedTime,
    });
    expect(result.ok).toBe(false);
    expect(result.verification_status).toBe('quarantined');
    expect(result.anchor_results[0]?.cert_status).toBe('QUARANTINED');
  });

  it('v1 cert_status is VALID_UNVERIFIED for good anchors', () => {
    const chain = buildChain(1);
    const result = verifyChainWithAnchors(chain, [goodAnchor(chain, 0)]);
    expect(result.anchor_results[0]?.cert_status).toBe('VALID_UNVERIFIED');
  });

  it('is read-only', () => {
    const chain = buildChain(2);
    const anchors = [goodAnchor(chain, 1)];
    const beforeChain = JSON.stringify(chain);
    const beforeAnchors = JSON.stringify(anchors);
    const result = verifyChainWithAnchors(chain, anchors);
    expect(result.ok).toBe(true);
    expect(JSON.stringify(chain)).toBe(beforeChain);
    expect(JSON.stringify(anchors)).toBe(beforeAnchors);
  });
});
