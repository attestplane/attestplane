// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Unit + cross-language conformance tests for reason_codes.ts (ADR-0010).
 * Replays sdk/python/tests/conformance/reason_codes_vectors.json — any
 * drift between Py and TS fails CI on either side.
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  ALL_REASON_CODES_V1,
  REASON_CODE_DESCRIPTIONS,
  REASON_CODE_SCHEMA_VERSION,
  type ReasonCodeV1,
  isKnownReasonCode,
  reasonCodeMatchesFormat,
} from '../src/reason_codes.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const VECTORS_PATH = resolve(
  __dirname,
  '..',
  '..',
  'python',
  'tests',
  'conformance',
  'reason_codes_vectors.json',
);

interface VectorsFile {
  $schema_version: number;
  reason_code_schema_version: number;
  all_reason_codes_v1: string[];
  expected_count: number;
  code_groups: Record<string, string[]>;
  format_check_examples: {
    valid: string[];
    invalid: string[];
  };
}

const VECTORS: VectorsFile = JSON.parse(readFileSync(VECTORS_PATH, 'utf-8')) as VectorsFile;

describe('ReasonCodeV1 — ADR-0010 enum conformance', () => {
  it('schema version locked at 1', () => {
    expect(REASON_CODE_SCHEMA_VERSION).toBe(1);
    expect(VECTORS.reason_code_schema_version).toBe(1);
  });

  it('TypeScript enum matches conformance vector', () => {
    const expected = new Set(VECTORS.all_reason_codes_v1);
    const actual = new Set<string>(ALL_REASON_CODES_V1 as ReadonlySet<string>);
    expect(actual).toEqual(expected);
    expect(actual.size).toBe(VECTORS.expected_count);
  });

  it('all codes have descriptions', () => {
    for (const code of ALL_REASON_CODES_V1) {
      const desc = REASON_CODE_DESCRIPTIONS[code as ReasonCodeV1];
      expect(typeof desc).toBe('string');
      expect(desc.length).toBeGreaterThan(0);
    }
  });

  it('description map keys exactly match enum set', () => {
    const descKeys = new Set(Object.keys(REASON_CODE_DESCRIPTIONS));
    const codeSet = new Set<string>(ALL_REASON_CODES_V1 as ReadonlySet<string>);
    expect(descKeys).toEqual(codeSet);
  });

  it('isKnownReasonCode positive', () => {
    for (const code of ALL_REASON_CODES_V1) {
      expect(isKnownReasonCode(code as string)).toBe(true);
    }
  });

  it('isKnownReasonCode negative', () => {
    expect(isKnownReasonCode('NOT_A_REAL_CODE')).toBe(false);
    expect(isKnownReasonCode('')).toBe(false);
    expect(isKnownReasonCode('chain_ok')).toBe(false);
  });

  it('format validation positive', () => {
    for (const code of VECTORS.format_check_examples.valid) {
      expect(reasonCodeMatchesFormat(code)).toBe(true);
    }
  });

  it('format validation negative', () => {
    for (const code of VECTORS.format_check_examples.invalid) {
      expect(reasonCodeMatchesFormat(code)).toBe(false);
    }
  });

  it('code groups partition the enum exactly', () => {
    const flat = new Set<string>();
    for (const [groupName, group] of Object.entries(VECTORS.code_groups)) {
      for (const code of group) {
        expect(flat.has(code)).toBe(false);
        flat.add(code);
        // groupName referenced for assertion message context only
        expect(groupName.length).toBeGreaterThan(0);
      }
    }
    const codeSet = new Set<string>(ALL_REASON_CODES_V1 as ReadonlySet<string>);
    expect(flat).toEqual(codeSet);
  });

  it('all v1 codes match the v1 regex', () => {
    for (const code of ALL_REASON_CODES_V1) {
      expect(reasonCodeMatchesFormat(code as string)).toBe(true);
    }
  });

  it.each([
    [
      'CHAIN_',
      ['CHAIN_OK', 'CHAIN_SEQ_MISMATCH', 'CHAIN_PREV_HASH_MISMATCH', 'CHAIN_EVENT_HASH_MISMATCH'],
    ],
    [
      'SIGNATURE_',
      [
        'SIGNATURE_OK',
        'SIGNATURE_INVALID',
        'SIGNATURE_UNKNOWN_KEY',
        'SIGNATURE_EXPIRED_KEY',
        'SIGNATURE_SCHEMA_MISMATCH',
        'SIGNATURE_PAYLOAD_MISMATCH',
      ],
    ],
    [
      'ANCHOR_',
      [
        'ANCHOR_OK',
        'ANCHOR_INVALID',
        'ANCHOR_CERT_EXPIRED',
        'ANCHOR_OCSP_FAILED',
        'ANCHOR_MISSING_LTV_ARTIFACTS',
      ],
    ],
    [
      'PAYLOAD_',
      [
        'PAYLOAD_OK',
        'PAYLOAD_MISSING_REQUIRED_FIELD',
        'PAYLOAD_FIELD_TYPE_MISMATCH',
        'PAYLOAD_FIELD_VALUE_OUT_OF_RANGE',
        'PAYLOAD_FORBIDDEN_FIELD_PRESENT',
        'PAYLOAD_SCHEMA_VERSION_MISMATCH',
      ],
    ],
  ] as const)('prefix %s namespaces its group correctly', (prefix, expected) => {
    const actual = [...ALL_REASON_CODES_V1].filter((c) => (c as string).startsWith(prefix)).sort();
    expect(actual).toEqual([...expected].sort());
  });
});
