// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Event-signing abstract types — TypeScript mirror of
 * `sdk/python/src/attestplane/signing/base.py` per the T6 architect
 * review (`docs/architecture/adr_0005_t6_review_20260517.md`).
 *
 * Hard-constraint preservation (architect plan hard constraint #1):
 * v0.0.1-alpha `vectors.json` continues to verify byte-for-byte. No
 * fields added to `AuditEvent` or `ChainedEvent`. `SignatureRecord`
 * is a pure sidecar (option B3) mirroring `AnchorRecord`.
 *
 * Field naming: snake_case matches the existing TS pattern
 * (`AnchorRecord.tsa_provider_id` etc.) — see decision 6 of the T6
 * review. This makes JSON serialisation a direct field-by-field copy
 * with no key remapping.
 *
 * Forbidden-verb gate (architect review § 1 D6 + ADR-0005 plan § 1 D):
 * `KeyProvider` subclasses MUST NOT declare public methods named
 * `revoke` / `rotate` / `delete` / `replace`. KeyProviders hold key
 * *access*, not key *authority*; exposing those verbs invites callers
 * to violate ADR-0004 § 1.
 */

import { createHash } from 'node:crypto';

export const SIGNATURE_SCHEMA_VERSION = 1 as const;
/** Frozen at 1 for v1. Independent of `chain.schema_version` and
 *  `anchor_schema_version`. */

export type SignatureMode = 'segment_head' | 'per_event';

// ----- Error hierarchy -----

export class SigningError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SigningError';
  }
}

export class KeyProviderError extends SigningError {
  constructor(message: string) {
    super(message);
    this.name = 'KeyProviderError';
  }
}

export class SignatureVerificationError extends SigningError {
  constructor(message: string) {
    super(message);
    this.name = 'SignatureVerificationError';
  }
}

export class KeyBoundaryError extends TypeError {
  constructor(message: string) {
    super(message);
    this.name = 'KeyBoundaryError';
  }
}

// ----- Data model -----

/** Identifies the v1 hex format: first 16 bytes of SHA-256(SPKI) → 32 hex chars. */
export function deriveKeyId(publicKeyDer: Uint8Array): string {
  if (publicKeyDer.length === 0) {
    throw new SigningError('deriveKeyId: publicKeyDer must be non-empty');
  }
  const hash = createHash('sha256').update(Buffer.from(publicKeyDer)).digest();
  return hash.subarray(0, 16).toString('hex');
}

/**
 * SignatureRecord — sidecar per architect plan § 1 B (option B3).
 *
 * Field names match Python's `SignatureRecord` exactly so JSON
 * serialisation is a direct copy. Validated via
 * {@link validateSignatureRecord}.
 */
export interface SignatureRecord {
  readonly signature_schema_version: number;
  readonly signed_seq: number;
  readonly signed_event_hash: Uint8Array;
  readonly signature: Uint8Array;
  readonly key_id: string;
  readonly public_key_der: Uint8Array;
  readonly signing_cert_chain: readonly Uint8Array[];
  readonly signed_at: Date;
  readonly signature_mode: SignatureMode;
  readonly signed_payload: Uint8Array;
}

/**
 * Throw `SigningError` if `record` violates the v1 invariants:
 * schema_version=1, seq≥0, signed_event_hash 32 bytes, signature 64
 * bytes (Ed25519), non-empty key_id / public_key_der / signed_payload,
 * key_id derives correctly from public_key_der.
 *
 * Mirror of Python `SignatureRecord.__post_init__`.
 */
export function validateSignatureRecord(record: SignatureRecord): void {
  if (record.signature_schema_version !== SIGNATURE_SCHEMA_VERSION) {
    throw new SigningError(
      `SignatureRecord.signature_schema_version must be ${SIGNATURE_SCHEMA_VERSION}, ` +
        `got ${record.signature_schema_version}`,
    );
  }
  if (record.signed_seq < 0) {
    throw new SigningError('SignatureRecord.signed_seq must be ≥ 0');
  }
  if (record.signed_event_hash.length !== 32) {
    throw new SigningError(
      `SignatureRecord.signed_event_hash must be 32 bytes, got ${record.signed_event_hash.length}`,
    );
  }
  if (record.signature.length !== 64) {
    throw new SigningError(
      `SignatureRecord.signature must be 64 bytes (Ed25519), got ${record.signature.length}`,
    );
  }
  if (!record.key_id) {
    throw new SigningError('SignatureRecord.key_id must be non-empty');
  }
  if (record.public_key_der.length === 0) {
    throw new SigningError('SignatureRecord.public_key_der must be non-empty');
  }
  if (record.signature_mode !== 'segment_head' && record.signature_mode !== 'per_event') {
    throw new SigningError(
      `SignatureRecord.signature_mode must be 'segment_head' or 'per_event', got ${JSON.stringify(record.signature_mode)}`,
    );
  }
  if (record.signed_payload.length === 0) {
    throw new SigningError('SignatureRecord.signed_payload must be non-empty');
  }
  const derived = deriveKeyId(record.public_key_der);
  if (record.key_id !== derived) {
    throw new SigningError(
      `SignatureRecord.key_id=${JSON.stringify(record.key_id)} does not match ` +
        `derived from public_key_der (${derived})`,
    );
  }
}

// ----- SignaturePolicy -----

export interface SignaturePolicy {
  readonly batch_size: number;
  readonly max_idle_seconds: number;
  readonly per_event: boolean;
}

export const DEFAULT_SIGNATURE_POLICY: SignaturePolicy = Object.freeze({
  batch_size: 64,
  max_idle_seconds: 60,
  per_event: false,
});

export function makeSignaturePolicy(input?: Partial<SignaturePolicy>): SignaturePolicy {
  const merged = { ...DEFAULT_SIGNATURE_POLICY, ...input };
  if (merged.batch_size < 1) {
    throw new SigningError('SignaturePolicy.batch_size must be ≥ 1');
  }
  if (merged.max_idle_seconds < 1) {
    throw new SigningError('SignaturePolicy.max_idle_seconds must be ≥ 1');
  }
  return Object.freeze({ ...merged });
}

// ----- SigningMaterial -----

import type { KeyObject } from 'node:crypto';

/**
 * Bundles a signing key with optional Fulcio-cert chain hook
 * (`signing_cert_chain` always empty in v1; ADR-0007 fills with
 * short-lived OIDC certs).
 */
export interface SigningMaterial {
  readonly privateKey: KeyObject;
  readonly publicKeyDer: Uint8Array;
  readonly signingCertChain: readonly Uint8Array[];
  readonly keyId: string;
}

// ----- KeyProvider abstract -----

const FORBIDDEN_KEY_PROVIDER_VERBS = new Set(['revoke', 'rotate', 'delete', 'replace']);

/**
 * Abstract base for any signing-key access strategy.
 *
 * Forbidden-verb gate is enforced at constructor time (TS analog of
 * Python's `__init_subclass__`). Any subclass declaring public
 * methods named in {revoke, rotate, delete, replace} fails at first
 * `new` call.
 */
export abstract class KeyProvider {
  abstract readonly provider_id: string;
  abstract readonly schema_version: number;

  constructor() {
    const proto = Object.getPrototypeOf(this) as object;
    const offenders: string[] = [];
    for (const name of Object.getOwnPropertyNames(proto)) {
      if (name === 'constructor') continue;
      if (name.startsWith('_')) continue;
      if (FORBIDDEN_KEY_PROVIDER_VERBS.has(name)) {
        offenders.push(name);
      }
    }
    if (offenders.length > 0) {
      offenders.sort();
      throw new KeyBoundaryError(
        `${this.constructor.name} declares forbidden mutating method(s) [${offenders.join(', ')}]; KeyProvider holds key access, not key authority. See ADR-0004 § 1 + adr_0005_signing_plan_20260517 § 1 D.`,
      );
    }
  }

  abstract getSigningMaterial(): SigningMaterial;
}
