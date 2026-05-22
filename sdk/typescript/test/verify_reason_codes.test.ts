// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';

import {
  ALL_VERIFY_REASON_CODES_V1,
  VERIFY_REASON_ANCHOR_INVALID,
  VERIFY_REASON_CANONICAL_MISMATCH,
  VERIFY_REASON_REQUIRED_FIELD_MISSING,
  VERIFY_REASON_SCHEMA_INVALID,
  VERIFY_REASON_SCHEMA_UNKNOWN,
  VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
  VERIFY_REASON_SIGNATURE_INVALID,
  VERIFY_REASON_SIGNATURE_MISSING,
  VERIFY_REASON_STRUCTURE_INVALID,
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
});
