// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Proof-bundle export and auditor-export builders (TypeScript port of
 * `sdk/python/src/attestplane/proof_bundle.py`).
 *
 * The bundle shape matches `schemas/v1/proof_bundle.schema.json` exactly,
 * and the auditor export matches `schemas/v1/auditor_export.schema.json`.
 * Cross-language byte-stable: a chain produced by the Python SDK and a
 * chain produced by the TypeScript SDK that go through the same builder
 * inputs produce the same proof-bundle dict.
 */

import { headOf, SCHEMA_VERSION, verifyChain } from './hashchain.js';
import type { ChainedEvent, SubjectRef } from './types.js';
import { VERSION as _SDK_VERSION } from './index_version.js';

export const DEFAULT_FORBIDDEN_FIELDS: readonly string[] = [
  'customer_names',
  'person_names',
  'pii',
  'raw_documents',
  'contracts',
  'scripts',
  'tickets',
  'emails',
  'secrets',
  'tokens',
  'jwts',
  'private_keys',
  'raw_audit_payloads',
];

export type ImplementationStatus =
  | 'mapping_target'
  | 'designed_toward'
  | 'field_supported'
  | 'verified_in_test';

export interface FrameworkMapping {
  readonly obligation_id: string;
  readonly evidence_event_indexes: readonly number[];
  readonly implementation_status_at_bundle_time: ImplementationStatus;
}

export interface ProofBundleBuilderInput {
  readonly chain_id: string;
  readonly producer_runtime: string;
  readonly forbidden_fields?: readonly string[];
  readonly anchor_ref?: string | null;
}

export interface ProofBundle {
  readonly bundle_version: 1;
  readonly chain_metadata: {
    readonly chain_id: string;
    readonly schema_version: number;
    readonly genesis_hash_hex: string;
    readonly head_hash_hex: string;
    readonly head_seq: number;
    readonly producer_runtime: string;
    readonly evidence_taxonomy_version: 1;
    readonly anchor_ref?: string;
  };
  readonly events: readonly SerializedChainedEvent[];
  readonly verification_report: {
    readonly ok: boolean;
    readonly first_bad_index: number | null;
    readonly reason: string | null;
    readonly verified_at: string;
    readonly verifier_version: string;
    readonly verification_method: 'canonical-bytes-walk' | 'canonical-bytes-walk+anchor';
  };
  readonly framework_mappings: readonly FrameworkMapping[];
  readonly forbidden_fields: readonly string[];
}

export interface SerializedSubjectRef {
  readonly scheme: 'sha256_salted' | 'opaque' | 'none';
  readonly value: string;
}

export interface SerializedAuditEvent {
  readonly schema_version: number;
  readonly event_id: string;
  readonly timestamp: string;
  readonly event_type: string;
  readonly actor: string;
  readonly payload: Record<string, unknown>;
  readonly subject_ref: SerializedSubjectRef | null;
  readonly session_id: string | null;
  readonly reference_db_ref: string | null;
  readonly matched_input_ref: string | null;
  readonly human_verifier: SerializedSubjectRef | null;
}

export interface SerializedChainedEvent {
  readonly seq: number;
  readonly prev_hash_hex: string;
  readonly event_hash_hex: string;
  readonly event: SerializedAuditEvent;
}

function bytesToHex(bytes: Uint8Array): string {
  let out = '';
  for (let i = 0; i < bytes.length; i++) {
    const v = (bytes[i] as number).toString(16).padStart(2, '0');
    out += v;
  }
  return out;
}

function formatTimestampMicros(d: Date): string {
  // ISO date with 6-digit microsecond precision and literal Z.
  // JavaScript Date is millisecond-precision; we right-pad three zeros.
  const isoMs = d.toISOString(); // "YYYY-MM-DDThh:mm:ss.sssZ"
  // Replace ".sssZ" with ".sss000Z" to widen to microseconds.
  return isoMs.replace(/\.(\d{3})Z$/, '.$1000Z');
}

function serializeSubject(ref: SubjectRef | null | undefined): SerializedSubjectRef | null {
  if (ref == null) return null;
  return { scheme: ref.scheme, value: ref.value };
}

export function serializeChainedEvent(event: ChainedEvent): SerializedChainedEvent {
  return {
    seq: event.seq,
    prev_hash_hex: bytesToHex(event.prev_hash),
    event_hash_hex: bytesToHex(event.event_hash),
    event: {
      schema_version: event.event.schema_version,
      event_id: event.event.event_id,
      timestamp: formatTimestampMicros(event.event.timestamp),
      event_type: event.event.event_type,
      actor: event.event.actor,
      payload: event.event.payload,
      subject_ref: serializeSubject(event.event.subject_ref),
      session_id: event.event.session_id,
      reference_db_ref: event.event.reference_db_ref,
      matched_input_ref: event.event.matched_input_ref,
      human_verifier: serializeSubject(event.event.human_verifier),
    },
  };
}

/**
 * Accumulator for one proof-bundle build.
 *
 * Not thread-safe — create one per bundle.
 */
export class ProofBundleBuilder {
  private readonly _chain_id: string;
  private readonly _producer_runtime: string;
  private readonly _forbidden_fields: readonly string[];
  private readonly _anchor_ref: string | null;
  private readonly _events: ChainedEvent[] = [];
  private readonly _framework_mappings: FrameworkMapping[] = [];

  constructor(input: ProofBundleBuilderInput) {
    this._chain_id = input.chain_id;
    this._producer_runtime = input.producer_runtime;
    this._forbidden_fields = input.forbidden_fields ?? DEFAULT_FORBIDDEN_FIELDS;
    this._anchor_ref = input.anchor_ref ?? null;
  }

  extend(events: readonly ChainedEvent[]): void {
    for (const e of events) this._events.push(e);
  }

  addFrameworkMapping(mapping: FrameworkMapping): void {
    for (const idx of mapping.evidence_event_indexes) {
      if (idx < 0 || idx >= this._events.length) {
        throw new Error(
          `framework_mapping for ${mapping.obligation_id} references event index ${idx} ` +
            `but bundle has only ${this._events.length} events`,
        );
      }
    }
    this._framework_mappings.push(mapping);
  }

  build(options?: { readonly now?: Date }): ProofBundle {
    const actualNow = options?.now ?? new Date();
    const result = verifyChain(this._events);
    const head = headOf(this._events);
    const verifiedAt = formatTimestampMicros(actualNow);

    const chainMetadata: ProofBundle['chain_metadata'] = {
      chain_id: this._chain_id,
      schema_version: SCHEMA_VERSION,
      genesis_hash_hex: '0'.repeat(64),
      head_hash_hex: bytesToHex(head.event_hash),
      head_seq: head.seq,
      producer_runtime: this._producer_runtime,
      evidence_taxonomy_version: 1,
      ...(this._anchor_ref != null ? { anchor_ref: this._anchor_ref } : {}),
    };

    return {
      bundle_version: 1,
      chain_metadata: chainMetadata,
      events: this._events.map(serializeChainedEvent),
      verification_report: {
        ok: result.ok,
        first_bad_index: result.first_bad_index,
        reason: result.reason,
        verified_at: verifiedAt,
        verifier_version: _SDK_VERSION,
        verification_method: 'canonical-bytes-walk',
      },
      framework_mappings: [...this._framework_mappings],
      forbidden_fields: [...this._forbidden_fields],
    };
  }
}

// ----- Auditor export ----- //

export interface AuditorExport {
  readonly export_version: 1;
  readonly chain_summary: {
    readonly chain_id: string;
    readonly head_hash_hex: string;
    readonly event_count: number;
    readonly time_range: {
      readonly earliest: string;
      readonly latest: string;
    };
    readonly producer_runtime: string;
    readonly event_type_histogram: Record<string, number>;
    readonly anchor_status: 'unanchored' | 'anchored_partial' | 'anchored_full';
  };
  readonly verification_status: {
    readonly ok: boolean;
    readonly first_bad_index: number | null;
    readonly reason: string | null;
    readonly verified_at: string;
    readonly verifier_version: string;
    readonly verification_method: 'canonical-bytes-walk' | 'canonical-bytes-walk+anchor';
  };
  readonly framework_coverage: readonly {
    readonly framework: string;
    readonly article: string;
    readonly obligation_ids_with_evidence: readonly string[];
    readonly obligation_ids_without_evidence: readonly string[];
  }[];
  readonly redaction_policy: {
    readonly forbidden_fields: readonly string[];
    readonly redaction_status: 'enforced_by_adapter' | 'enforced_by_producer' | 'unenforced';
    readonly consent_status?: 'consent_present' | 'consent_absent' | 'consent_not_applicable';
  };
  readonly legal_disclaimer: string;
}

export interface AuditorExportOptions {
  readonly redaction_status?: AuditorExport['redaction_policy']['redaction_status'];
  readonly consent_status?: 'consent_present' | 'consent_absent' | 'consent_not_applicable';
  readonly legal_disclaimer?: string;
}

const DEFAULT_DISCLAIMER =
  'This export is a technical chain-integrity and framework-coverage summary. ' +
  'It is not a compliance opinion. Consult qualified counsel for any regulatory determination.';

export function buildAuditorExport(
  bundle: ProofBundle,
  options?: AuditorExportOptions,
): AuditorExport {
  const histogram: Record<string, number> = {};
  for (const ev of bundle.events) {
    const key = ev.event.event_type;
    histogram[key] = (histogram[key] ?? 0) + 1;
  }

  let earliest: string;
  let latest: string;
  if (bundle.events.length > 0) {
    earliest = bundle.events.reduce(
      (acc, ev) => (ev.event.timestamp < acc ? ev.event.timestamp : acc),
      bundle.events[0]!.event.timestamp,
    );
    latest = bundle.events.reduce(
      (acc, ev) => (ev.event.timestamp > acc ? ev.event.timestamp : acc),
      bundle.events[0]!.event.timestamp,
    );
  } else {
    earliest = bundle.verification_report.verified_at;
    latest = earliest;
  }

  return {
    export_version: 1,
    chain_summary: {
      chain_id: bundle.chain_metadata.chain_id,
      head_hash_hex: bundle.chain_metadata.head_hash_hex,
      event_count: bundle.events.length,
      time_range: { earliest, latest },
      producer_runtime: bundle.chain_metadata.producer_runtime,
      event_type_histogram: histogram,
      anchor_status: 'unanchored',
    },
    verification_status: {
      ok: bundle.verification_report.ok,
      first_bad_index: bundle.verification_report.first_bad_index,
      reason: bundle.verification_report.reason,
      verified_at: bundle.verification_report.verified_at,
      verifier_version: bundle.verification_report.verifier_version,
      verification_method: bundle.verification_report.verification_method,
    },
    framework_coverage: [],
    redaction_policy: {
      forbidden_fields: bundle.forbidden_fields,
      redaction_status: options?.redaction_status ?? 'enforced_by_producer',
      consent_status: options?.consent_status ?? 'consent_not_applicable',
    },
    legal_disclaimer: options?.legal_disclaimer ?? DEFAULT_DISCLAIMER,
  };
}
