// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Stable verifier rejection reason-code taxonomy.
 *
 * Separate from ADR-0010 `ReasonCodeV1` and older `VERIFY_*` verifier outcome
 * codes. These namespaced strings are the public SDK surface for why `verify`
 * rejected an otherwise parsed input.
 */

export const VERIFY_REASON_CODE_SCHEMA_VERSION = 1 as const;
export const VERIFY_REASON_CODE_VERSION = 'rc.v1' as const;

export type VerifyReasonCodeV1 =
  | 'att.verify.anchor_invalid'
  | 'att.verify.canonical_mismatch'
  | 'att.verify.required_field_missing'
  | 'att.verify.schema_invalid'
  | 'att.verify.schema_unknown'
  | 'att.verify.schema_version_missing'
  | 'att.verify.schema_version_unsupported'
  | 'att.verify.signature_invalid'
  | 'att.verify.signature_missing'
  | 'att.verify.structure_invalid';

export interface VerifyReasonCodeRecord {
  readonly reasonCode: VerifyReasonCodeV1;
  readonly reasonCodeVersion: typeof VERIFY_REASON_CODE_VERSION;
  readonly rationale: string;
}

export const VERIFY_REASON_REGISTRY_V1 = [
  {
    reasonCode: 'att.verify.anchor_invalid',
    reasonCodeVersion: VERIFY_REASON_CODE_VERSION,
    rationale: 'Anchor material is missing, malformed, unsupported, or failed verification.',
  },
  {
    reasonCode: 'att.verify.canonical_mismatch',
    reasonCodeVersion: VERIFY_REASON_CODE_VERSION,
    rationale:
      'Recomputed canonical bytes, event hashes, chain links, or embedded verification reports disagree.',
  },
  {
    reasonCode: 'att.verify.required_field_missing',
    reasonCodeVersion: VERIFY_REASON_CODE_VERSION,
    rationale: 'A required top-level, nested, signature, or verifier-envelope field is absent.',
  },
  {
    reasonCode: 'att.verify.schema_invalid',
    reasonCodeVersion: VERIFY_REASON_CODE_VERSION,
    rationale: 'The input shape is malformed for a known verifier schema.',
  },
  {
    reasonCode: 'att.verify.schema_unknown',
    reasonCodeVersion: VERIFY_REASON_CODE_VERSION,
    rationale:
      'The input declares an unknown schema family, verification method namespace, or fail-closed critical/required field.',
  },
  {
    reasonCode: 'att.verify.schema_version_missing',
    reasonCodeVersion: VERIFY_REASON_CODE_VERSION,
    rationale: 'A known bundle, payload, signature, or verifier schema version is missing.',
  },
  {
    reasonCode: 'att.verify.schema_version_unsupported',
    reasonCodeVersion: VERIFY_REASON_CODE_VERSION,
    rationale: 'A known bundle, payload, signature, or verifier schema version is unsupported.',
  },
  {
    reasonCode: 'att.verify.signature_invalid',
    reasonCodeVersion: VERIFY_REASON_CODE_VERSION,
    rationale: 'Signature material is present but malformed or fails verifier checks.',
  },
  {
    reasonCode: 'att.verify.signature_missing',
    reasonCodeVersion: VERIFY_REASON_CODE_VERSION,
    rationale: 'Strict verification requires signature material but none is present.',
  },
  {
    reasonCode: 'att.verify.structure_invalid',
    reasonCodeVersion: VERIFY_REASON_CODE_VERSION,
    rationale: 'Known bundle relationships are malformed, duplicated, dangling, or out of order.',
  },
] as const satisfies readonly VerifyReasonCodeRecord[];

export const VERIFY_REASON_ANCHOR_INVALID = VERIFY_REASON_REGISTRY_V1[0].reasonCode;
export const VERIFY_REASON_CANONICAL_MISMATCH = VERIFY_REASON_REGISTRY_V1[1].reasonCode;
export const VERIFY_REASON_REQUIRED_FIELD_MISSING = VERIFY_REASON_REGISTRY_V1[2].reasonCode;
export const VERIFY_REASON_SCHEMA_INVALID = VERIFY_REASON_REGISTRY_V1[3].reasonCode;
export const VERIFY_REASON_SCHEMA_UNKNOWN = VERIFY_REASON_REGISTRY_V1[4].reasonCode;
export const VERIFY_REASON_SCHEMA_VERSION_MISSING = VERIFY_REASON_REGISTRY_V1[5].reasonCode;
export const VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED = VERIFY_REASON_REGISTRY_V1[6].reasonCode;
export const VERIFY_REASON_SIGNATURE_INVALID = VERIFY_REASON_REGISTRY_V1[7].reasonCode;
export const VERIFY_REASON_SIGNATURE_MISSING = VERIFY_REASON_REGISTRY_V1[8].reasonCode;
export const VERIFY_REASON_STRUCTURE_INVALID = VERIFY_REASON_REGISTRY_V1[9].reasonCode;

export type VerifyReasonCodeVersionV1 = typeof VERIFY_REASON_CODE_VERSION;

export const ALL_VERIFY_REASON_CODES_V1 = VERIFY_REASON_REGISTRY_V1.map(
  (entry) => entry.reasonCode,
) as readonly VerifyReasonCodeV1[];

export const VERIFY_REASON_CODE_DESCRIPTIONS: Readonly<Record<VerifyReasonCodeV1, string>> = {
  [VERIFY_REASON_ANCHOR_INVALID]: VERIFY_REASON_REGISTRY_V1[0].rationale,
  [VERIFY_REASON_CANONICAL_MISMATCH]: VERIFY_REASON_REGISTRY_V1[1].rationale,
  [VERIFY_REASON_REQUIRED_FIELD_MISSING]: VERIFY_REASON_REGISTRY_V1[2].rationale,
  [VERIFY_REASON_SCHEMA_INVALID]: VERIFY_REASON_REGISTRY_V1[3].rationale,
  [VERIFY_REASON_SCHEMA_UNKNOWN]: VERIFY_REASON_REGISTRY_V1[4].rationale,
  [VERIFY_REASON_SCHEMA_VERSION_MISSING]: VERIFY_REASON_REGISTRY_V1[5].rationale,
  [VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED]: VERIFY_REASON_REGISTRY_V1[6].rationale,
  [VERIFY_REASON_SIGNATURE_INVALID]: VERIFY_REASON_REGISTRY_V1[7].rationale,
  [VERIFY_REASON_SIGNATURE_MISSING]: VERIFY_REASON_REGISTRY_V1[8].rationale,
  [VERIFY_REASON_STRUCTURE_INVALID]: VERIFY_REASON_REGISTRY_V1[9].rationale,
};

export const VERIFY_REASON_CODE_VERSIONS: Readonly<Record<VerifyReasonCodeV1, VerifyReasonCodeVersionV1>> =
  {
    [VERIFY_REASON_ANCHOR_INVALID]: VERIFY_REASON_REGISTRY_V1[0].reasonCodeVersion,
    [VERIFY_REASON_CANONICAL_MISMATCH]: VERIFY_REASON_REGISTRY_V1[1].reasonCodeVersion,
    [VERIFY_REASON_REQUIRED_FIELD_MISSING]: VERIFY_REASON_REGISTRY_V1[2].reasonCodeVersion,
    [VERIFY_REASON_SCHEMA_INVALID]: VERIFY_REASON_REGISTRY_V1[3].reasonCodeVersion,
    [VERIFY_REASON_SCHEMA_UNKNOWN]: VERIFY_REASON_REGISTRY_V1[4].reasonCodeVersion,
    [VERIFY_REASON_SCHEMA_VERSION_MISSING]: VERIFY_REASON_REGISTRY_V1[5].reasonCodeVersion,
    [VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED]: VERIFY_REASON_REGISTRY_V1[6].reasonCodeVersion,
    [VERIFY_REASON_SIGNATURE_INVALID]: VERIFY_REASON_REGISTRY_V1[7].reasonCodeVersion,
    [VERIFY_REASON_SIGNATURE_MISSING]: VERIFY_REASON_REGISTRY_V1[8].reasonCodeVersion,
    [VERIFY_REASON_STRUCTURE_INVALID]: VERIFY_REASON_REGISTRY_V1[9].reasonCodeVersion,
  };

export function getVerifyReasonRecord(code: VerifyReasonCodeV1): VerifyReasonCodeRecord {
  const entry = VERIFY_REASON_RECORD_BY_CODE.get(code);
  if (!entry) {
    throw new Error(`unknown verify reason code: ${code}`);
  }
  return entry;
}

const VERIFY_REASON_RECORD_BY_CODE = new Map<VerifyReasonCodeV1, VerifyReasonCodeRecord>(
  VERIFY_REASON_REGISTRY_V1.map((entry) => [entry.reasonCode, entry]),
);

export function verifyReasonCodeVersion(code: VerifyReasonCodeV1): VerifyReasonCodeVersionV1 {
  const entry = VERIFY_REASON_RECORD_BY_CODE.get(code);
  if (!entry) {
    throw new Error(`unknown verify reason code: ${code}`);
  }
  return entry.reasonCodeVersion;
}

export function verifyReasonRationale(code: VerifyReasonCodeV1): string {
  const entry = VERIFY_REASON_RECORD_BY_CODE.get(code);
  if (!entry) {
    throw new Error(`unknown verify reason code: ${code}`);
  }
  return entry.rationale;
};

const VERIFY_REASON_CODE_PATTERN = /^att\.verify\.[a-z][a-z0-9_]*$/;

export function isKnownVerifyReasonCode(value: string): value is VerifyReasonCodeV1 {
  return (ALL_VERIFY_REASON_CODES_V1 as readonly string[]).includes(value);
}

export function verifyReasonCodeMatchesFormat(value: string): boolean {
  return VERIFY_REASON_CODE_PATTERN.test(value);
}
