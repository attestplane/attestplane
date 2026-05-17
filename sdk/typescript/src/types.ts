// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Core data types for the Attestplane substrate (TypeScript SDK).
 *
 * Field names are deliberately `snake_case` to match the Python SDK's wire
 * format byte-for-byte. The canonical event-hash includes the field names
 * (per RFC 8785 / restricted JSON profile of ADR-0002), so any rename here
 * would break cross-language conformance against the frozen
 * `sdk/python/tests/conformance/vectors.json`.
 *
 * This is a load-bearing convention. Do not switch to camelCase.
 */

export type SubjectScheme = 'sha256_salted' | 'opaque' | 'none';

export interface SubjectRef {
  readonly scheme: SubjectScheme;
  readonly value: string;
}

export function makeSubjectRef(scheme: SubjectScheme, value: string): SubjectRef {
  if (scheme === 'none' && value !== '') {
    throw new Error("SubjectRef scheme 'none' requires empty value");
  }
  if (scheme !== 'none' && value.length === 0) {
    throw new Error(`SubjectRef scheme '${scheme}' requires non-empty value`);
  }
  return { scheme, value };
}

export interface EventDraft {
  readonly event_type: string;
  readonly actor: string;
  readonly payload: Record<string, unknown>;
  readonly subject_ref: SubjectRef | null;
  readonly session_id: string | null;
  readonly reference_db_ref: string | null;
  readonly matched_input_ref: string | null;
  readonly human_verifier: SubjectRef | null;
}

export interface EventDraftInput {
  event_type: string;
  actor: string;
  payload?: Record<string, unknown>;
  subject_ref?: SubjectRef | null;
  session_id?: string | null;
  reference_db_ref?: string | null;
  matched_input_ref?: string | null;
  human_verifier?: SubjectRef | null;
}

export function makeEventDraft(input: EventDraftInput): EventDraft {
  if (!input.event_type) {
    throw new Error('EventDraft.event_type must be non-empty');
  }
  if (!input.actor) {
    throw new Error('EventDraft.actor must be non-empty');
  }
  return {
    event_type: input.event_type,
    actor: input.actor,
    payload: input.payload ?? {},
    subject_ref: input.subject_ref ?? null,
    session_id: input.session_id ?? null,
    reference_db_ref: input.reference_db_ref ?? null,
    matched_input_ref: input.matched_input_ref ?? null,
    human_verifier: input.human_verifier ?? null,
  };
}

export interface AuditEvent {
  readonly schema_version: number;
  readonly event_id: string;
  readonly timestamp: Date;
  readonly event_type: string;
  readonly actor: string;
  readonly payload: Record<string, unknown>;
  readonly subject_ref: SubjectRef | null;
  readonly session_id: string | null;
  readonly reference_db_ref: string | null;
  readonly matched_input_ref: string | null;
  readonly human_verifier: SubjectRef | null;
}

export interface ChainedEvent {
  readonly seq: number;
  readonly prev_hash: Uint8Array;
  readonly event_hash: Uint8Array;
  readonly event: AuditEvent;
}

export interface ChainHead {
  readonly seq: number;
  readonly event_hash: Uint8Array;
}
