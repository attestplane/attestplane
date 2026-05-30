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
import { VERSION as _SDK_VERSION } from './index_version.js';
import { type RetentionProof, validateRetentionProof } from './retention.js';
import {
  SIGNATURE_SCHEMA_VERSION,
  type SignatureRecord,
  validateSignatureRecord,
} from './signing/base.js';
import type { ChainedEvent, SubjectRef } from './types.js';

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
  /**
   * Additive `policy_trace_refs` field per ADR-0012 P1.2. Flat list of
   * `event_hash_hex` for every ChainedEvent whose `event_type ==
   * 'policy_check_event'`. Chain-seq-ascending order; deduplicated;
   * absent when empty (preserves byte identity with bundles that have
   * no policy_check_event rows).
   */
  readonly policy_trace_refs?: readonly string[];
  /**
   * Additive `signatures` field per ADR-0005 T5. Absent when no
   * SignatureRecord has been added (preserves byte equality with
   * v0.0.1-alpha bundles).
   */
  readonly signatures?: readonly SerializedSignatureRecord[];
  /**
   * Additive ADR-0015 commit-then-redact proof markers. Verifiers check marker
   * shape and references only; they do not claim GDPR compliance.
   */
  readonly retention_proofs?: readonly RetentionProof[];
}

/**
 * Wire-format `SignatureRecord` per `_serialize_signature_record` in
 * `sdk/python/src/attestplane/proof_bundle.py`. Field-by-field
 * byte-stable copy of Python's encoding.
 */
export interface SerializedSignatureRecord {
  readonly signature_schema_version: number;
  readonly signed_seq: number;
  readonly signed_event_hash_hex: string;
  readonly signature_hex: string;
  readonly key_id: string;
  readonly public_key_der_b64: string;
  readonly signing_cert_chain_b64: readonly string[];
  readonly signed_at: string;
  readonly signature_mode: 'segment_head' | 'per_event';
  readonly signed_payload_b64: string;
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

function hexToBytes(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) {
    throw new Error(`hex string has odd length: ${hex.length}`);
  }
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    const byte = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    if (Number.isNaN(byte)) {
      throw new Error(`invalid hex at offset ${i * 2}: ${hex.slice(i * 2, i * 2 + 2)}`);
    }
    out[i] = byte;
  }
  return out;
}

function b64encode(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString('base64');
}

function b64decode(b64: string): Uint8Array {
  return new Uint8Array(Buffer.from(b64, 'base64'));
}

function parseSignedAtTimestamp(ts: string): Date {
  // Python emits "YYYY-MM-DDTHH:MM:SS.ffffffZ" (microsecond precision +
  // literal Z). Date.parse accepts trailing-Z ISO; sub-millisecond
  // digits are silently truncated to ms precision, which is acceptable
  // because we only compare ISO-form on re-emit — never round-trip Date
  // back to bytes.
  const t = Date.parse(ts);
  if (Number.isNaN(t)) {
    throw new Error(`invalid signed_at timestamp: ${JSON.stringify(ts)}`);
  }
  return new Date(t);
}

/**
 * Encode a `SignatureRecord` as the wire-format dict per Python's
 * `_serialize_signature_record`. Hex for fixed-length crypto values
 * (event_hash, signature); base64 for variable blobs (public_key_der,
 * cert_chain, signed_payload); RFC-3339 µs-Z for the datetime.
 */
export function serializeSignatureRecord(record: SignatureRecord): SerializedSignatureRecord {
  return {
    signature_schema_version: record.signature_schema_version,
    signed_seq: record.signed_seq,
    signed_event_hash_hex: bytesToHex(record.signed_event_hash),
    signature_hex: bytesToHex(record.signature),
    key_id: record.key_id,
    public_key_der_b64: b64encode(record.public_key_der),
    signing_cert_chain_b64: record.signing_cert_chain.map((c) => b64encode(c)),
    signed_at: formatTimestampMicros(record.signed_at),
    signature_mode: record.signature_mode,
    signed_payload_b64: b64encode(record.signed_payload),
  };
}

/**
 * Inverse of `serializeSignatureRecord`. Validates the result via
 * `validateSignatureRecord` so malformed records surface as a
 * `SigningError`.
 */
export function deserializeSignatureRecord(raw: SerializedSignatureRecord): SignatureRecord {
  const required = [
    'signature_schema_version',
    'signed_seq',
    'signed_event_hash_hex',
    'signature_hex',
    'key_id',
    'public_key_der_b64',
    'signing_cert_chain_b64',
    'signed_at',
    'signature_mode',
    'signed_payload_b64',
  ] as const;
  const obj = raw as unknown as Record<string, unknown>;
  for (const k of required) {
    if (!(k in obj)) {
      throw new Error(`deserializeSignatureRecord: missing field ${k}`);
    }
  }
  const record: SignatureRecord = {
    signature_schema_version: Number(raw.signature_schema_version),
    signed_seq: Number(raw.signed_seq),
    signed_event_hash: hexToBytes(raw.signed_event_hash_hex),
    signature: hexToBytes(raw.signature_hex),
    key_id: String(raw.key_id),
    public_key_der: b64decode(raw.public_key_der_b64),
    signing_cert_chain: raw.signing_cert_chain_b64.map((c) => b64decode(c)),
    signed_at: parseSignedAtTimestamp(raw.signed_at),
    signature_mode: raw.signature_mode,
    signed_payload: b64decode(raw.signed_payload_b64),
  };
  validateSignatureRecord(record);
  return record;
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
  private readonly _signatures: SignatureRecord[] = [];
  private readonly _retention_proofs: RetentionProof[] = [];

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

  /**
   * Add `SignatureRecord` instances per ADR-0005 T5. Each entry is
   * validated immediately via `validateSignatureRecord`; the bundle's
   * `signatures` field is emitted only when at least one record has
   * been added (preserves byte equality with v0.0.1-alpha bundles).
   */
  extendSignatures(records: readonly SignatureRecord[]): void {
    for (const r of records) {
      validateSignatureRecord(r);
      if (r.signature_schema_version !== SIGNATURE_SCHEMA_VERSION) {
        throw new Error(
          `extendSignatures: signature_schema_version must be ${SIGNATURE_SCHEMA_VERSION}, got ${r.signature_schema_version}`,
        );
      }
      this._signatures.push(r);
    }
  }

  extendRetentionProofs(records: readonly RetentionProof[]): void {
    for (const r of records) {
      validateRetentionProof(r as unknown as Record<string, unknown>);
      this._retention_proofs.push(r);
    }
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

    const bundle: ProofBundle = {
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
      // ADR-0012 P1.2: auto-derive policy_trace_refs (absent when empty).
      ...((): { policy_trace_refs?: readonly string[] } => {
        const refs = this._events
          .filter((ev) => ev.event.event_type === 'policy_check_event')
          .map((ev) => bytesToHex(ev.event_hash));
        return refs.length > 0 ? { policy_trace_refs: refs } : {};
      })(),
      ...(this._signatures.length > 0
        ? { signatures: this._signatures.map(serializeSignatureRecord) }
        : {}),
      ...(this._retention_proofs.length > 0
        ? { retention_proofs: [...this._retention_proofs] }
        : {}),
    };
    return bundle;
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
  const firstEvent = bundle.events[0];
  if (firstEvent !== undefined) {
    earliest = bundle.events.reduce(
      (acc, ev) => (ev.event.timestamp < acc ? ev.event.timestamp : acc),
      firstEvent.event.timestamp,
    );
    latest = bundle.events.reduce(
      (acc, ev) => (ev.event.timestamp > acc ? ev.event.timestamp : acc),
      firstEvent.event.timestamp,
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
