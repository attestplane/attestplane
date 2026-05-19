// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Commit-then-redact retention/deletion proof helpers.
 *
 * The profile proves that a bundle carries well-formed proof markers
 * referencing existing events.  It does not claim GDPR compliance or legal
 * sufficiency.
 */

export const RETENTION_PROOF_SCHEMA_VERSION = 1;

export type RetentionAction = 'retention_marker' | 'deletion_marker';

export interface RetentionProof {
  readonly retention_proof_schema_version: 1;
  readonly proof_id: string;
  readonly action: RetentionAction;
  readonly target_event_hash_hex: string;
  readonly commit_event_hash_hex: string;
  readonly redacted_event_hash_hex?: string;
  readonly reason: string;
}

export interface RetentionProofVerificationResult {
  readonly ok: boolean;
  readonly reason: string | null;
  readonly checked_count: number;
  readonly failed_index: number | null;
}

const HEX64 = /^[0-9a-f]{64}$/;

export function buildDeletionProof(input: {
  readonly proof_id: string;
  readonly target_event_hash_hex: string;
  readonly commit_event_hash_hex: string;
  readonly redacted_event_hash_hex: string;
  readonly reason: string;
}): RetentionProof {
  const proof: RetentionProof = {
    action: 'deletion_marker',
    commit_event_hash_hex: input.commit_event_hash_hex,
    proof_id: input.proof_id,
    reason: input.reason,
    redacted_event_hash_hex: input.redacted_event_hash_hex,
    retention_proof_schema_version: RETENTION_PROOF_SCHEMA_VERSION,
    target_event_hash_hex: input.target_event_hash_hex,
  };
  validateRetentionProof(proof as unknown);
  return proof;
}

export function buildRetentionMarker(input: {
  readonly proof_id: string;
  readonly target_event_hash_hex: string;
  readonly commit_event_hash_hex: string;
  readonly reason: string;
}): RetentionProof {
  const proof: RetentionProof = {
    action: 'retention_marker',
    commit_event_hash_hex: input.commit_event_hash_hex,
    proof_id: input.proof_id,
    reason: input.reason,
    retention_proof_schema_version: RETENTION_PROOF_SCHEMA_VERSION,
    target_event_hash_hex: input.target_event_hash_hex,
  };
  validateRetentionProof(proof as unknown);
  return proof;
}

export function validateRetentionProof(raw: unknown): asserts raw is RetentionProof {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    throw new Error('retention proof must be an object');
  }
  const record = raw as Record<string, unknown>;
  const required = [
    'retention_proof_schema_version',
    'proof_id',
    'action',
    'target_event_hash_hex',
    'commit_event_hash_hex',
    'reason',
  ] as const;
  const missing = required.filter((field) => !(field in record));
  if (missing.length > 0) {
    throw new Error(`retention proof missing required fields: ${JSON.stringify(missing)}`);
  }
  if (record.retention_proof_schema_version !== RETENTION_PROOF_SCHEMA_VERSION) {
    throw new Error('retention_proof_schema_version must be 1');
  }
  if (typeof record.proof_id !== 'string' || record.proof_id.length === 0) {
    throw new Error('proof_id must be a non-empty string');
  }
  if (record.action !== 'retention_marker' && record.action !== 'deletion_marker') {
    throw new Error('action must be retention_marker or deletion_marker');
  }
  if (typeof record.reason !== 'string' || record.reason.length === 0) {
    throw new Error('reason must be a non-empty string');
  }
  for (const key of ['target_event_hash_hex', 'commit_event_hash_hex'] as const) {
    if (typeof record[key] !== 'string' || !HEX64.test(record[key])) {
      throw new Error(`${key} must be lowercase 64-hex`);
    }
  }
  if (record.action === 'deletion_marker') {
    if (
      typeof record.redacted_event_hash_hex !== 'string' ||
      !HEX64.test(record.redacted_event_hash_hex)
    ) {
      throw new Error('redacted_event_hash_hex must be lowercase 64-hex for deletion_marker');
    }
  } else if (record.redacted_event_hash_hex !== undefined) {
    if (
      typeof record.redacted_event_hash_hex !== 'string' ||
      !HEX64.test(record.redacted_event_hash_hex)
    ) {
      throw new Error('redacted_event_hash_hex must be lowercase 64-hex when present');
    }
  }
}

export function verifyRetentionProofs(
  proofs: unknown,
  eventHashes: ReadonlySet<string>,
): RetentionProofVerificationResult {
  if (proofs === undefined) {
    return { checked_count: 0, failed_index: null, ok: true, reason: null };
  }
  if (!Array.isArray(proofs)) {
    return {
      checked_count: 0,
      failed_index: 0,
      ok: false,
      reason: 'retention_proofs must be an array',
    };
  }
  const seen = new Set<string>();
  for (let i = 0; i < proofs.length; i++) {
    const proof = proofs[i];
    if (typeof proof !== 'object' || proof === null || Array.isArray(proof)) {
      return {
        checked_count: i,
        failed_index: i,
        ok: false,
        reason: `retention_proofs[${i}] must be an object`,
      };
    }
    try {
      validateRetentionProof(proof);
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : String(exc);
      return {
        checked_count: i,
        failed_index: i,
        ok: false,
        reason: `retention_proofs[${i}]: ${message}`,
      };
    }
    const typed = proof as RetentionProof;
    if (seen.has(typed.proof_id)) {
      return {
        checked_count: i,
        failed_index: i,
        ok: false,
        reason: `retention_proofs[${i}] duplicate proof_id`,
      };
    }
    seen.add(typed.proof_id);
    const refs = [
      typed.target_event_hash_hex,
      typed.commit_event_hash_hex,
      ...(typed.redacted_event_hash_hex !== undefined ? [typed.redacted_event_hash_hex] : []),
    ];
    const missing = refs.filter((ref) => !eventHashes.has(ref));
    if (missing.length > 0) {
      return {
        checked_count: i,
        failed_index: i,
        ok: false,
        reason: `retention_proofs[${i}] contains dangling event refs: ${JSON.stringify(missing)}`,
      };
    }
  }
  return { checked_count: proofs.length, failed_index: null, ok: true, reason: null };
}
