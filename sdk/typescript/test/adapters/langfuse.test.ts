// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Tests for src/adapters/langfuse.ts — TypeScript port of
 * sdk/python/tests/adapters/test_langfuse.py.
 */

import { createHash } from 'node:crypto';

import { describe, expect, it } from 'vitest';

import { AdapterTranslationError } from '../../src/adapters.js';
import { LangFuseAdapter, type LangFuseObservation } from '../../src/adapters/langfuse.js';
import { TOOL_CALL_EVENT } from '../../src/event_types.js';

const NOW = new Date('2026-05-17T12:00:00.000Z');

function hashJson(value: unknown): string {
  function sortDeep(v: unknown): unknown {
    if (v instanceof Date) return v.toISOString();
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
      const obj = v as Record<string, unknown>;
      const out: Record<string, unknown> = {};
      for (const k of Object.keys(obj).sort()) out[k] = sortDeep(obj[k]);
      return out;
    }
    if (Array.isArray(v)) return v.map(sortDeep);
    return v;
  }
  return createHash('sha256')
    .update(JSON.stringify(sortDeep(value)), 'utf-8')
    .digest('hex');
}

describe('LangFuseAdapter', () => {
  it('translates a GENERATION observation', () => {
    const adapter = new LangFuseAdapter();
    const obs: LangFuseObservation = {
      id: 'obs-1',
      trace_id: 'trace-1',
      type: 'GENERATION',
      name: 'completion',
      start_time: NOW,
      end_time: NOW,
      input: { prompt: 'Hello' },
      output: { text: 'Hi there' },
      model: 'gpt-4o-mini',
      level: 'DEFAULT',
      user_id: 'user-42',
    };
    const draft = adapter.translate(obs);
    expect(draft.event_type).toBe(TOOL_CALL_EVENT);
    expect(draft.payload.kind).toBe('generation');
    expect(draft.payload.tool_name).toBe('langfuse.generation.completion');
    expect(draft.payload.tool_call_id).toBe('obs-1');
    expect(draft.payload.tool_version).toBe('gpt-4o-mini');
    expect(draft.payload.arguments_hash).toBe(hashJson({ prompt: 'Hello' }));
    expect(draft.payload.result_hash).toBe(hashJson({ text: 'Hi there' }));
    expect(draft.payload.result_status).toBe('OK');
    expect(draft.session_id).toBe('trace-1');
    expect(draft.subject_ref).toEqual({ scheme: 'opaque', value: 'user-42' });
  });

  it('translates SPAN observation', () => {
    const adapter = new LangFuseAdapter();
    const draft = adapter.translate({
      id: 'span-1',
      trace_id: 't-1',
      type: 'SPAN',
      name: 'agent_loop',
    });
    expect(draft.payload.kind).toBe('span');
  });

  it('translates EVENT observation', () => {
    const adapter = new LangFuseAdapter();
    const draft = adapter.translate({
      id: 'ev-1',
      trace_id: 't-1',
      type: 'EVENT',
      name: 'checkpoint',
    });
    expect(draft.payload.kind).toBe('event');
  });

  it('ERROR level → result_status ERROR', () => {
    const adapter = new LangFuseAdapter();
    const draft = adapter.translate({
      id: 'o',
      trace_id: 't',
      type: 'GENERATION',
      name: 'x',
      level: 'ERROR',
      status_message: 'rate limit exceeded',
    });
    expect(draft.payload.result_status).toBe('ERROR');
    expect(draft.payload.error_code).toContain('rate limit');
  });

  it('WARNING level → result_status OK + level preserved', () => {
    const adapter = new LangFuseAdapter();
    const draft = adapter.translate({
      id: 'o',
      trace_id: 't',
      type: 'SPAN',
      name: 'x',
      level: 'WARNING',
    });
    expect(draft.payload.result_status).toBe('OK');
    expect(draft.payload.level).toBe('WARNING');
  });

  it('redacts raw input/output (no secret in payload)', () => {
    const adapter = new LangFuseAdapter();
    const secret = 'Bearer sk-token-abc123';
    const draft = adapter.translate({
      id: 'o',
      trace_id: 't',
      type: 'GENERATION',
      name: 'x',
      input: { headers: secret },
      output: { text: secret },
    });
    expect(JSON.stringify(draft.payload)).not.toContain(secret);
    expect(draft.payload.arguments_hash).toBeDefined();
    expect(draft.payload.result_hash).toBeDefined();
  });

  it('null input still emits hash of empty object', () => {
    const adapter = new LangFuseAdapter();
    const draft = adapter.translate({
      id: 'o',
      trace_id: 't',
      type: 'GENERATION',
      name: 'x',
      input: null,
    });
    expect(draft.payload.arguments_hash).toBe(hashJson({}));
  });

  it('unknown type → kind=unknown', () => {
    const adapter = new LangFuseAdapter();
    const draft = adapter.translate({
      id: 'o',
      trace_id: 't',
      type: 'WEIRDTYPE',
      name: 'x',
    });
    expect(draft.payload.kind).toBe('unknown');
  });

  it('latency_ms populated when start/end present', () => {
    const adapter = new LangFuseAdapter();
    const end = new Date(NOW.getTime() + 2500);
    const draft = adapter.translate({
      id: 'o',
      trace_id: 't',
      type: 'GENERATION',
      name: 'x',
      start_time: NOW,
      end_time: end,
    });
    expect(draft.payload.latency_ms).toBe(2500);
  });

  it('user_id → SubjectRef', () => {
    const adapter = new LangFuseAdapter();
    const draft = adapter.translate({
      id: 'o',
      trace_id: 't',
      type: 'GENERATION',
      name: 'x',
      user_id: 'alice',
    });
    expect(draft.subject_ref).toEqual({ scheme: 'opaque', value: 'alice' });
  });

  it('no user_id → no SubjectRef', () => {
    const adapter = new LangFuseAdapter();
    const draft = adapter.translate({
      id: 'o',
      trace_id: 't',
      type: 'GENERATION',
      name: 'x',
    });
    expect(draft.subject_ref).toBeNull();
  });

  it('rejects non-Observation input', () => {
    const adapter = new LangFuseAdapter();
    expect(() => adapter.translate({ id: 'o' } as unknown as LangFuseObservation)).toThrow(
      AdapterTranslationError,
    );
  });

  it('pure function — same input same output', () => {
    const adapter = new LangFuseAdapter();
    const obs: LangFuseObservation = {
      id: 'o',
      trace_id: 't',
      type: 'GENERATION',
      name: 'x',
      start_time: NOW,
      end_time: NOW,
      input: { a: 1 },
    };
    expect(adapter.translate(obs)).toEqual(adapter.translate(obs));
  });

  // fromDict tests
  it('fromDict minimal', () => {
    const obs = LangFuseAdapter.fromDict({
      id: 'o-1',
      trace_id: 't-1',
      type: 'GENERATION',
    });
    expect(obs.id).toBe('o-1');
    expect(obs.type).toBe('GENERATION');
  });

  it('fromDict with user_id kwarg', () => {
    const obs = LangFuseAdapter.fromDict(
      { id: 'o', trace_id: 't', type: 'GENERATION' },
      { user_id: 'trace-user' },
    );
    expect(obs.user_id).toBe('trace-user');
  });

  it('fromDict missing required throws', () => {
    expect(() => LangFuseAdapter.fromDict({ id: 'x' })).toThrow(/missing required/);
  });

  it('fromDict parses ISO datetime', () => {
    const obs = LangFuseAdapter.fromDict({
      id: 'o',
      trace_id: 't',
      type: 'GENERATION',
      start_time: '2026-05-17T12:00:00Z',
      end_time: '2026-05-17T12:00:01Z',
    });
    expect(obs.start_time?.getTime()).toBe(NOW.getTime());
    expect(obs.end_time?.getTime()).toBe(NOW.getTime() + 1000);
  });

  it('fromDict bad metadata type throws', () => {
    expect(() =>
      LangFuseAdapter.fromDict({
        id: 'o',
        trace_id: 't',
        type: 'GENERATION',
        metadata: 'not a dict',
      }),
    ).toThrow(/metadata/);
  });

  it('runtime_name + schema_version locked', () => {
    const a = new LangFuseAdapter();
    expect(a.runtime_name).toBe('langfuse');
    expect(a.schema_version).toBe(1);
  });
});
