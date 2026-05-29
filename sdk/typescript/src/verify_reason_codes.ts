// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Stable verifier rejection reason-code taxonomy.
 *
 * Separate from ADR-0010 `ReasonCodeV1` and older `VERIFY_*` verifier outcome
 * codes. These namespaced strings are the public SDK surface for why `verify`
 * rejected an otherwise parsed input.
 */

export const VERIFY_REASON_TAXONOMY_VERSION = 1 as const;
export const VERIFY_REASON_CODE_SCHEMA_VERSION = VERIFY_REASON_TAXONOMY_VERSION;

export const VERIFY_REASON_ANCHOR_INVALID = 'att.verify.anchor_invalid' as const;
export const VERIFY_REASON_CANONICAL_MISMATCH = 'att.verify.canonical_mismatch' as const;
export const VERIFY_REASON_REQUIRED_FIELD_MISSING = 'att.verify.required_field_missing' as const;
export const VERIFY_REASON_SCHEMA_INVALID = 'att.verify.schema_invalid' as const;
export const VERIFY_REASON_SCHEMA_UNKNOWN = 'att.verify.schema_unknown' as const;
export const VERIFY_REASON_SCHEMA_VERSION_MISSING = 'att.verify.schema_version_missing' as const;
export const VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED =
  'att.verify.schema_version_unsupported' as const;
export const VERIFY_REASON_SIGNATURE_INVALID = 'att.verify.signature_invalid' as const;
export const VERIFY_REASON_SIGNATURE_MISSING = 'att.verify.signature_missing' as const;
export const VERIFY_REASON_STRUCTURE_INVALID = 'att.verify.structure_invalid' as const;

export type VerifyReasonCodeV1 =
  | typeof VERIFY_REASON_ANCHOR_INVALID
  | typeof VERIFY_REASON_CANONICAL_MISMATCH
  | typeof VERIFY_REASON_REQUIRED_FIELD_MISSING
  | typeof VERIFY_REASON_SCHEMA_INVALID
  | typeof VERIFY_REASON_SCHEMA_UNKNOWN
  | typeof VERIFY_REASON_SCHEMA_VERSION_MISSING
  | typeof VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
  | typeof VERIFY_REASON_SIGNATURE_INVALID
  | typeof VERIFY_REASON_SIGNATURE_MISSING
  | typeof VERIFY_REASON_STRUCTURE_INVALID;

export const ALL_VERIFY_REASON_CODES_V1 = [
  VERIFY_REASON_ANCHOR_INVALID,
  VERIFY_REASON_CANONICAL_MISMATCH,
  VERIFY_REASON_REQUIRED_FIELD_MISSING,
  VERIFY_REASON_SCHEMA_INVALID,
  VERIFY_REASON_SCHEMA_UNKNOWN,
  VERIFY_REASON_SCHEMA_VERSION_MISSING,
  VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
  VERIFY_REASON_SIGNATURE_INVALID,
  VERIFY_REASON_SIGNATURE_MISSING,
  VERIFY_REASON_STRUCTURE_INVALID,
] as const satisfies readonly VerifyReasonCodeV1[];

export const VERIFY_REASON_TAXONOMY: Readonly<Record<VerifyReasonCodeV1, string>> = {
  [VERIFY_REASON_ANCHOR_INVALID]:
    'Anchor material is missing, malformed, unsupported, or failed verification.',
  [VERIFY_REASON_CANONICAL_MISMATCH]:
    'Recomputed canonical bytes, event hashes, chain links, or embedded verification reports disagree.',
  [VERIFY_REASON_REQUIRED_FIELD_MISSING]:
    'A required top-level, nested, signature, or verifier-envelope field is absent.',
  [VERIFY_REASON_SCHEMA_INVALID]: 'The input shape is malformed for a known verifier schema.',
  [VERIFY_REASON_SCHEMA_UNKNOWN]:
    'The input declares an unknown schema family, verification method namespace, or fail-closed critical/required field.',
  [VERIFY_REASON_SCHEMA_VERSION_MISSING]:
    'A known bundle, payload, signature, or verifier schema version is missing.',
  [VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED]:
    'A known bundle, payload, signature, or verifier schema version is unsupported.',
  [VERIFY_REASON_SIGNATURE_INVALID]:
    'Signature material is present but malformed or fails verifier checks.',
  [VERIFY_REASON_SIGNATURE_MISSING]:
    'Strict verification requires signature material but none is present.',
  [VERIFY_REASON_STRUCTURE_INVALID]:
    'Known bundle relationships are malformed, duplicated, dangling, or out of order.',
};

export const VERIFY_REASON_CODE_DESCRIPTIONS: Readonly<Record<VerifyReasonCodeV1, string>> =
  VERIFY_REASON_TAXONOMY;

const VERIFY_REASON_CODE_PATTERN = /^att\.verify\.[a-z][a-z0-9_]*$/;

export function isKnownVerifyReasonCode(value: string): value is VerifyReasonCodeV1 {
  return (ALL_VERIFY_REASON_CODES_V1 as readonly string[]).includes(value);
}

export function verifyReasonCodeMatchesFormat(value: string): boolean {
  return VERIFY_REASON_CODE_PATTERN.test(value);
}

export function verifyReasonCodeExplanation(value: VerifyReasonCodeV1): string {
  return VERIFY_REASON_TAXONOMY[value];
}

export function resolveVerifyTaxonomyVersion(): typeof VERIFY_REASON_TAXONOMY_VERSION {
  return VERIFY_REASON_TAXONOMY_VERSION;
}

export function formatVerifyTaxonomyVersion(value: number | null | undefined = undefined): string {
  if (value === null || value === undefined) {
    return 'unknown';
  }
  return String(value);
}
