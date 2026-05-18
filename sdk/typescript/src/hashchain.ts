// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Pure-function hash-chain primitives for the Attestplane substrate.
 *
 * Mirrors `sdk/python/src/attestplane/hashchain.py`. Pure: no I/O, no global
 * state, no time reads. Container responsibility lives in `substrate.ts`.
 */

import { createHash } from 'node:crypto';
import { v7 as uuidv7 } from 'uuid';

import { canonicalize } from './canonical.js';
import type { AuditEvent, ChainHead, ChainedEvent, EventDraft } from './types.js';

export const SCHEMA_VERSION = 1;
export const GENESIS_HASH: Uint8Array = new Uint8Array(32);

export interface VerificationResult {
  readonly ok: boolean;
  readonly first_bad_index: number | null;
  readonly reason: string | null;
}

export function genesisHead(): ChainHead {
  return { seq: -1, event_hash: GENESIS_HASH };
}

export function hashEvent(event: AuditEvent): Uint8Array {
  return new Uint8Array(createHash('sha256').update(canonicalizeAuditEvent(event)).digest());
}

export function canonicalizeAuditEvent(event: AuditEvent): Uint8Array {
  return canonicalize(canonicalEvent(event));
}

export interface ChainExtendOptions {
  readonly now: Date;
  readonly event_id?: string;
}

export function chainExtend(
  tip: ChainHead,
  draft: EventDraft,
  options: ChainExtendOptions,
): ChainedEvent {
  if (Number.isNaN(options.now.getTime())) {
    throw new Error('chainExtend requires a valid Date for now');
  }
  const event_id = options.event_id ?? uuidv7();
  const event: AuditEvent = {
    schema_version: SCHEMA_VERSION,
    event_id,
    timestamp: options.now,
    event_type: draft.event_type,
    actor: draft.actor,
    payload: draft.payload,
    subject_ref: draft.subject_ref,
    session_id: draft.session_id,
    reference_db_ref: draft.reference_db_ref,
    matched_input_ref: draft.matched_input_ref,
    human_verifier: draft.human_verifier,
  };
  const event_hash = hashEvent(event);
  return {
    seq: tip.seq + 1,
    prev_hash: tip.event_hash,
    event_hash,
    event,
  };
}

export function verifyChain(events: readonly ChainedEvent[]): VerificationResult {
  let expectedTip = genesisHead();
  for (let i = 0; i < events.length; i++) {
    const item = events[i] as ChainedEvent;
    if (item.seq !== i) {
      return {
        ok: false,
        first_bad_index: i,
        reason: `seq mismatch at index ${i}: got ${item.seq}, expected ${i}`,
      };
    }
    if (!bytesEqual(item.prev_hash, expectedTip.event_hash)) {
      return {
        ok: false,
        first_bad_index: i,
        reason: `prev_hash mismatch at seq ${i}`,
      };
    }
    const recomputed = hashEvent(item.event);
    if (!bytesEqual(recomputed, item.event_hash)) {
      return {
        ok: false,
        first_bad_index: i,
        reason: `event_hash mismatch at seq ${i}`,
      };
    }
    expectedTip = { seq: item.seq, event_hash: item.event_hash };
  }
  return { ok: true, first_bad_index: null, reason: null };
}

export function headOf(events: readonly ChainedEvent[]): ChainHead {
  if (events.length === 0) return genesisHead();
  const last = events[events.length - 1] as ChainedEvent;
  return { seq: last.seq, event_hash: last.event_hash };
}

function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

function canonicalEvent(event: AuditEvent): Record<string, unknown> {
  const timestamp = (event as { readonly timestamp: unknown }).timestamp;
  return {
    ...event,
    timestamp:
      timestamp instanceof Date ? formatDateUtcMicroseconds(timestamp, '$.timestamp') : timestamp,
  };
}

function formatDateUtcMicroseconds(value: Date, path: string): string {
  const ms = value.getTime();
  if (Number.isNaN(ms)) {
    throw new Error(`${path}: invalid Date (NaN time value)`);
  }
  const yyyy = value.getUTCFullYear().toString().padStart(4, '0');
  const mm = (value.getUTCMonth() + 1).toString().padStart(2, '0');
  const dd = value.getUTCDate().toString().padStart(2, '0');
  const hh = value.getUTCHours().toString().padStart(2, '0');
  const mi = value.getUTCMinutes().toString().padStart(2, '0');
  const ss = value.getUTCSeconds().toString().padStart(2, '0');
  const milli = value.getUTCMilliseconds().toString().padStart(3, '0');
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}:${ss}.${milli}000Z`;
}
