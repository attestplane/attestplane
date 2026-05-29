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

import { POLICY_CHECK_EVENT } from './event_types.js';
import {
  GENESIS_HASH,
  SUPPORTED_SCHEMA_VERSIONS,
  type VerificationResult,
  hashEvent,
  headOf,
  verifyChain,
} from './hashchain.js';
import type {
  ProofBundle,
  SerializedAuditEvent,
  SerializedChainedEvent,
  SerializedSignatureRecord,
  SerializedSubjectRef,
} from './proof_bundle.js';
import { DEFAULT_FORBIDDEN_FIELDS } from './proof_bundle.js';
import { verifyRetentionProofs } from './retention.js';
import type { AuditEvent, ChainedEvent, SubjectRef } from './types.js';
import {
  VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
  VERIFY_CHAIN_RECOMPUTE_FAILED,
  VERIFY_METADATA_CLOSURE_FAILED,
  VERIFY_OK,
  VERIFY_POLICY_TRACE_REFS_FAILED,
  VERIFY_REQUIRED_FIELDS_MISSING,
  VERIFY_RETENTION_PROOF_FAILED,
  type VerifyErrorCode,
} from './verify_errors.js';
import {
  VERIFY_REASON_CANONICAL_MISMATCH,
  VERIFY_REASON_REQUIRED_FIELD_MISSING,
  VERIFY_REASON_SCHEMA_INVALID,
  VERIFY_REASON_SCHEMA_UNKNOWN,
  VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
  VERIFY_REASON_SIGNATURE_INVALID,
  VERIFY_REASON_SIGNATURE_MISSING,
  VERIFY_REASON_STRUCTURE_INVALID,
  VERIFY_REASON_TAXONOMY_VERSION,
  type VerifyReasonCodeV1,
} from './verify_reason_codes.js';

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
  readonly bundle_version: 1;
  readonly taxonomy_version: typeof VERIFY_REASON_TAXONOMY_VERSION;
  readonly chain_id: string;
  readonly head_hash_hex: string;
  readonly metadata_ok: boolean;
  readonly metadata_reason: string | null;
  readonly policy_trace_refs_ok: boolean;
  readonly policy_trace_refs_reason: string | null;
  readonly retention_proofs_ok: boolean;
  readonly retention_proofs_reason: string | null;
  readonly signed_attestation_schema_ok: boolean;
  readonly signed_attestation_schema_reason: string | null;
  readonly error_code: VerifyErrorCode;
  readonly primary_reason: VerifyReasonCodeV1 | null;
  readonly secondary_reasons: readonly VerifyReasonCodeV1[];
}

export interface VerifyProofBundleOptions {
  readonly requireNonEmpty?: boolean;
  readonly requireSignedAttestation?: boolean;
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
    `agreement=${result.agreement} metadata_reason=${JSON.stringify(result.metadata_reason)} ` +
    `policy_trace_refs_reason=${JSON.stringify(result.policy_trace_refs_reason)} ` +
    `retention_proofs_reason=${JSON.stringify(result.retention_proofs_reason)} ` +
    `signed_attestation_schema_reason=${JSON.stringify(result.signed_attestation_schema_reason)} ` +
    `error_code=${result.error_code} primary_reason=${result.primary_reason}`
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
const REQUIRED_VERIFICATION_REPORT = [
  'ok',
  'first_bad_index',
  'reason',
  'verified_at',
  'verifier_version',
  'verification_method',
] as const;
const ALLOWED_TOP_LEVEL = new Set([
  ...REQUIRED_TOP_LEVEL,
  'framework_mappings',
  'signature',
  'policy_trace_refs',
  'signatures',
  'retention_proofs',
]);
const ALLOWED_VERIFICATION_METHODS = new Set([
  'canonical-bytes-walk',
  'canonical-bytes-walk+anchor',
]);
const HEX64 = /^[0-9a-f]{64}$/;

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function validateShape(raw: unknown): asserts raw is ProofBundle {
  if (!isPlainObject(raw)) {
    throw new BundleSchemaError(
      `bundle must be a JSON object, got ${raw === null ? 'null' : typeof raw}`,
    );
  }
  const unknown = Object.keys(raw).filter((k) => !ALLOWED_TOP_LEVEL.has(k));
  if (unknown.length > 0) {
    throw new BundleSchemaError(
      `bundle contains unknown top-level fields: ${JSON.stringify(unknown.sort())}`,
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
  const report = raw.verification_report;
  const missingReport = REQUIRED_VERIFICATION_REPORT.filter((k) => !(k in report));
  if (missingReport.length > 0) {
    throw new BundleSchemaError(
      `verification_report missing required fields: ${JSON.stringify(missingReport)}`,
    );
  }
  const method = report.verification_method;
  if (!ALLOWED_VERIFICATION_METHODS.has(String(method))) {
    throw new BundleSchemaError(`unsupported verification_method=${JSON.stringify(method)}`);
  }
  if (!Array.isArray(raw.forbidden_fields)) {
    throw new BundleSchemaError('forbidden_fields must be an array');
  }
  const forbiddenFields = raw.forbidden_fields;
  if (!forbiddenFields.every((item) => typeof item === 'string' && item.length > 0)) {
    throw new BundleSchemaError('forbidden_fields must contain non-empty strings');
  }
  const missingForbidden = DEFAULT_FORBIDDEN_FIELDS.filter(
    (term) => !forbiddenFields.includes(term),
  );
  if (missingForbidden.length > 0) {
    throw new BundleSchemaError(
      `forbidden_fields missing required redaction terms: ${JSON.stringify(missingForbidden)}`,
    );
  }
  if ('framework_mappings' in raw && !Array.isArray(raw.framework_mappings)) {
    throw new BundleSchemaError('framework_mappings must be an array when present');
  }
  if ('policy_trace_refs' in raw && !Array.isArray(raw.policy_trace_refs)) {
    throw new BundleSchemaError('policy_trace_refs must be an array when present');
  }
  if ('retention_proofs' in raw && !Array.isArray(raw.retention_proofs)) {
    throw new BundleSchemaError('retention_proofs must be an array when present');
  }
}

function unknownRequiredFieldReason(
  section: Record<string, unknown>,
  sectionName: string,
): string | null {
  const criticalFields = Object.keys(section)
    .filter((key) => key.startsWith('critical_'))
    .sort();
  if (criticalFields.length === 0) return null;
  return `${sectionName}.${criticalFields[0]} is an unknown required field`;
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

function bytesToHex(bytes: Uint8Array): string {
  let out = '';
  for (let i = 0; i < bytes.length; i++) {
    out += (bytes[i] as number).toString(16).padStart(2, '0');
  }
  return out;
}

function isValidBase64(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  if (value.length % 4 !== 0) return false;
  return /^[A-Za-z0-9+/]*={0,2}$/.test(value);
}

function validateSignatureRecordShape(
  raw: SerializedSignatureRecord,
  index: number,
): string | null {
  const obj = raw as unknown as Record<string, unknown>;
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
  const missing = required.filter((field) => !(field in obj));
  if (missing.length > 0) {
    return `signatures[${index}] is malformed: missing fields ${JSON.stringify(missing)}`;
  }
  if (!Number.isInteger(raw.signature_schema_version) || raw.signature_schema_version < 1) {
    return `signatures[${index}].signature_schema_version must be a positive integer`;
  }
  if (!Number.isInteger(raw.signed_seq) || raw.signed_seq < 0) {
    return `signatures[${index}].signed_seq must be a non-negative integer`;
  }
  if (typeof raw.signature_hex !== 'string' || !/^[0-9a-f]{128}$/.test(raw.signature_hex)) {
    return `signatures[${index}] is malformed: signature_hex must be lowercase 128-hex`;
  }
  if (typeof raw.key_id !== 'string' || !/^[0-9a-f]{32}$/.test(raw.key_id)) {
    return `signatures[${index}].key_id must be lowercase 32-hex`;
  }
  if (raw.signature_mode !== 'segment_head' && raw.signature_mode !== 'per_event') {
    return `signatures[${index}].signature_mode must be segment_head or per_event`;
  }
  if (!isValidBase64(raw.public_key_der_b64)) {
    return `signatures[${index}].public_key_der_b64 must be base64`;
  }
  if (!isValidBase64(raw.signed_payload_b64)) {
    return `signatures[${index}].signed_payload_b64 must be base64`;
  }
  if (!Array.isArray(raw.signing_cert_chain_b64)) {
    return `signatures[${index}].signing_cert_chain_b64 must be a list`;
  }
  for (let i = 0; i < raw.signing_cert_chain_b64.length; i++) {
    if (!isValidBase64(raw.signing_cert_chain_b64[i])) {
      return `signatures[${index}].signing_cert_chain_b64[${i}] must be base64`;
    }
  }
  if (typeof raw.signed_at !== 'string') {
    return `signatures[${index}].signed_at must be a string`;
  }
  if (Number.isNaN(Date.parse(raw.signed_at))) {
    return `signatures[${index}].signed_at must be RFC3339/ISO-8601 datetime text`;
  }
  return null;
}

function validateMinimumSignedAttestationSchema(
  bundle: ProofBundle,
  events: readonly ChainedEvent[],
): { ok: boolean; reason: string | null } {
  if (events.length === 0) {
    return {
      ok: false,
      reason: 'events must contain at least one event before signed-attestation schema can pass',
    };
  }
  if (!Array.isArray(bundle.signatures) || bundle.signatures.length === 0) {
    return { ok: false, reason: 'signatures must contain at least one signed attestation' };
  }
  const canonicalEventHashes = new Set(events.map((event) => bytesToHex(hashEvent(event.event))));
  if (canonicalEventHashes.size !== events.length) {
    return { ok: false, reason: 'events do not have unique canonical subject digests' };
  }
  const malformedReasons: string[] = [];
  for (let i = 0; i < bundle.signatures.length; i++) {
    const raw = bundle.signatures[i];
    if (!isPlainObject(raw)) {
      malformedReasons.push(`signatures[${i}] must be an object`);
      continue;
    }
    const record = raw as unknown as SerializedSignatureRecord;
    if (
      typeof record.signed_event_hash_hex !== 'string' ||
      !HEX64.test(record.signed_event_hash_hex)
    ) {
      malformedReasons.push(`signatures[${i}].signed_event_hash_hex must be lowercase 64-hex`);
      continue;
    }
    if (!canonicalEventHashes.has(record.signed_event_hash_hex)) {
      malformedReasons.push(
        `signatures[${i}].signed_event_hash_hex does not match a canonical bundle event`,
      );
      continue;
    }
    const shapeReason = validateSignatureRecordShape(record, i);
    if (shapeReason !== null) {
      malformedReasons.push(shapeReason);
      continue;
    }
    return { ok: true, reason: null };
  }
  return {
    ok: false,
    reason:
      malformedReasons.length > 0 ? malformedReasons.join('; ') : 'no usable signature record',
  };
}

function signedAttestationReasonCode(reason: string | null): VerifyReasonCodeV1 {
  if (reason === null) return VERIFY_REASON_SIGNATURE_INVALID;
  if (reason.startsWith('events must contain')) return VERIFY_REASON_REQUIRED_FIELD_MISSING;
  if (reason.startsWith('signatures must contain')) return VERIFY_REASON_SIGNATURE_MISSING;
  if (reason.includes('missing fields') || reason.includes('signed_event_hash_hex must')) {
    return VERIFY_REASON_REQUIRED_FIELD_MISSING;
  }
  return VERIFY_REASON_SIGNATURE_INVALID;
}

export function classifyBundleSchemaError(error: Error | string): VerifyReasonCodeV1 {
  const text = typeof error === 'string' ? error : error.message;
  if (text.includes('unsupported bundle_version')) return VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED;
  if (text.includes('unsupported verification_method')) return VERIFY_REASON_SCHEMA_UNKNOWN;
  if (text.includes('missing required fields') || text.includes('missing fields')) {
    return VERIFY_REASON_REQUIRED_FIELD_MISSING;
  }
  if (text.includes('must be a JSON object') || text.includes('must be an array')) {
    return VERIFY_REASON_SCHEMA_INVALID;
  }
  if (text.includes('unknown top-level fields')) return VERIFY_REASON_SCHEMA_UNKNOWN;
  if (text.includes('schema_version') && text.includes('handles')) {
    return VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED;
  }
  return VERIFY_REASON_SCHEMA_INVALID;
}

function dedupeReasons(reasons: VerifyReasonCodeV1[]): {
  primary: VerifyReasonCodeV1 | null;
  secondary: readonly VerifyReasonCodeV1[];
} {
  const ordered: VerifyReasonCodeV1[] = [];
  for (const reason of reasons) {
    if (!ordered.includes(reason)) ordered.push(reason);
  }
  return {
    primary: ordered[0] ?? null,
    secondary: ordered.slice(1),
  };
}

function verificationReasons(input: {
  chainResult: VerificationResult;
  agreement: boolean;
  requireNonEmpty: boolean;
  events: readonly ChainedEvent[];
  signedSchemaOk: boolean;
  signedSchemaReason: string | null;
  metadataOk: boolean;
  metadataReason: string | null;
  policyOk: boolean;
  retentionOk: boolean;
}): { primary: VerifyReasonCodeV1 | null; secondary: readonly VerifyReasonCodeV1[] } {
  const reasons: VerifyReasonCodeV1[] = [];
  if (!input.chainResult.ok || !input.agreement) reasons.push(VERIFY_REASON_CANONICAL_MISMATCH);
  if (input.requireNonEmpty && input.events.length === 0) {
    reasons.push(VERIFY_REASON_REQUIRED_FIELD_MISSING);
  }
  if (!input.signedSchemaOk) reasons.push(signedAttestationReasonCode(input.signedSchemaReason));
  if (!input.metadataOk) {
    if (
      input.metadataReason?.includes('schema_version') &&
      input.metadataReason.includes('handles')
    ) {
      reasons.push(classifyBundleSchemaError(input.metadataReason));
    } else if (input.metadataReason?.includes('unknown required field')) {
      reasons.push(VERIFY_REASON_SCHEMA_UNKNOWN);
    } else {
      reasons.push(VERIFY_REASON_STRUCTURE_INVALID);
    }
  }
  if (!input.policyOk) reasons.push(VERIFY_REASON_STRUCTURE_INVALID);
  if (!input.retentionOk) reasons.push(VERIFY_REASON_STRUCTURE_INVALID);
  return dedupeReasons(reasons);
}

function verifyMetadataClosure(
  bundle: ProofBundle,
  events: readonly ChainedEvent[],
  chainResult: VerificationResult,
  options: VerifyProofBundleOptions = {},
): { ok: boolean; reason: string | null } {
  const metadata = bundle.chain_metadata;
  const report = bundle.verification_report;
  if (options.requireNonEmpty === true && events.length === 0) {
    return {
      ok: false,
      reason: 'events must contain at least one event when requireNonEmpty=true',
    };
  }
  if (!SUPPORTED_SCHEMA_VERSIONS.includes(metadata.schema_version as 1)) {
    return {
      ok: false,
      reason: `chain_metadata.schema_version=${JSON.stringify(metadata.schema_version)}; this verifier handles schema_version values ${JSON.stringify(SUPPORTED_SCHEMA_VERSIONS)}`,
    };
  }
  const metadataUnknownRequiredField = unknownRequiredFieldReason(
    metadata as Record<string, unknown>,
    'chain_metadata',
  );
  if (metadataUnknownRequiredField !== null) {
    return { ok: false, reason: metadataUnknownRequiredField };
  }
  const reportUnknownRequiredField = unknownRequiredFieldReason(
    report as Record<string, unknown>,
    'verification_report',
  );
  if (reportUnknownRequiredField !== null) {
    return { ok: false, reason: reportUnknownRequiredField };
  }
  if (metadata.genesis_hash_hex !== bytesToHex(GENESIS_HASH)) {
    return {
      ok: false,
      reason: 'chain_metadata.genesis_hash_hex does not match substrate genesis hash',
    };
  }
  if (
    metadata.evidence_taxonomy_version !== undefined &&
    metadata.evidence_taxonomy_version !== 1
  ) {
    return { ok: false, reason: 'chain_metadata.evidence_taxonomy_version must be 1 when present' };
  }
  const head = headOf(events);
  if (metadata.head_seq !== head.seq) {
    return {
      ok: false,
      reason: `chain_metadata.head_seq=${JSON.stringify(metadata.head_seq)} does not match computed head seq ${head.seq}`,
    };
  }
  if (metadata.head_hash_hex !== bytesToHex(head.event_hash)) {
    return {
      ok: false,
      reason: 'chain_metadata.head_hash_hex does not match computed chain head',
    };
  }
  if (Boolean(report.ok) !== chainResult.ok) {
    return { ok: false, reason: 'verification_report.ok disagrees with recomputed chain result' };
  }
  if (report.first_bad_index !== chainResult.first_bad_index) {
    return {
      ok: false,
      reason: 'verification_report.first_bad_index disagrees with recomputed chain result',
    };
  }
  if (report.reason !== chainResult.reason) {
    return {
      ok: false,
      reason: 'verification_report.reason disagrees with recomputed chain result',
    };
  }
  if (chainResult.ok && (report.first_bad_index !== null || report.reason !== null)) {
    return {
      ok: false,
      reason: 'verification_report carries failure detail while recomputed chain is ok',
    };
  }
  return { ok: true, reason: null };
}

function verifyPolicyTraceRefs(
  bundle: ProofBundle,
  events: readonly ChainedEvent[],
): { ok: boolean; reason: string | null } {
  const expected = events
    .filter((event) => event.event.event_type === POLICY_CHECK_EVENT)
    .map((event) => bytesToHex(event.event_hash));
  const hasRefs = bundle.policy_trace_refs !== undefined;
  if (expected.length === 0) {
    if (!hasRefs) return { ok: true, reason: null };
    const refs = bundle.policy_trace_refs as readonly string[];
    if (refs.length === 0) {
      return {
        ok: false,
        reason: 'policy_trace_refs must be absent, not empty, when no policy_check_event exists',
      };
    }
    return {
      ok: false,
      reason: 'policy_trace_refs present but bundle contains no policy_check_event',
    };
  }
  if (!hasRefs) {
    return {
      ok: false,
      reason: 'policy_trace_refs missing while bundle contains policy_check_event',
    };
  }
  const refs = bundle.policy_trace_refs as readonly string[];
  if (!refs.every((ref) => typeof ref === 'string' && HEX64.test(ref))) {
    return {
      ok: false,
      reason: 'policy_trace_refs must contain only lowercase 64-hex event hashes',
    };
  }
  if (new Set(refs).size !== refs.length) {
    return { ok: false, reason: 'policy_trace_refs contains duplicate event hashes' };
  }
  const eventHashes = new Set(events.map((event) => bytesToHex(event.event_hash)));
  const dangling = refs.filter((ref) => !eventHashes.has(ref));
  if (dangling.length > 0) {
    return {
      ok: false,
      reason: `policy_trace_refs contains dangling refs: ${JSON.stringify(dangling)}`,
    };
  }
  const expectedSet = new Set(expected);
  const wrongType = refs.filter((ref) => eventHashes.has(ref) && !expectedSet.has(ref));
  if (wrongType.length > 0) {
    return {
      ok: false,
      reason: `policy_trace_refs points at non-policy events: ${JSON.stringify(wrongType)}`,
    };
  }
  if (JSON.stringify(refs) !== JSON.stringify(expected)) {
    return {
      ok: false,
      reason: 'policy_trace_refs does not match chain-seq-ordered policy_check_event hashes',
    };
  }
  return { ok: true, reason: null };
}

export function verifyProofBundle(
  raw: unknown,
  options: VerifyProofBundleOptions = {},
): BundleVerificationResult {
  validateShape(raw);
  const bundle = raw;
  const events = rehydrateEvents(bundle.events);
  const chainResult = verifyChain(events);
  const bundleReportedOk = Boolean(bundle.verification_report.ok);
  const agreement = bundleReportedOk === chainResult.ok;
  const requireSignedAttestation = options.requireSignedAttestation === true;
  const signedAttestationSchema = requireSignedAttestation
    ? validateMinimumSignedAttestationSchema(bundle, events)
    : { ok: true, reason: null };
  const metadata = verifyMetadataClosure(bundle, events, chainResult, options);
  const policyTraceRefs = verifyPolicyTraceRefs(bundle, events);
  const retentionProofs = verifyRetentionProofs(
    bundle.retention_proofs,
    new Set(events.map((event) => bytesToHex(event.event_hash))),
  );
  let errorCode: VerifyErrorCode = VERIFY_OK;
  if (!chainResult.ok || !agreement) {
    errorCode = VERIFY_CHAIN_RECOMPUTE_FAILED;
  } else if (options.requireNonEmpty === true && events.length === 0) {
    errorCode = VERIFY_REQUIRED_FIELDS_MISSING;
  } else if (!signedAttestationSchema.ok) {
    errorCode = VERIFY_BUNDLE_SCHEMA_INCOMPLETE;
  } else if (!metadata.ok) {
    errorCode = VERIFY_METADATA_CLOSURE_FAILED;
  } else if (!policyTraceRefs.ok) {
    errorCode = VERIFY_POLICY_TRACE_REFS_FAILED;
  } else if (!retentionProofs.ok) {
    errorCode = VERIFY_RETENTION_PROOF_FAILED;
  }
  const reasons = verificationReasons({
    chainResult,
    agreement,
    requireNonEmpty: options.requireNonEmpty === true,
    events,
    signedSchemaOk: signedAttestationSchema.ok,
    signedSchemaReason: signedAttestationSchema.reason,
    metadataOk: metadata.ok,
    metadataReason: metadata.reason,
    policyOk: policyTraceRefs.ok,
    retentionOk: retentionProofs.ok,
  });

  return {
    ok:
      chainResult.ok &&
      agreement &&
      metadata.ok &&
      policyTraceRefs.ok &&
      retentionProofs.ok &&
      signedAttestationSchema.ok,
    chain_result: chainResult,
    bundle_reported_ok: bundleReportedOk,
    agreement,
    event_count: events.length,
    bundle_version: 1,
    taxonomy_version: VERIFY_REASON_TAXONOMY_VERSION,
    chain_id: bundle.chain_metadata.chain_id,
    head_hash_hex: bundle.chain_metadata.head_hash_hex,
    metadata_ok: metadata.ok,
    metadata_reason: metadata.reason,
    policy_trace_refs_ok: policyTraceRefs.ok,
    policy_trace_refs_reason: policyTraceRefs.reason,
    retention_proofs_ok: retentionProofs.ok,
    retention_proofs_reason: retentionProofs.reason,
    signed_attestation_schema_ok: signedAttestationSchema.ok,
    signed_attestation_schema_reason: signedAttestationSchema.reason,
    error_code: errorCode,
    primary_reason: reasons.primary,
    secondary_reasons: reasons.secondary,
  };
}

export async function verifyProofBundleFile(
  path: string,
  options: VerifyProofBundleOptions = {},
): Promise<BundleVerificationResult> {
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
  return verifyProofBundle(parsed, options);
}
