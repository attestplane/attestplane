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
const REASON_CODE_PATTERN = /^[A-Z][A-Z0-9_]{1,63}$/;

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
    throw new PayloadValidationError(`${field}: must be ISO-8601 string, got ${typeof value}`);
  }
  if (!(value.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(value))) {
    throw new PayloadValidationError(
      `${field}: must be UTC-aware (use 'Z' or '+00:00' suffix), got ${JSON.stringify(value)}`,
    );
  }
  const ts = Date.parse(value);
  if (Number.isNaN(ts)) {
    throw new PayloadValidationError(`${field}: not valid ISO-8601: ${JSON.stringify(value)}`);
  }
}

function rejectForbiddenFields(payload: Record<string, unknown>, eventType: string): void {
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

function rejectUnknownFields(
  payload: Record<string, unknown>,
  allowedFields: ReadonlySet<string>,
  eventType: string,
): void {
  const unknown = Object.keys(payload).filter((key) => !allowedFields.has(key));
  if (unknown.length > 0) {
    unknown.sort();
    throw new PayloadValidationError(
      `${eventType}: unknown field(s) [${unknown.join(', ')}] not allowed by payload schema`,
    );
  }
}

function requireOptionalString(
  obj: Record<string, unknown>,
  field: string,
  eventType: string,
): void {
  if (field in obj && typeof obj[field] !== 'string') {
    throw new PayloadValidationError(
      `${eventType}.${field}: must be string or absent, got ${obj[field] === null ? 'null' : typeof obj[field]}`,
    );
  }
}

function requireOptionalReasonCode(
  obj: Record<string, unknown>,
  field: string,
  eventType: string,
): void {
  if (!(field in obj)) return;
  const value = obj[field];
  if (typeof value !== 'string' || !REASON_CODE_PATTERN.test(value)) {
    throw new PayloadValidationError(
      `${eventType}.${field}: must match ^[A-Z][A-Z0-9_]{1,63}$, got ${JSON.stringify(value)}`,
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
const ALLOWED_LEASE_KEYS: ReadonlySet<string> = new Set([
  'lease_event_schema_version',
  'lease_id_hash',
  'lifecycle',
  'observed_at',
  'grantor_runtime_id',
  'tenant_id_ref',
  'step_id_ref',
  'run_id_ref',
  'artifact_hash_ref',
  'reason_code',
  'reason_text',
]);

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
  rejectUnknownFields(obj, ALLOWED_LEASE_KEYS, 'lease_lifecycle_event');

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

  if ('artifact_hash_ref' in obj) {
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
    'reason_text',
  ]) {
    requireOptionalString(obj, optField, 'lease_lifecycle_event');
  }
  requireOptionalReasonCode(obj, 'reason_code', 'lease_lifecycle_event');
}

// ----- policy_check_event payload -----

export type PolicyDecision = 'allow' | 'deny' | 'abstain' | 'require_approval';

export type PolicyEffect = 'INFO' | 'WARN' | 'BLOCK';

/**
 * Payload shape for the `policy_check_event` event_type.
 *
 * Schema-shape re-issue (Mode A.6 per ADR-0009 § 1) of fields
 * originally observed at `~/aios/schemas/policy/policy.schema.json`.
 * Authority lifecycle fields (`expression` body / `PolicyUpdateCandidate`
 * / `activated_at` / `deprecated_at`) are explicitly NOT absorbed —
 * ADR-0004 § 2 case #10 keeps expression as hash only.
 */
export interface PolicyCheckEventPayload {
  readonly policy_event_schema_version: 1;
  readonly policy_id: string;
  readonly rule_id: string;
  readonly decision: PolicyDecision;
  readonly observed_at: string;
  readonly policy_version?: number;
  readonly kind?: string;
  readonly effect?: PolicyEffect;
  readonly expression_hash?: string;
  readonly evidence_refs?: readonly string[];
  readonly reason_code?: string;
  readonly reason_text?: string;
}

const REQUIRED_POLICY_KEYS: readonly string[] = [
  'policy_event_schema_version',
  'policy_id',
  'rule_id',
  'decision',
  'observed_at',
];
const ALLOWED_POLICY_KEYS: ReadonlySet<string> = new Set([
  'policy_event_schema_version',
  'policy_id',
  'rule_id',
  'decision',
  'observed_at',
  'policy_version',
  'kind',
  'effect',
  'expression_hash',
  'evidence_refs',
  'reason_code',
  'reason_text',
]);

const DECISION_VALUES: ReadonlySet<string> = new Set([
  'allow',
  'deny',
  'abstain',
  'require_approval',
]);

const EFFECT_VALUES: ReadonlySet<string> = new Set(['INFO', 'WARN', 'BLOCK']);

/**
 * Throw `PayloadValidationError` if `payload` violates A.8 invariants.
 *
 * Mirrors `validate_policy_check_event_payload` in Python.
 */
export function validatePolicyCheckEventPayload(payload: unknown): void {
  if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new PayloadValidationError(
      `policy_check_event payload must be object, got ${Array.isArray(payload) ? 'array' : payload === null ? 'null' : typeof payload}`,
    );
  }
  const obj = payload as Record<string, unknown>;
  rejectForbiddenFields(obj, 'policy_check_event');
  rejectUnknownFields(obj, ALLOWED_POLICY_KEYS, 'policy_check_event');

  const missing = REQUIRED_POLICY_KEYS.filter((k) => !(k in obj));
  if (missing.length > 0) {
    missing.sort();
    throw new PayloadValidationError(
      `policy_check_event: missing required fields [${missing.join(', ')}]`,
    );
  }
  if (obj.policy_event_schema_version !== 1) {
    throw new PayloadValidationError(
      `policy_check_event: policy_event_schema_version must be 1, got ${JSON.stringify(obj.policy_event_schema_version)}`,
    );
  }
  for (const strField of ['policy_id', 'rule_id'] as const) {
    const v = obj[strField];
    if (typeof v !== 'string' || v.length === 0) {
      throw new PayloadValidationError(
        `policy_check_event.${strField}: must be non-empty string, got ${JSON.stringify(v)}`,
      );
    }
  }
  const decision = obj.decision;
  if (typeof decision !== 'string' || !DECISION_VALUES.has(decision)) {
    throw new PayloadValidationError(
      `policy_check_event: decision must be one of [abstain, allow, deny, require_approval], got ${JSON.stringify(decision)}`,
    );
  }
  requireIsoUtc(obj.observed_at, 'policy_check_event.observed_at');

  if ('policy_version' in obj) {
    const pv = obj.policy_version;
    if (typeof pv !== 'number' || !Number.isInteger(pv) || pv < 1) {
      throw new PayloadValidationError(
        `policy_check_event.policy_version: must be integer >= 1, got ${JSON.stringify(pv)}`,
      );
    }
  }
  if ('effect' in obj) {
    if (typeof obj.effect !== 'string' || !EFFECT_VALUES.has(obj.effect)) {
      throw new PayloadValidationError(
        `policy_check_event.effect: must be one of [BLOCK, INFO, WARN] or absent, got ${JSON.stringify(obj.effect)}`,
      );
    }
  }
  if ('expression_hash' in obj) {
    if (typeof obj.expression_hash !== 'string' || !HEX64.test(obj.expression_hash)) {
      throw new PayloadValidationError(
        `policy_check_event.expression_hash: must be 64-hex string, got ${JSON.stringify(obj.expression_hash)}`,
      );
    }
  }
  if ('evidence_refs' in obj) {
    if (!Array.isArray(obj.evidence_refs)) {
      throw new PayloadValidationError(
        `policy_check_event.evidence_refs: must be array, got ${typeof obj.evidence_refs}`,
      );
    }
    if (obj.evidence_refs.length > 256) {
      throw new PayloadValidationError(
        `policy_check_event.evidence_refs: max 256 entries, got ${obj.evidence_refs.length}`,
      );
    }
    const seen = new Set<string>();
    for (let i = 0; i < obj.evidence_refs.length; i++) {
      const ref = obj.evidence_refs[i];
      if (typeof ref !== 'string' || !HEX64.test(ref)) {
        throw new PayloadValidationError(
          `policy_check_event.evidence_refs[${i}]: must be 64-hex string, got ${JSON.stringify(ref)}`,
        );
      }
      if (seen.has(ref)) {
        throw new PayloadValidationError(
          `policy_check_event.evidence_refs: duplicate entry ${JSON.stringify(ref)}`,
        );
      }
      seen.add(ref);
    }
  }

  for (const optField of ['kind', 'reason_code', 'reason_text']) {
    if (optField === 'reason_code') continue;
    requireOptionalString(obj, optField, 'policy_check_event');
  }
  requireOptionalReasonCode(obj, 'reason_code', 'policy_check_event');
}

// ----- replay_event payload -----

/**
 * Payload shape for the `replay_event` event_type.
 *
 * Schema-shape re-issue (Mode A.6 per ADR-0009 § 1 + A.9) of fields
 * observed at `~/aios/crates/aios-sdk-evidence/src/replay.rs` +
 * `~/aios/schemas/replay/replay_proof.schema.json`. Records that an
 * external runner observed the four boolean outcomes of a replay.
 * Attestplane substrate does NOT re-execute — replay execution lives
 * in REDLINE C.13 `aios-replay-runner`.
 *
 * The `deterministic_result` field MUST equal the logical AND of
 * `input_hash_match`, `artifact_hash_match`, `audit_chain_match`.
 * Validators enforce this cross-check.
 */
export interface ReplayEventPayload {
  readonly replay_event_schema_version: 1;
  readonly replay_run_id: string;
  readonly original_run_id: string;
  readonly input_hash_match: boolean;
  readonly artifact_hash_match: boolean;
  readonly audit_chain_match: boolean;
  readonly deterministic_result: boolean;
  readonly observed_at: string;
  readonly snapshot_id_ref?: string;
  readonly diff_summary_hash?: string;
  readonly reason_code?: string;
  readonly reason_text?: string;
}

const REQUIRED_REPLAY_KEYS: readonly string[] = [
  'replay_event_schema_version',
  'replay_run_id',
  'original_run_id',
  'input_hash_match',
  'artifact_hash_match',
  'audit_chain_match',
  'deterministic_result',
  'observed_at',
];
const ALLOWED_REPLAY_KEYS: ReadonlySet<string> = new Set([
  'replay_event_schema_version',
  'replay_run_id',
  'original_run_id',
  'input_hash_match',
  'artifact_hash_match',
  'audit_chain_match',
  'deterministic_result',
  'observed_at',
  'snapshot_id_ref',
  'diff_summary_hash',
  'reason_code',
  'reason_text',
]);

/**
 * Throw `PayloadValidationError` if `payload` violates A.9 invariants.
 *
 * Mirrors `validate_replay_event_payload` in Python.
 */
export function validateReplayEventPayload(payload: unknown): void {
  if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new PayloadValidationError(
      `replay_event payload must be object, got ${
        Array.isArray(payload) ? 'array' : payload === null ? 'null' : typeof payload
      }`,
    );
  }
  const obj = payload as Record<string, unknown>;
  rejectForbiddenFields(obj, 'replay_event');
  rejectUnknownFields(obj, ALLOWED_REPLAY_KEYS, 'replay_event');

  const missing = REQUIRED_REPLAY_KEYS.filter((k) => !(k in obj));
  if (missing.length > 0) {
    missing.sort();
    throw new PayloadValidationError(
      `replay_event: missing required fields [${missing.join(', ')}]`,
    );
  }
  if (obj.replay_event_schema_version !== 1) {
    throw new PayloadValidationError(
      `replay_event: replay_event_schema_version must be 1, got ${JSON.stringify(obj.replay_event_schema_version)}`,
    );
  }
  for (const strField of ['replay_run_id', 'original_run_id'] as const) {
    const v = obj[strField];
    if (typeof v !== 'string' || v.length === 0) {
      throw new PayloadValidationError(
        `replay_event.${strField}: must be non-empty string, got ${JSON.stringify(v)}`,
      );
    }
  }
  for (const boolField of [
    'input_hash_match',
    'artifact_hash_match',
    'audit_chain_match',
    'deterministic_result',
  ] as const) {
    const v = obj[boolField];
    if (typeof v !== 'boolean') {
      throw new PayloadValidationError(
        `replay_event.${boolField}: must be boolean, got ${typeof v}`,
      );
    }
  }
  const expectedDet =
    (obj.input_hash_match as boolean) &&
    (obj.artifact_hash_match as boolean) &&
    (obj.audit_chain_match as boolean);
  if (obj.deterministic_result !== expectedDet) {
    throw new PayloadValidationError(
      `replay_event.deterministic_result: must equal logical AND of input_hash_match, artifact_hash_match, audit_chain_match (got ${JSON.stringify(obj.deterministic_result)}, expected ${expectedDet})`,
    );
  }
  requireIsoUtc(obj.observed_at, 'replay_event.observed_at');

  if ('snapshot_id_ref' in obj) {
    if (typeof obj.snapshot_id_ref !== 'string' || obj.snapshot_id_ref.length === 0) {
      throw new PayloadValidationError(
        `replay_event.snapshot_id_ref: must be non-empty string, got ${JSON.stringify(obj.snapshot_id_ref)}`,
      );
    }
  }
  if ('diff_summary_hash' in obj) {
    if (typeof obj.diff_summary_hash !== 'string' || !HEX64.test(obj.diff_summary_hash)) {
      throw new PayloadValidationError(
        `replay_event.diff_summary_hash: must be 64-hex string, got ${JSON.stringify(obj.diff_summary_hash)}`,
      );
    }
  }

  for (const optField of ['reason_code', 'reason_text']) {
    if (optField === 'reason_code') continue;
    requireOptionalString(obj, optField, 'replay_event');
  }
  requireOptionalReasonCode(obj, 'reason_code', 'replay_event');
}
