// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';

import {
  ALL_VERIFY_REASON_CODES_V1,
  VERIFY_REASON_CODE_VERSION,
  VERIFY_REASON_ANCHOR_INVALID,
  VERIFY_REASON_CANONICAL_MISMATCH,
  VERIFY_REASON_CODE_VERSIONS,
  VERIFY_REASON_REQUIRED_FIELD_MISSING,
  VERIFY_REASON_SCHEMA_INVALID,
  VERIFY_REASON_SCHEMA_UNKNOWN,
  VERIFY_REASON_SCHEMA_VERSION_MISSING,
  VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
  VERIFY_REASON_SIGNATURE_INVALID,
  VERIFY_REASON_SIGNATURE_MISSING,
  VERIFY_REASON_REGISTRY_V1,
  VERIFY_REASON_STRUCTURE_INVALID,
  getVerifyReasonRecord,
  isKnownVerifyReasonCode,
  verifyReasonCodeMatchesFormat,
} from '../src/verify_reason_codes.js';

describe('verify reason codes', () => {
  it('pins the v1 namespaced verifier rejection taxonomy', () => {
    expect(ALL_VERIFY_REASON_CODES_V1).toEqual([
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
    ]);

    for (const code of ALL_VERIFY_REASON_CODES_V1) {
      expect(isKnownVerifyReasonCode(code)).toBe(true);
      expect(verifyReasonCodeMatchesFormat(code)).toBe(true);
    }
    expect(isKnownVerifyReasonCode('VERIFY_OK')).toBe(false);
  });

  it('pins the versioned registry and derived descriptions', () => {
    expect(VERIFY_REASON_REGISTRY_V1).toHaveLength(ALL_VERIFY_REASON_CODES_V1.length);
    expect(Object.keys(VERIFY_REASON_CODE_VERSIONS).sort()).toEqual(
      [...ALL_VERIFY_REASON_CODES_V1].sort(),
    );
    for (const code of ALL_VERIFY_REASON_CODES_V1) {
      const record = getVerifyReasonRecord(code);
      expect(record.reasonCode).toBe(code);
      expect(record.reasonCodeVersion).toBe(VERIFY_REASON_CODE_VERSION);
      expect(record.rationale.length).toBeGreaterThan(0);
      expect(VERIFY_REASON_CODE_VERSIONS[code]).toBe(VERIFY_REASON_CODE_VERSION);
    }
  });
});
