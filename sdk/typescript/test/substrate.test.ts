// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';

import { GENESIS_HASH } from '../src/hashchain.js';
import { AttestSubstrate } from '../src/substrate.js';
import { makeEventDraft, makeSubjectRef } from '../src/types.js';

const FIXED_NOW = new Date('2026-05-17T12:00:00.000Z');

describe('AttestSubstrate', () => {
  it('starts empty', () => {
    const s = new AttestSubstrate();
    expect(s.length).toBe(0);
    expect(s.tip().event_hash).toEqual(GENESIS_HASH);
    expect(s.tip().seq).toBe(-1);
    expect(s.verify().ok).toBe(true);
  });

  it('append assigns chain fields', () => {
    const s = new AttestSubstrate();
    const e = s.append(makeEventDraft({ event_type: 'ai_decision', actor: 'agent-a' }), {
      now: FIXED_NOW,
    });
    expect(e.seq).toBe(0);
    expect(e.prev_hash).toEqual(GENESIS_HASH);
    expect(s.length).toBe(1);
    expect(s.tip().event_hash).toEqual(e.event_hash);
  });

  it('three appends link correctly and verify', () => {
    const s = new AttestSubstrate();
    const events = [0, 1, 2].map((i) =>
      s.append(makeEventDraft({ event_type: 't', actor: 'a', payload: { i } }), {
        now: new Date(FIXED_NOW.getTime() + i),
      }),
    );
    expect(events.map((e) => e.seq)).toEqual([0, 1, 2]);
    expect(events[1]?.prev_hash).toEqual(events[0]?.event_hash);
    expect(events[2]?.prev_hash).toEqual(events[1]?.event_hash);
    expect(s.verify().ok).toBe(true);
  });

  it('iterator yields all events', () => {
    const s = new AttestSubstrate();
    s.append(makeEventDraft({ event_type: 't', actor: 'a' }), { now: FIXED_NOW });
    s.append(makeEventDraft({ event_type: 't', actor: 'a' }), {
      now: new Date(FIXED_NOW.getTime() + 1),
    });
    const collected = Array.from(s);
    expect(collected).toHaveLength(2);
  });

  it('fromEvents rehydrates a valid chain', () => {
    const source = new AttestSubstrate();
    for (let i = 0; i < 3; i++) {
      source.append(makeEventDraft({ event_type: 't', actor: 'a', payload: { i } }), {
        now: new Date(FIXED_NOW.getTime() + i),
      });
    }
    const rehydrated = AttestSubstrate.fromEvents(source.snapshot());
    expect(rehydrated.length).toBe(3);
    expect(rehydrated.tip()).toEqual(source.tip());
  });

  it('fromEvents rejects a broken chain', () => {
    const source = new AttestSubstrate();
    for (let i = 0; i < 2; i++) {
      source.append(makeEventDraft({ event_type: 't', actor: 'a' }), {
        now: new Date(FIXED_NOW.getTime() + i),
      });
    }
    const events = source.snapshot();
    const tampered = [...events];
    const original = events[0];
    if (!original) throw new Error('test setup failed');
    tampered[0] = { ...original, event_hash: new Uint8Array(32) };
    expect(() => AttestSubstrate.fromEvents(tampered)).toThrow(/rehydrate/);
  });

  it('event_id is UUIDv7', () => {
    const s = new AttestSubstrate();
    const e = s.append(makeEventDraft({ event_type: 't', actor: 'a' }), { now: FIXED_NOW });
    const parts = e.event.event_id.split('-');
    expect(parts).toHaveLength(5);
    expect(parts[2]?.charAt(0)).toBe('7');
  });

  it('Art. 12 fields contribute to hash', () => {
    const a = new AttestSubstrate();
    const b = new AttestSubstrate();
    a.append(makeEventDraft({ event_type: 't', actor: 'a' }), { now: FIXED_NOW });
    b.append(
      makeEventDraft({
        event_type: 't',
        actor: 'a',
        session_id: 'session-xyz',
        reference_db_ref: 'db://watchlist/v1',
        matched_input_ref: 'hash:abc',
        human_verifier: makeSubjectRef('opaque', 'reviewer-1'),
      }),
      { now: FIXED_NOW },
    );
    const ea = a.snapshot()[0];
    const eb = b.snapshot()[0];
    if (!ea || !eb) throw new Error('test setup failed');
    expect(ea.event_hash).not.toEqual(eb.event_hash);
  });

  it('SubjectRef scheme=none requires empty value', () => {
    expect(() => makeSubjectRef('none', 'x')).toThrow(/empty value/);
  });

  it("SubjectRef non-'none' scheme requires non-empty value", () => {
    expect(() => makeSubjectRef('opaque', '')).toThrow(/non-empty value/);
  });
});
