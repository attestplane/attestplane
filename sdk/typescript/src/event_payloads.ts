// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Event-payload interfaces + validators per ADR-0009 Mode A.6.
 *
 * Each interface here describes the **payload slot** of an `AuditEvent`
 * for one v1 `event_type` (per `./event_types.ts` / ADR-0008). The
 * substrate's `ChainedEvent` shape stays frozen — INV 2. Payload
 * schemas are versioned independently of `chain.schema_version` /
 * `anchor_schema_version` / `signature_schema_version` /
 * `reason_code_schema_version`.
 *
 * Each payload schema also defines a small `validate*()` function that
 * rejects malformed payloads (wrong types, missing required fields,
 * forbidden field names per ADR-0004 § 2 column 3).
 */

const HEX64 = /^[0-9a-f]{64}$/;

/**
 * Per ADR-0004 § 2 column 3 + ADR-0009 § 1 Mode A.6 redaction policy.
 * Payload field names that MUST NEVER appear at the root of any event
 * payload.
 */
export const FORBIDDEN_PAYLOAD_FIELDS: ReadonlySet<string> = new Set([
  'signature',
  'private_key',
  'secret',
  'token',
  'auth_header',
  'session_token',
  'capability',
  'capability_required',
  'budget',
  'budget_cap',
  'quota',
  'scope_expression',
  'scope_body',
  'hmac',
  'hmac_canonical_payload',
  'policy_expression_body',
  'expression',
]);

export class PayloadValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PayloadValidationError';
  }
}

function requireIsoUtc(value: unknown, field: string): void {
  if (typeof value !== 'string') {
    throw new PayloadValidationError(
      `${field}: must be ISO-8601 string, got ${typeof value}`,
    );
  }
  if (!(value.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(value))) {
    throw new PayloadValidationError(
      `${field}: must be UTC-aware (use 'Z' or '+00:00' suffix), got ${JSON.stringify(value)}`,
    );
  }
  const ts = Date.parse(value);
  if (Number.isNaN(ts)) {
    throw new PayloadValidationError(
      `${field}: not valid ISO-8601: ${JSON.stringify(value)}`,
    );
  }
}

function rejectForbiddenFields(
  payload: Record<string, unknown>,
  eventType: string,
): void {
  const hits: string[] = [];
  for (const key of Object.keys(payload)) {
    if (FORBIDDEN_PAYLOAD_FIELDS.has(key)) hits.push(key);
  }
  if (hits.length > 0) {
    hits.sort();
    throw new PayloadValidationError(
      `${eventType}: payload contains forbidden field(s) [${hits.join(', ')}] per ADR-0004 § 2 redaction policy`,
    );
  }
}

// ----- lease_lifecycle_event payload -----

export type LeaseLifecycle = 'granted' | 'consumed' | 'expired' | 'revoked';

/**
 * Payload shape for the `lease_lifecycle_event` event_type.
 *
 * Schema-shape re-issue (Mode A.6 per ADR-0009 § 1) of fields
 * originally observed at `~/aios/crates/aios-sdk-evidence/src/artifact.rs`
 * and `~/aios/schemas/lease/lease.schema.json`. Authority-bearing
 * fields (`signature`, `capability_required`, `budget_cap`, `hmac`)
 * are explicitly NOT absorbed.
 */
export interface LeaseLifecycleEventPayload {
  readonly lease_event_schema_version: 1;
  readonly lease_id_hash: string;
  readonly lifecycle: LeaseLifecycle;
  readonly observed_at: string;
  readonly grantor_runtime_id?: string;
  readonly tenant_id_ref?: string;
  readonly step_id_ref?: string;
  readonly run_id_ref?: string;
  readonly artifact_hash_ref?: string;
  readonly reason_code?: string;
  readonly reason_text?: string;
}

const REQUIRED_LEASE_KEYS: readonly string[] = [
  'lease_event_schema_version',
  'lease_id_hash',
  'lifecycle',
  'observed_at',
];

const LIFECYCLE_VALUES: ReadonlySet<string> = new Set([
  'granted',
  'consumed',
  'expired',
  'revoked',
]);

/**
 * Throw `PayloadValidationError` if `payload` violates A.7 invariants.
 *
 * Mirrors `validate_lease_lifecycle_event_payload` in Python.
 */
export function validateLeaseLifecycleEventPayload(payload: unknown): void {
  if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new PayloadValidationError(
      `lease_lifecycle_event payload must be object, got ${Array.isArray(payload) ? 'array' : payload === null ? 'null' : typeof payload}`,
    );
  }
  const obj = payload as Record<string, unknown>;
  rejectForbiddenFields(obj, 'lease_lifecycle_event');

  const missing = REQUIRED_LEASE_KEYS.filter((k) => !(k in obj));
  if (missing.length > 0) {
    missing.sort();
    throw new PayloadValidationError(
      `lease_lifecycle_event: missing required fields [${missing.join(', ')}]`,
    );
  }
  if (obj.lease_event_schema_version !== 1) {
    throw new PayloadValidationError(
      `lease_lifecycle_event: lease_event_schema_version must be 1, got ${JSON.stringify(obj.lease_event_schema_version)}`,
    );
  }
  const leaseIdHash = obj.lease_id_hash;
  if (typeof leaseIdHash !== 'string' || !HEX64.test(leaseIdHash)) {
    throw new PayloadValidationError(
      `lease_lifecycle_event: lease_id_hash must be 64-hex string, got ${JSON.stringify(leaseIdHash)}`,
    );
  }
  const lifecycle = obj.lifecycle;
  if (typeof lifecycle !== 'string' || !LIFECYCLE_VALUES.has(lifecycle)) {
    throw new PayloadValidationError(
      `lease_lifecycle_event: lifecycle must be one of [consumed, expired, granted, revoked], got ${JSON.stringify(lifecycle)}`,
    );
  }
  requireIsoUtc(obj.observed_at, 'lease_lifecycle_event.observed_at');

  if (obj.artifact_hash_ref !== undefined) {
    if (typeof obj.artifact_hash_ref !== 'string' || !HEX64.test(obj.artifact_hash_ref)) {
      throw new PayloadValidationError(
        `lease_lifecycle_event: artifact_hash_ref (if present) must be 64-hex string, got ${JSON.stringify(obj.artifact_hash_ref)}`,
      );
    }
  }

  for (const optField of [
    'grantor_runtime_id',
    'tenant_id_ref',
    'step_id_ref',
    'run_id_ref',
    'reason_code',
    'reason_text',
  ]) {
    const v = obj[optField];
    if (v !== undefined && typeof v !== 'string') {
      throw new PayloadValidationError(
        `lease_lifecycle_event.${optField}: must be string or absent, got ${typeof v}`,
      );
    }
  }
}
