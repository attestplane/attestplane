// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Stable verifier error taxonomy for machine-readable CLI and verifier output.
 *
 * This is intentionally separate from ADR-0010 ReasonCodeV1.  Reason codes
 * classify chain/event verification semantics; these VERIFY_* strings classify
 * verifier and CLI outcomes.
 */

export const VERIFY_ERROR_SCHEMA_VERSION = 1;

export const ALL_VERIFY_ERROR_CODES_V1 = [
  'VERIFY_OK',
  'VERIFY_IO_ERROR',
  'VERIFY_SCHEMA_ERROR',
  'bundle.schema.incomplete',
  'VERIFY_CHAIN_RECOMPUTE_FAILED',
  'VERIFY_METADATA_CLOSURE_FAILED',
  'VERIFY_POLICY_TRACE_REFS_FAILED',
  'VERIFY_RETENTION_PROOF_FAILED',
  'VERIFY_ARTIFACT_HASH_FAILED',
  'VERIFY_REQUIRED_FIELDS_MISSING',
  'VERIFY_EXTENSION_INVALID_INPUT',
  'VERIFY_EXTENSION_UNSUPPORTED',
  'VERIFY_EXTENSION_FAILED',
] as const;

export type VerifyErrorCode = (typeof ALL_VERIFY_ERROR_CODES_V1)[number];

export const VERIFY_OK: VerifyErrorCode = 'VERIFY_OK';
export const VERIFY_IO_ERROR: VerifyErrorCode = 'VERIFY_IO_ERROR';
export const VERIFY_SCHEMA_ERROR: VerifyErrorCode = 'VERIFY_SCHEMA_ERROR';
export const VERIFY_BUNDLE_SCHEMA_INCOMPLETE: VerifyErrorCode = 'bundle.schema.incomplete';
export const VERIFY_CHAIN_RECOMPUTE_FAILED: VerifyErrorCode = 'VERIFY_CHAIN_RECOMPUTE_FAILED';
export const VERIFY_METADATA_CLOSURE_FAILED: VerifyErrorCode = 'VERIFY_METADATA_CLOSURE_FAILED';
export const VERIFY_POLICY_TRACE_REFS_FAILED: VerifyErrorCode = 'VERIFY_POLICY_TRACE_REFS_FAILED';
export const VERIFY_RETENTION_PROOF_FAILED: VerifyErrorCode = 'VERIFY_RETENTION_PROOF_FAILED';
export const VERIFY_ARTIFACT_HASH_FAILED: VerifyErrorCode = 'VERIFY_ARTIFACT_HASH_FAILED';
export const VERIFY_REQUIRED_FIELDS_MISSING: VerifyErrorCode = 'VERIFY_REQUIRED_FIELDS_MISSING';
export const VERIFY_EXTENSION_INVALID_INPUT: VerifyErrorCode = 'VERIFY_EXTENSION_INVALID_INPUT';
export const VERIFY_EXTENSION_UNSUPPORTED: VerifyErrorCode = 'VERIFY_EXTENSION_UNSUPPORTED';
export const VERIFY_EXTENSION_FAILED: VerifyErrorCode = 'VERIFY_EXTENSION_FAILED';

export const VERIFY_ERROR_DESCRIPTIONS: Record<VerifyErrorCode, string> = {
  VERIFY_OK: 'Verification completed without a verifier-detected failure.',
  VERIFY_IO_ERROR: 'The verifier could not read the requested input.',
  VERIFY_SCHEMA_ERROR: 'The input shape is unsupported or malformed.',
  'bundle.schema.incomplete':
    'The proof bundle lacks the minimum signed-attestation schema required by strict verification.',
  VERIFY_CHAIN_RECOMPUTE_FAILED: 'Recomputed hash-chain verification failed.',
  VERIFY_METADATA_CLOSURE_FAILED: 'Bundle metadata disagrees with recomputed chain state.',
  VERIFY_POLICY_TRACE_REFS_FAILED:
    'Policy trace references are missing, dangling, duplicated, or out of order.',
  VERIFY_RETENTION_PROOF_FAILED:
    'Retention/deletion proof references are malformed or do not point at bundle events.',
  VERIFY_ARTIFACT_HASH_FAILED:
    'The envelope artifact hash does not match the embedded proof bundle.',
  VERIFY_REQUIRED_FIELDS_MISSING: 'A required verifier-envelope field is missing.',
  VERIFY_EXTENSION_INVALID_INPUT: 'Requested signature or anchor extension input is malformed.',
  VERIFY_EXTENSION_UNSUPPORTED:
    'Requested signature or anchor extension input uses an unsupported mode.',
  VERIFY_EXTENSION_FAILED: 'Requested signature or anchor extension verification failed.',
};

export function isKnownVerifyErrorCode(value: string): value is VerifyErrorCode {
  return (ALL_VERIFY_ERROR_CODES_V1 as readonly string[]).includes(value);
}
