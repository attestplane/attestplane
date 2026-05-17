// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * LangSmith → Attestplane evidence-event adapter (TypeScript port of
 * `sdk/python/src/attestplane/adapters/langsmith.py`).
 *
 * Byte-identical translation semantics with the Python adapter:
 * given the same LangSmith Run, both adapters produce the same
 * EventDraft fields (event_type, actor, payload, subject_ref,
 * session_id, reference_db_ref).
 *
 * Pure function per GenericRuntimeAdapter contract: no I/O, no
 * LangSmith API calls.
 *
 * Trust boundary (ADR-0004 § 4): adapter consumes the public
 * LangSmith Run shape, not LangChain proprietary code. LangChain
 * does not endorse this adapter; see docs/policy/forbidden_claims.md
 * § G.
 *
 * Redaction (ADR-0008 § Boundary anti-requirements):
 * - Raw inputs / outputs are NEVER copied to payload — only SHA-256
 *   hashes go in `arguments_hash` / `result_hash`.
 * - Error strings are truncated to 200 chars to limit PII leakage.
 * - end_user_id (from LangSmith metadata.user_id) is wrapped in
 *   SubjectRef(scheme="opaque").
 *
 * Run type → event_type mapping is identical to the Python adapter:
 * all run_types map to `tool_call_event` in v1; payload.kind carries
 * the LangSmith run_type for downstream filtering.
 */

import { createHash } from 'node:crypto';

import { AdapterTranslationError, GenericRuntimeAdapter } from '../adapters.js';
import { TOOL_CALL_EVENT } from '../event_types.js';
import { makeEventDraft, makeSubjectRef, type EventDraft } from '../types.js';

const KNOWN_RUN_TYPES = new Set([
  'tool', 'llm', 'chain', 'retriever',
  'prompt', 'parser', 'embedding',
]);

export interface LangSmithRun {
  readonly id: string;
  readonly name: string;
  readonly run_type: string;
  readonly start_time: Date;
  readonly end_time?: Date | null;
  readonly inputs?: Record<string, unknown>;
  readonly outputs?: Record<string, unknown> | null;
  readonly error?: string | null;
  readonly trace_id?: string | null;
  readonly parent_run_id?: string | null;
  readonly status?: string | null;
  readonly tags?: readonly string[];
  readonly metadata?: Record<string, unknown>;
  readonly end_user_id?: string | null;
}

function _canonicalReplacer(): (this: unknown, key: string, value: unknown) => unknown {
  // sort_keys + default=str equivalent (matches Python's json.dumps
  // with sort_keys=True, separators=(",",":"), default=str).
  return function (this: unknown, _key: string, value: unknown): unknown {
    if (value === undefined) return undefined;
    if (value instanceof Date) return value.toISOString();
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      const sorted: Record<string, unknown> = {};
      const obj = value as Record<string, unknown>;
      for (const k of Object.keys(obj).sort()) {
        sorted[k] = obj[k];
      }
      return sorted;
    }
    return value;
  };
}

function _hashJson(value: unknown): string {
  // Match Python: json.dumps(value, sort_keys=True, separators=(",",":"), default=str)
  // JS JSON.stringify by default uses no separators; we need to mimic compact form.
  // The canonical_replacer above sorts keys; we then re-emit with the no-space
  // separator form by passing the result through a second stringify.
  const sorted = JSON.parse(JSON.stringify(value, _canonicalReplacer()));
  const compact = JSON.stringify(sorted);
  return createHash('sha256').update(compact, 'utf-8').digest('hex');
}

function _truncate(text: string, n = 200): string {
  if (text.length <= n) return text;
  return text.slice(0, n - 3) + '...';
}

export class LangSmithAdapter extends GenericRuntimeAdapter<LangSmithRun> {
  readonly runtime_name = 'langsmith';
  readonly schema_version = 1;

  translate(runtime_event: LangSmithRun): EventDraft {
    if (
      typeof runtime_event !== 'object'
      || runtime_event === null
      || typeof (runtime_event as LangSmithRun).id !== 'string'
      || typeof (runtime_event as LangSmithRun).run_type !== 'string'
    ) {
      throw new AdapterTranslationError(
        `expected LangSmithRun object, got ${runtime_event === null ? 'null' : typeof runtime_event}`,
      );
    }

    const run = runtime_event;

    let resultStatus: string;
    if (run.error) {
      resultStatus = 'ERROR';
    } else {
      resultStatus = 'OK';
    }

    const kind = KNOWN_RUN_TYPES.has(run.run_type) ? run.run_type : 'unknown';

    const inputs = run.inputs ?? {};
    const payload: Record<string, unknown> = {
      kind,
      tool_name: `langsmith.${kind}.${run.name}`,
      tool_call_id: run.id,
      arguments_hash: _hashJson(inputs),
      result_status: resultStatus,
    };
    if (run.outputs != null) {
      payload['result_hash'] = _hashJson(run.outputs);
    }
    if (run.end_time != null) {
      const ms = run.end_time.getTime() - run.start_time.getTime();
      payload['latency_ms'] = Math.trunc(ms);
    }
    if (run.error) {
      payload['error_code'] = _truncate(run.error);
    }
    if (run.tags && run.tags.length > 0) {
      payload['tags'] = [...run.tags];
    }

    const sessionId = run.trace_id ?? run.id;

    return makeEventDraft({
      event_type: TOOL_CALL_EVENT,
      actor: `langsmith://${run.run_type}/${run.name}`,
      payload,
      subject_ref: run.end_user_id ? makeSubjectRef('opaque', run.end_user_id) : null,
      session_id: sessionId,
      reference_db_ref: run.parent_run_id ?? null,
    });
  }

  static fromDict(raw: Record<string, unknown>): LangSmithRun {
    const required = ['id', 'name', 'run_type', 'start_time'] as const;
    const missing = required.filter((k) => !(k in raw));
    if (missing.length > 0) {
      throw new AdapterTranslationError(
        `LangSmith run dict missing required fields: ${JSON.stringify(missing.sort())}`,
      );
    }

    const parseDt = (value: unknown): Date => {
      if (value instanceof Date) return value;
      if (typeof value === 'string') {
        const normalized = value.endsWith('Z')
          ? value.replace('Z', '+00:00')
          : value;
        const d = new Date(normalized);
        if (Number.isNaN(d.getTime())) {
          throw new AdapterTranslationError(`unparseable datetime ${JSON.stringify(value)}`);
        }
        return d;
      }
      throw new AdapterTranslationError(
        `datetime field has type ${typeof value}, expected Date or ISO string`,
      );
    };

    const metadata = (raw['metadata'] as Record<string, unknown> | undefined) ?? {};
    if (typeof metadata !== 'object' || Array.isArray(metadata)) {
      throw new AdapterTranslationError('metadata must be an object');
    }

    const tagsRaw = raw['tags'];
    if (tagsRaw !== undefined && tagsRaw !== null && !Array.isArray(tagsRaw)) {
      throw new AdapterTranslationError('tags must be an array');
    }
    const tags = Array.isArray(tagsRaw)
      ? tagsRaw.map((t) => String(t))
      : [];

    return {
      id: String(raw['id']),
      name: String(raw['name']),
      run_type: String(raw['run_type']),
      start_time: parseDt(raw['start_time']),
      end_time: raw['end_time'] ? parseDt(raw['end_time']) : null,
      inputs: (raw['inputs'] as Record<string, unknown>) ?? {},
      outputs: (raw['outputs'] as Record<string, unknown> | null) ?? null,
      error: (raw['error'] as string | null) ?? null,
      trace_id: (raw['trace_id'] as string | null) ?? null,
      parent_run_id: (raw['parent_run_id'] as string | null) ?? null,
      status: (raw['status'] as string | null) ?? null,
      tags,
      metadata,
      end_user_id: typeof metadata['user_id'] === 'string' ? metadata['user_id'] : null,
    };
  }
}
