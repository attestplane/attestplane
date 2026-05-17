// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Tests for src/adapters/langsmith.ts — TypeScript port of
 * sdk/python/tests/adapters/test_langsmith.py.
 */

import { createHash } from 'node:crypto';

import { describe, expect, it } from 'vitest';

import { AdapterTranslationError } from '../../src/adapters.js';
import {
  LangSmithAdapter,
  type LangSmithRun,
} from '../../src/adapters/langsmith.js';
import { TOOL_CALL_EVENT } from '../../src/event_types.js';

const NOW = new Date('2026-05-17T12:00:00.000Z');

function hashJson(value: unknown): string {
  // Match Python's json.dumps(sort_keys=True, separators=(",",":"), default=str)
  // by sorting keys and using compact stringification.
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
  const compact = JSON.stringify(sortDeep(value));
  return createHash('sha256').update(compact, 'utf-8').digest('hex');
}

describe('LangSmithAdapter', () => {
  it('translates a tool run', () => {
    const adapter = new LangSmithAdapter();
    const run: LangSmithRun = {
      id: 'run-1',
      name: 'search_web',
      run_type: 'tool',
      start_time: NOW,
      end_time: NOW,
      inputs: { query: 'weather in tokyo' },
      outputs: { result: 'sunny, 22C' },
      trace_id: 'trace-abc',
    };
    const draft = adapter.translate(run);
    expect(draft.event_type).toBe(TOOL_CALL_EVENT);
    expect(draft.payload['kind']).toBe('tool');
    expect(draft.payload['tool_name']).toBe('langsmith.tool.search_web');
    expect(draft.payload['tool_call_id']).toBe('run-1');
    expect(draft.payload['result_status']).toBe('OK');
    expect(draft.payload['arguments_hash']).toBe(hashJson({ query: 'weather in tokyo' }));
    expect(draft.payload['result_hash']).toBe(hashJson({ result: 'sunny, 22C' }));
    expect(draft.session_id).toBe('trace-abc');
  });

  it('redacts inputs and outputs (no raw secret in payload)', () => {
    const adapter = new LangSmithAdapter();
    const secret = 'secret_api_key=sk-abc123xyz';
    const run: LangSmithRun = {
      id: 'r', name: 'tool', run_type: 'tool',
      start_time: NOW, end_time: NOW,
      inputs: { sensitive: secret },
      outputs: { result: secret },
    };
    const draft = adapter.translate(run);
    const payloadStr = JSON.stringify(draft.payload);
    expect(payloadStr).not.toContain(secret);
    expect(draft.payload['arguments_hash']).toBeDefined();
    expect(draft.payload['result_hash']).toBeDefined();
  });

  it('error run marks status ERROR', () => {
    const adapter = new LangSmithAdapter();
    const run: LangSmithRun = {
      id: 'r', name: 'tool', run_type: 'tool',
      start_time: NOW, end_time: NOW,
      inputs: {},
      error: 'ToolExecutionError: timeout after 30s',
    };
    const draft = adapter.translate(run);
    expect(draft.payload['result_status']).toBe('ERROR');
    expect(draft.payload['error_code']).toContain('timeout');
  });

  it('long error truncated to 200 chars', () => {
    const adapter = new LangSmithAdapter();
    const run: LangSmithRun = {
      id: 'r', name: 'tool', run_type: 'tool',
      start_time: NOW, end_time: NOW,
      inputs: {},
      error: 'X'.repeat(5000),
    };
    const draft = adapter.translate(run);
    expect((draft.payload['error_code'] as string).length).toBeLessThanOrEqual(200);
  });

  it('user_id pseudonymized via SubjectRef', () => {
    const adapter = new LangSmithAdapter();
    const run: LangSmithRun = {
      id: 'r', name: 'tool', run_type: 'tool',
      start_time: NOW, inputs: {},
      end_user_id: 'user_42',
    };
    const draft = adapter.translate(run);
    expect(draft.subject_ref).toEqual({ scheme: 'opaque', value: 'user_42' });
  });

  it('unknown run_type tagged "unknown"', () => {
    const adapter = new LangSmithAdapter();
    const run: LangSmithRun = {
      id: 'r', name: 'x', run_type: 'weirdcustomtype',
      start_time: NOW, inputs: {},
    };
    const draft = adapter.translate(run);
    expect(draft.payload['kind']).toBe('unknown');
  });

  it('latency_ms populated when end_time present', () => {
    const adapter = new LangSmithAdapter();
    const end = new Date(NOW.getTime() + 1500);
    const run: LangSmithRun = {
      id: 'r', name: 't', run_type: 'tool',
      start_time: NOW, end_time: end, inputs: {},
    };
    const draft = adapter.translate(run);
    expect(draft.payload['latency_ms']).toBe(1500);
  });

  it('session_id falls back to run.id', () => {
    const adapter = new LangSmithAdapter();
    const run: LangSmithRun = {
      id: 'solo', name: 't', run_type: 'tool',
      start_time: NOW, inputs: {},
    };
    expect(adapter.translate(run).session_id).toBe('solo');
  });

  it('parent_run_id → reference_db_ref', () => {
    const adapter = new LangSmithAdapter();
    const run: LangSmithRun = {
      id: 'child', name: 't', run_type: 'tool',
      start_time: NOW, inputs: {}, parent_run_id: 'parent-1',
    };
    expect(adapter.translate(run).reference_db_ref).toBe('parent-1');
  });

  it('rejects non-LangSmithRun object', () => {
    const adapter = new LangSmithAdapter();
    expect(() => adapter.translate('not a run' as unknown as LangSmithRun)).toThrow(
      AdapterTranslationError,
    );
  });

  it('pure function — same input same output', () => {
    const adapter = new LangSmithAdapter();
    const run: LangSmithRun = {
      id: 'x', name: 't', run_type: 'tool',
      start_time: NOW, end_time: NOW, inputs: { a: 1 },
    };
    expect(adapter.translate(run)).toEqual(adapter.translate(run));
  });

  // fromDict tests
  it('fromDict accepts minimal valid input', () => {
    const run = LangSmithAdapter.fromDict({
      id: 'r1', name: 'tool_x', run_type: 'tool',
      start_time: '2026-05-17T12:00:00Z',
    });
    expect(run.id).toBe('r1');
    expect(run.start_time.getTime()).toBe(NOW.getTime());
  });

  it('fromDict missing required field throws', () => {
    expect(() => LangSmithAdapter.fromDict({ id: 'x', name: 'y' })).toThrow(
      /missing required/,
    );
  });

  it('fromDict bad datetime throws', () => {
    expect(() =>
      LangSmithAdapter.fromDict({
        id: 'x', name: 'y', run_type: 'tool', start_time: 'not-a-date',
      }),
    ).toThrow(/unparseable/);
  });

  it('fromDict extracts user_id from metadata', () => {
    const run = LangSmithAdapter.fromDict({
      id: 'x', name: 'y', run_type: 'tool',
      start_time: '2026-05-17T12:00:00Z',
      metadata: { user_id: 'u-42' },
    });
    expect(run.end_user_id).toBe('u-42');
  });

  it('runtime_name + schema_version locked', () => {
    const a = new LangSmithAdapter();
    expect(a.runtime_name).toBe('langsmith');
    expect(a.schema_version).toBe(1);
  });
});
