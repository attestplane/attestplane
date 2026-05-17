// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * High-level proof-bundle verifier (TypeScript port of
 * `sdk/python/src/attestplane/verifier.py`).
 *
 * Takes a parsed bundle object, performs a lightweight shape check
 * (sufficient to safely rehydrate; callers needing full JSON Schema
 * validation can run any standard validator against
 * `schemas/v1/proof_bundle.schema.json`), rehydrates the contained
 * events, re-walks the chain with `verifyChain`, and returns a
 * `BundleVerificationResult`.
 *
 * Pure with respect to the bundle: no mutation, no signing, no I/O
 * other than optionally reading a file when using `verifyProofBundleFile`.
 */

import { promises as fs } from 'node:fs';

import { type VerificationResult, verifyChain } from './hashchain.js';
import type {
  ProofBundle,
  SerializedAuditEvent,
  SerializedChainedEvent,
  SerializedSubjectRef,
} from './proof_bundle.js';
import type { AuditEvent, ChainedEvent, SubjectRef } from './types.js';

export class BundleVerificationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'BundleVerificationError';
  }
}

export class BundleSchemaError extends BundleVerificationError {
  constructor(message: string) {
    super(message);
    this.name = 'BundleSchemaError';
  }
}

export interface BundleVerificationResult {
  readonly ok: boolean;
  readonly chain_result: VerificationResult;
  readonly bundle_reported_ok: boolean;
  readonly agreement: boolean;
  readonly event_count: number;
  readonly bundle_version: number;
  readonly chain_id: string;
  readonly head_hash_hex: string;
}

export function shortSummary(result: BundleVerificationResult): string {
  if (result.ok) {
    return (
      `OK chain_id='${result.chain_id}' events=${result.event_count} ` +
      `head=${result.head_hash_hex.slice(0, 16)}…`
    );
  }
  const bad = result.chain_result.first_bad_index;
  return (
    `FAIL chain_id='${result.chain_id}' events=${result.event_count} ` +
    `first_bad_index=${bad} reason=${JSON.stringify(result.chain_result.reason)} ` +
    `agreement=${result.agreement}`
  );
}

const REQUIRED_TOP_LEVEL = [
  'bundle_version',
  'chain_metadata',
  'events',
  'verification_report',
  'forbidden_fields',
] as const;

const REQUIRED_CHAIN_METADATA = [
  'chain_id',
  'schema_version',
  'genesis_hash_hex',
  'head_hash_hex',
  'head_seq',
  'producer_runtime',
] as const;

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function validateShape(raw: unknown): asserts raw is ProofBundle {
  if (!isPlainObject(raw)) {
    throw new BundleSchemaError(
      `bundle must be a JSON object, got ${raw === null ? 'null' : typeof raw}`,
    );
  }
  const missing = REQUIRED_TOP_LEVEL.filter((k) => !(k in raw));
  if (missing.length > 0) {
    throw new BundleSchemaError(`bundle missing required fields: ${JSON.stringify(missing)}`);
  }
  if (raw.bundle_version !== 1) {
    throw new BundleSchemaError(
      `unsupported bundle_version=${JSON.stringify(raw.bundle_version)}; this verifier handles version 1 only`,
    );
  }
  const cm = raw.chain_metadata;
  if (!isPlainObject(cm)) {
    throw new BundleSchemaError('chain_metadata must be a JSON object');
  }
  const missingCm = REQUIRED_CHAIN_METADATA.filter((k) => !(k in cm));
  if (missingCm.length > 0) {
    throw new BundleSchemaError(
      `chain_metadata missing required fields: ${JSON.stringify(missingCm)}`,
    );
  }
  if (!Array.isArray(raw.events)) {
    throw new BundleSchemaError('events must be an array');
  }
  if (!isPlainObject(raw.verification_report)) {
    throw new BundleSchemaError('verification_report must be a JSON object');
  }
  if (!Array.isArray(raw.forbidden_fields)) {
    throw new BundleSchemaError('forbidden_fields must be an array');
  }
}

function hexToBytes(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) {
    throw new BundleSchemaError(`hex string has odd length: ${hex.length}`);
  }
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    const byte = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    if (Number.isNaN(byte)) {
      throw new BundleSchemaError(
        `invalid hex byte at position ${i * 2}: ${hex.slice(i * 2, i * 2 + 2)}`,
      );
    }
    out[i] = byte;
  }
  return out;
}

function deserializeSubject(raw: SerializedSubjectRef | null | undefined): SubjectRef | null {
  if (raw == null) return null;
  return { scheme: raw.scheme, value: raw.value };
}

function deserializeTimestamp(s: string): Date {
  // Accept "YYYY-MM-DDThh:mm:ss.uuuuuuZ" with 6-digit microsecond precision.
  // JavaScript Date is millisecond-precision; we drop the last three digits
  // and round-trip through the standard ISO 8601 parser.
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})\d{3}Z$/.exec(s);
  if (!match) {
    throw new BundleSchemaError(`bad timestamp format: ${JSON.stringify(s)}`);
  }
  const date = new Date(`${match[1]}Z`);
  if (Number.isNaN(date.getTime())) {
    throw new BundleSchemaError(`unparsable timestamp: ${JSON.stringify(s)}`);
  }
  return date;
}

function deserializeAuditEvent(raw: SerializedAuditEvent): AuditEvent {
  return {
    schema_version: raw.schema_version,
    event_id: raw.event_id,
    timestamp: deserializeTimestamp(raw.timestamp),
    event_type: raw.event_type,
    actor: raw.actor,
    payload: raw.payload,
    subject_ref: deserializeSubject(raw.subject_ref),
    session_id: raw.session_id,
    reference_db_ref: raw.reference_db_ref,
    matched_input_ref: raw.matched_input_ref,
    human_verifier: deserializeSubject(raw.human_verifier),
  };
}

function rehydrateEvents(rawEvents: readonly SerializedChainedEvent[]): ChainedEvent[] {
  const chain: ChainedEvent[] = [];
  for (let i = 0; i < rawEvents.length; i++) {
    const raw = rawEvents[i] as SerializedChainedEvent;
    try {
      chain.push({
        seq: raw.seq,
        prev_hash: hexToBytes(raw.prev_hash_hex),
        event_hash: hexToBytes(raw.event_hash_hex),
        event: deserializeAuditEvent(raw.event),
      });
    } catch (exc) {
      if (exc instanceof BundleSchemaError) {
        throw new BundleSchemaError(`events[${i}]: ${exc.message}`);
      }
      throw exc;
    }
  }
  return chain;
}

export function verifyProofBundle(raw: unknown): BundleVerificationResult {
  validateShape(raw);
  const bundle = raw;
  const events = rehydrateEvents(bundle.events);
  const chainResult = verifyChain(events);
  const bundleReportedOk = Boolean(bundle.verification_report.ok);
  const agreement = bundleReportedOk === chainResult.ok;

  return {
    ok: chainResult.ok && agreement,
    chain_result: chainResult,
    bundle_reported_ok: bundleReportedOk,
    agreement,
    event_count: events.length,
    bundle_version: bundle.bundle_version,
    chain_id: bundle.chain_metadata.chain_id,
    head_hash_hex: bundle.chain_metadata.head_hash_hex,
  };
}

export async function verifyProofBundleFile(path: string): Promise<BundleVerificationResult> {
  let text: string;
  try {
    text = await fs.readFile(path, 'utf-8');
  } catch (exc) {
    if (exc instanceof Error && 'code' in exc && (exc as NodeJS.ErrnoException).code === 'ENOENT') {
      throw new BundleVerificationError(`bundle file not found: ${path}`);
    }
    throw exc;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (exc) {
    const msg = exc instanceof Error ? exc.message : String(exc);
    throw new BundleSchemaError(`${path}: not valid JSON: ${msg}`);
  }
  return verifyProofBundle(parsed);
}
