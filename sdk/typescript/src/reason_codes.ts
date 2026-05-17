// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * ReasonCodeV1 enum — machine-readable verification findings (ADR-0010).
 *
 * Stable string enum for downstream tooling (audit reports, EU AI Act
 * Article 12 evidence packs, regulator dashboards) to branch on the
 * *kind* of verification finding instead of regex-matching free-text
 * strings.
 *
 * The enum value set is frozen for v1 alongside
 * `REASON_CODE_SCHEMA_VERSION`. Adding new values requires a new ADR
 * amending ADR-0010 + a bump to schema version 2.
 *
 * Cross-language byte stability: the Python SDK exposes the same value
 * set via `reason_codes.py`. A conformance vector pins Py/TS equality
 * in CI.
 *
 * This module ships ONLY the enum primitive + helpers; it does NOT
 * modify `VerificationResult` or any verifier path's return shape.
 * Threading is sequenced into a follow-up ADR (anticipated ADR-0015)
 * so this ADR can ship as additive-only.
 */

export const REASON_CODE_SCHEMA_VERSION = 1 as const;

// Regex from ADR-0010 § 1: uppercase ASCII underscored, 2-64 chars.
const REASON_CODE_PATTERN = /^[A-Z][A-Z0-9_]{1,63}$/;

export type ReasonCodeV1 =
  // Chain integrity
  | 'CHAIN_OK'
  | 'CHAIN_SEQ_MISMATCH'
  | 'CHAIN_PREV_HASH_MISMATCH'
  | 'CHAIN_EVENT_HASH_MISMATCH'
  // Signature (ADR-0005)
  | 'SIGNATURE_OK'
  | 'SIGNATURE_INVALID'
  | 'SIGNATURE_UNKNOWN_KEY'
  | 'SIGNATURE_EXPIRED_KEY'
  | 'SIGNATURE_SCHEMA_MISMATCH'
  | 'SIGNATURE_PAYLOAD_MISMATCH'
  // Anchor (ADR-0003 + ADR-0006)
  | 'ANCHOR_OK'
  | 'ANCHOR_INVALID'
  | 'ANCHOR_CERT_EXPIRED'
  | 'ANCHOR_OCSP_FAILED'
  | 'ANCHOR_MISSING_LTV_ARTIFACTS'
  // Payload validators (event_payloads.ts)
  | 'PAYLOAD_OK'
  | 'PAYLOAD_MISSING_REQUIRED_FIELD'
  | 'PAYLOAD_FIELD_TYPE_MISMATCH'
  | 'PAYLOAD_FIELD_VALUE_OUT_OF_RANGE'
  | 'PAYLOAD_FORBIDDEN_FIELD_PRESENT'
  | 'PAYLOAD_SCHEMA_VERSION_MISMATCH'
  // Cross-cutting
  | 'UNSIGNED_SEGMENT'
  | 'UNANCHORED_SEGMENT'
  | 'BUNDLE_MISSING_REQUIRED_FIELD'
  | 'INTERNAL_ERROR';

export const ALL_REASON_CODES_V1: ReadonlySet<ReasonCodeV1> = new Set<ReasonCodeV1>([
  'CHAIN_OK',
  'CHAIN_SEQ_MISMATCH',
  'CHAIN_PREV_HASH_MISMATCH',
  'CHAIN_EVENT_HASH_MISMATCH',
  'SIGNATURE_OK',
  'SIGNATURE_INVALID',
  'SIGNATURE_UNKNOWN_KEY',
  'SIGNATURE_EXPIRED_KEY',
  'SIGNATURE_SCHEMA_MISMATCH',
  'SIGNATURE_PAYLOAD_MISMATCH',
  'ANCHOR_OK',
  'ANCHOR_INVALID',
  'ANCHOR_CERT_EXPIRED',
  'ANCHOR_OCSP_FAILED',
  'ANCHOR_MISSING_LTV_ARTIFACTS',
  'PAYLOAD_OK',
  'PAYLOAD_MISSING_REQUIRED_FIELD',
  'PAYLOAD_FIELD_TYPE_MISMATCH',
  'PAYLOAD_FIELD_VALUE_OUT_OF_RANGE',
  'PAYLOAD_FORBIDDEN_FIELD_PRESENT',
  'PAYLOAD_SCHEMA_VERSION_MISMATCH',
  'UNSIGNED_SEGMENT',
  'UNANCHORED_SEGMENT',
  'BUNDLE_MISSING_REQUIRED_FIELD',
  'INTERNAL_ERROR',
]);

export const REASON_CODE_DESCRIPTIONS: Readonly<Record<ReasonCodeV1, string>> = {
  CHAIN_OK: 'Chain integrity verified end-to-end.',
  CHAIN_SEQ_MISMATCH: 'ChainedEvent.seq does not equal expected position in chain.',
  CHAIN_PREV_HASH_MISMATCH: "ChainedEvent.prev_hash does not equal previous event's event_hash.",
  CHAIN_EVENT_HASH_MISMATCH:
    'ChainedEvent.event_hash does not equal hash_event(audit_event); canonicalize bytes have drifted.',
  SIGNATURE_OK: 'Ed25519 signature verified.',
  SIGNATURE_INVALID: 'Ed25519 verification failed (cryptographic mismatch).',
  SIGNATURE_UNKNOWN_KEY: 'key_id is not present in the configured trust roots.',
  SIGNATURE_EXPIRED_KEY: "verification_time falls outside the trust-root entry's validity window.",
  SIGNATURE_SCHEMA_MISMATCH: 'signature_schema_version is unsupported by this verifier.',
  SIGNATURE_PAYLOAD_MISMATCH:
    'signed_payload bytes do not match the re-canonicalised expected payload.',
  ANCHOR_OK: 'Anchor record verified including LTV (long-term validation) artifacts.',
  ANCHOR_INVALID: "Anchor record's signature, hash, or format check failed.",
  ANCHOR_CERT_EXPIRED: 'TSA certificate chain expired at verification_time.',
  ANCHOR_OCSP_FAILED: 'OCSP response invalid, revoked, or missing for the TSA certificate.',
  ANCHOR_MISSING_LTV_ARTIFACTS:
    'tsa_cert_chain or ocsp_responses is empty; CAdES-A long-term validation unsupported.',
  PAYLOAD_OK: 'Payload validates against its declared event schema.',
  PAYLOAD_MISSING_REQUIRED_FIELD: 'A required payload field is absent.',
  PAYLOAD_FIELD_TYPE_MISMATCH: 'A payload field is present but has the wrong type.',
  PAYLOAD_FIELD_VALUE_OUT_OF_RANGE:
    'A payload field has a value outside the declared enum/regex/numeric range.',
  PAYLOAD_FORBIDDEN_FIELD_PRESENT:
    'Payload contains a field name forbidden by ADR-0004 § 2 redaction policy.',
  PAYLOAD_SCHEMA_VERSION_MISMATCH: "Payload's declared <event>_schema_version is unsupported.",
  UNSIGNED_SEGMENT: 'Bundle contains no signature records covering this chain segment.',
  UNANCHORED_SEGMENT: 'Bundle contains no anchor records covering this chain segment.',
  BUNDLE_MISSING_REQUIRED_FIELD: 'A top-level proof-bundle field is absent.',
  INTERNAL_ERROR: 'Verifier hit an unexpected condition; should not occur in conformant input.',
};

/**
 * Return `true` if `code` is in `ALL_REASON_CODES_V1`. Use this in
 * tests to catch typos at the emit site, and in downstream consumers
 * for forward-compatible fallback ("treat unknown codes as INTERNAL_ERROR").
 */
export function isKnownReasonCode(code: string): code is ReasonCodeV1 {
  return (ALL_REASON_CODES_V1 as ReadonlySet<string>).has(code);
}

/**
 * Return `true` if `code` matches the documented uppercase regex.
 * Useful for validating caller-supplied codes in payload `reason_code`
 * fields where domain-specific codes are also permitted.
 */
export function reasonCodeMatchesFormat(code: string): boolean {
  return REASON_CODE_PATTERN.test(code);
}
