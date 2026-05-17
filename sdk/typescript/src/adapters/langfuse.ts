// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * LangFuse → Attestplane evidence-event adapter (TypeScript port of
 * `sdk/python/src/attestplane/adapters/langfuse.py`).
 *
 * Byte-identical translation semantics with the Python adapter.
 *
 * Pure function per GenericRuntimeAdapter contract: no I/O, no
 * LangFuse API calls.
 *
 * Trust boundary (ADR-0004 § 4): adapter consumes the public
 * LangFuse Observation shape; LangFuse / ClickHouse do not endorse
 * this adapter (see docs/policy/forbidden_claims.md § G).
 *
 * Redaction (ADR-0008 § Boundary anti-requirements):
 * - Raw input / output never copied to payload — only SHA-256 hashes.
 * - status_message truncated to 200 chars before placing in error_code.
 * - user_id (from parent Trace) wrapped in SubjectRef(scheme="opaque").
 *
 * Observation type → event_type mapping:
 *   GENERATION / SPAN / EVENT → tool_call_event with payload.kind set.
 *
 * Level → result_status mapping:
 *   ERROR → "ERROR"; everything else → "OK" (WARNING preserved as
 *   payload.level but not flipping status).
 */

import { createHash } from 'node:crypto';

import { AdapterTranslationError, GenericRuntimeAdapter } from '../adapters.js';
import { TOOL_CALL_EVENT } from '../event_types.js';
import { type EventDraft, makeEventDraft, makeSubjectRef } from '../types.js';

const KNOWN_OBSERVATION_TYPES = new Set(['GENERATION', 'SPAN', 'EVENT']);
const KNOWN_LEVELS = new Set(['DEFAULT', 'DEBUG', 'WARNING', 'ERROR']);

export interface LangFuseObservation {
  readonly id: string;
  readonly trace_id: string;
  readonly type: string; // GENERATION | SPAN | EVENT
  readonly name?: string | null;
  readonly start_time?: Date | null;
  readonly end_time?: Date | null;
  readonly input?: unknown;
  readonly output?: unknown;
  readonly level?: string | null;
  readonly metadata?: Record<string, unknown>;
  readonly status_message?: string | null;
  readonly model?: string | null;
  readonly user_id?: string | null;
}

function _canonicalReplacer(): (this: unknown, key: string, value: unknown) => unknown {
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
  const sorted = JSON.parse(JSON.stringify(value, _canonicalReplacer()));
  const compact = JSON.stringify(sorted);
  return createHash('sha256').update(compact, 'utf-8').digest('hex');
}

function _truncate(text: string, n = 200): string {
  if (text.length <= n) return text;
  return `${text.slice(0, n - 3)}...`;
}

function _levelToStatus(level: string | null | undefined): 'OK' | 'ERROR' {
  return level === 'ERROR' ? 'ERROR' : 'OK';
}

export class LangFuseAdapter extends GenericRuntimeAdapter<LangFuseObservation> {
  readonly runtime_name = 'langfuse';
  readonly schema_version = 1;

  translate(runtime_event: LangFuseObservation): EventDraft {
    if (
      typeof runtime_event !== 'object' ||
      runtime_event === null ||
      typeof (runtime_event as LangFuseObservation).id !== 'string' ||
      typeof (runtime_event as LangFuseObservation).trace_id !== 'string' ||
      typeof (runtime_event as LangFuseObservation).type !== 'string'
    ) {
      throw new AdapterTranslationError(
        `expected LangFuseObservation object, got ${
          runtime_event === null ? 'null' : typeof runtime_event
        }`,
      );
    }
    const obs = runtime_event;

    const kind = KNOWN_OBSERVATION_TYPES.has(obs.type) ? obs.type.toLowerCase() : 'unknown';
    const resultStatus = _levelToStatus(obs.level);

    const payload: Record<string, unknown> = {
      kind,
      tool_name: `langfuse.${kind}.${obs.name ?? 'unnamed'}`,
      tool_call_id: obs.id,
      result_status: resultStatus,
    };

    if (obs.input !== undefined && obs.input !== null) {
      payload.arguments_hash = _hashJson(obs.input);
    } else {
      // Schema requires arguments_hash always present; hash empty dict.
      payload.arguments_hash = _hashJson({});
    }

    if (obs.output !== undefined && obs.output !== null) {
      payload.result_hash = _hashJson(obs.output);
    }

    if (obs.start_time != null && obs.end_time != null) {
      const ms = obs.end_time.getTime() - obs.start_time.getTime();
      payload.latency_ms = Math.trunc(ms);
    }

    if (obs.status_message && resultStatus === 'ERROR') {
      payload.error_code = _truncate(obs.status_message);
    }

    if (obs.model) {
      payload.tool_version = obs.model;
    }

    if (obs.level && KNOWN_LEVELS.has(obs.level) && obs.level !== 'DEFAULT') {
      payload.level = obs.level;
    }

    return makeEventDraft({
      event_type: TOOL_CALL_EVENT,
      actor: `langfuse://${kind}/${obs.name ?? 'unnamed'}`,
      payload,
      subject_ref: obs.user_id ? makeSubjectRef('opaque', obs.user_id) : null,
      session_id: obs.trace_id,
    });
  }

  static fromDict(
    raw: Record<string, unknown>,
    options?: { readonly user_id?: string },
  ): LangFuseObservation {
    const required = ['id', 'trace_id', 'type'] as const;
    const missing = required.filter((k) => !(k in raw));
    if (missing.length > 0) {
      throw new AdapterTranslationError(
        `LangFuse observation dict missing required fields: ${JSON.stringify(missing.sort())}`,
      );
    }

    const parseDt = (value: unknown): Date | null => {
      if (value == null) return null;
      if (value instanceof Date) return value;
      if (typeof value === 'string') {
        const normalized = value.endsWith('Z') ? value.replace('Z', '+00:00') : value;
        const d = new Date(normalized);
        if (Number.isNaN(d.getTime())) {
          throw new AdapterTranslationError(`unparsable datetime ${JSON.stringify(value)}`);
        }
        return d;
      }
      throw new AdapterTranslationError(`datetime field has type ${typeof value}`);
    };

    const metadata = (raw.metadata as Record<string, unknown> | undefined) ?? {};
    if (typeof metadata !== 'object' || Array.isArray(metadata)) {
      throw new AdapterTranslationError('metadata must be an object');
    }

    return {
      id: String(raw.id),
      trace_id: String(raw.trace_id),
      type: String(raw.type),
      name: (raw.name as string | null) ?? null,
      start_time: parseDt(raw.start_time),
      end_time: parseDt(raw.end_time),
      input: raw.input,
      output: raw.output,
      level: (raw.level as string | null) ?? null,
      metadata,
      status_message: (raw.status_message as string | null) ?? null,
      model: (raw.model as string | null) ?? null,
      user_id: options?.user_id ?? null,
    };
  }
}
