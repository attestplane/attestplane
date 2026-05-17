// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';

import { canonicalize } from '../src/canonical.js';
import {
  GENESIS_HASH,
  SCHEMA_VERSION,
  chainExtend,
  genesisHead,
  hashEvent,
  headOf,
  verifyChain,
} from '../src/hashchain.js';
import { type ChainedEvent, makeEventDraft, makeSubjectRef } from '../src/types.js';

const FIXED_NOW = new Date('2026-05-17T12:00:00.000Z');

describe('genesis', () => {
  it('genesisHead has seq -1 and 32 zero bytes', () => {
    const head = genesisHead();
    expect(head.seq).toBe(-1);
    expect(head.event_hash).toEqual(GENESIS_HASH);
    expect(GENESIS_HASH.length).toBe(32);
    for (const byte of GENESIS_HASH) expect(byte).toBe(0);
  });

  it('SCHEMA_VERSION is frozen at 1', () => {
    expect(SCHEMA_VERSION).toBe(1);
  });
});

describe('chainExtend', () => {
  it('assigns seq 0 and links to genesis', () => {
    const draft = makeEventDraft({ event_type: 'ai_decision', actor: 'agent-a' });
    const chained = chainExtend(genesisHead(), draft, { now: FIXED_NOW, event_id: 'evt-1' });
    expect(chained.seq).toBe(0);
    expect(chained.prev_hash).toEqual(GENESIS_HASH);
    expect(chained.event.schema_version).toBe(SCHEMA_VERSION);
    expect(chained.event.event_id).toBe('evt-1');
  });

  it('is deterministic given (tip, draft, now, event_id)', () => {
    const draft = makeEventDraft({
      event_type: 'ai_decision',
      actor: 'agent-a',
      payload: { k: 1 },
    });
    const a = chainExtend(genesisHead(), draft, { now: FIXED_NOW, event_id: 'x' });
    const b = chainExtend(genesisHead(), draft, { now: FIXED_NOW, event_id: 'x' });
    expect(a.event_hash).toEqual(b.event_hash);
  });

  it('generates UUIDv7 when event_id omitted', () => {
    const draft = makeEventDraft({ event_type: 't', actor: 'a' });
    const chained = chainExtend(genesisHead(), draft, { now: FIXED_NOW });
    expect(chained.event.event_id).toHaveLength(36);
    expect(chained.event.event_id.charAt(14)).toBe('7');
  });
});

describe('hashEvent', () => {
  it('equals sha256(canonicalize(event))', () => {
    const draft = makeEventDraft({ event_type: 't', actor: 'a', payload: { x: 1 } });
    const chained = chainExtend(genesisHead(), draft, { now: FIXED_NOW, event_id: 'e' });
    const expected = createHash('sha256').update(canonicalize(chained.event)).digest();
    expect(chained.event_hash).toEqual(new Uint8Array(expected));
  });
});

describe('verifyChain', () => {
  const buildChain = (count: number): ChainedEvent[] => {
    const events: ChainedEvent[] = [];
    let head = genesisHead();
    for (let i = 0; i < count; i++) {
      const draft = makeEventDraft({ event_type: 't', actor: 'a', payload: { i } });
      const chained = chainExtend(head, draft, {
        now: new Date(FIXED_NOW.getTime() + i),
        event_id: `e${i}`,
      });
      events.push(chained);
      head = headOf(events);
    }
    return events;
  };

  it('empty chain is ok', () => {
    expect(verifyChain([])).toEqual({ ok: true, first_bad_index: null, reason: null });
  });

  it('valid chain of 3 verifies', () => {
    const events = buildChain(3);
    const r = verifyChain(events);
    expect(r.ok).toBe(true);
  });

  it('detects payload tamper at index 1', () => {
    const events = buildChain(3);
    const tampered: ChainedEvent[] = [...events];
    const original = events[1] as ChainedEvent;
    tampered[1] = {
      ...original,
      event: { ...original.event, payload: { i: 99 } },
    };
    const r = verifyChain(tampered);
    expect(r.ok).toBe(false);
    expect(r.first_bad_index).toBe(1);
    expect(r.reason).toMatch(/event_hash/);
  });

  it('detects broken prev_hash', () => {
    const events = buildChain(2);
    const tampered: ChainedEvent[] = [...events];
    const original = events[1] as ChainedEvent;
    tampered[1] = { ...original, prev_hash: new Uint8Array(32).fill(0xff) };
    const r = verifyChain(tampered);
    expect(r.ok).toBe(false);
    expect(r.first_bad_index).toBe(1);
    expect(r.reason).toMatch(/prev_hash/);
  });

  it('detects seq skip', () => {
    const events = buildChain(1);
    const tampered: ChainedEvent[] = [{ ...(events[0] as ChainedEvent), seq: 5 }];
    const r = verifyChain(tampered);
    expect(r.ok).toBe(false);
    expect(r.reason).toMatch(/seq mismatch/);
  });
});

describe('subject_ref impact on hash', () => {
  it('different subject_ref → different event_hash', () => {
    const a = chainExtend(genesisHead(), makeEventDraft({ event_type: 't', actor: 'a' }), {
      now: FIXED_NOW,
      event_id: 'e',
    });
    const b = chainExtend(
      genesisHead(),
      makeEventDraft({
        event_type: 't',
        actor: 'a',
        subject_ref: makeSubjectRef('opaque', 'user-1'),
      }),
      { now: FIXED_NOW, event_id: 'e' },
    );
    expect(a.event_hash).not.toEqual(b.event_hash);
  });
});
