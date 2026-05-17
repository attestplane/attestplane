// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Unit + cross-language conformance tests for event_payloads.ts (ADR-0009 P0.1).
 * Replays the same JSON file the Python SDK consumes — any drift fails CI
 * on either side.
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  FORBIDDEN_PAYLOAD_FIELDS,
  PayloadValidationError,
  type LeaseLifecycleEventPayload,
  type PolicyCheckEventPayload,
  validateLeaseLifecycleEventPayload,
  validatePolicyCheckEventPayload,
} from '../src/event_payloads.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const VECTORS_PATH = resolve(
  __dirname,
  '..',
  '..',
  'python',
  'tests',
  'conformance',
  'lease_lifecycle_event_vectors.json',
);
const POLICY_VECTORS_PATH = resolve(
  __dirname,
  '..',
  '..',
  'python',
  'tests',
  'conformance',
  'policy_check_event_vectors.json',
);

interface PositiveVector {
  name: string;
  description?: string;
  payload: Record<string, unknown>;
}

interface NegativeVector {
  name: string;
  expected_error_contains: string;
  payload: Record<string, unknown>;
}

interface VectorsFile {
  $schema_version: number;
  positive_vectors: PositiveVector[];
  negative_vectors: NegativeVector[];
}

const VECTORS: VectorsFile = JSON.parse(
  readFileSync(VECTORS_PATH, 'utf-8'),
) as VectorsFile;
const POLICY_VECTORS: VectorsFile = JSON.parse(
  readFileSync(POLICY_VECTORS_PATH, 'utf-8'),
) as VectorsFile;

describe('lease_lifecycle_event payload conformance', () => {
  it('vectors file loads', () => {
    expect(VECTORS.$schema_version).toBe(1);
    expect(VECTORS.positive_vectors.length).toBe(4);
    expect(VECTORS.negative_vectors.length).toBe(7);
  });

  for (const vec of VECTORS.positive_vectors) {
    it(`positive: ${vec.name}`, () => {
      expect(() => validateLeaseLifecycleEventPayload(vec.payload)).not.toThrow();
    });
  }

  for (const vec of VECTORS.negative_vectors) {
    it(`negative: ${vec.name}`, () => {
      try {
        validateLeaseLifecycleEventPayload(vec.payload);
        throw new Error(`expected ${vec.name} to throw, but it did not`);
      } catch (exc) {
        expect(exc).toBeInstanceOf(PayloadValidationError);
        expect((exc as Error).message).toContain(vec.expected_error_contains);
      }
    });
  }
});

describe('FORBIDDEN_PAYLOAD_FIELDS', () => {
  it('covers documented AIOS authority-signal field names', () => {
    const expectedMin = [
      'signature',
      'private_key',
      'secret',
      'token',
      'capability',
      'capability_required',
      'budget',
      'budget_cap',
      'expression',
      'hmac',
    ];
    for (const name of expectedMin) {
      expect(FORBIDDEN_PAYLOAD_FIELDS.has(name)).toBe(true);
    }
  });
});

describe('validateLeaseLifecycleEventPayload — Py/TS parity edge cases', () => {
  it('rejects non-object input', () => {
    expect(() => validateLeaseLifecycleEventPayload('not an object')).toThrow(
      /must be object/,
    );
  });

  it('rejects array input', () => {
    expect(() => validateLeaseLifecycleEventPayload([])).toThrow(/must be object/);
  });

  it('rejects optional non-string field', () => {
    expect(() =>
      validateLeaseLifecycleEventPayload({
        lease_event_schema_version: 1,
        lease_id_hash: '0'.repeat(64),
        lifecycle: 'granted',
        observed_at: '2026-05-17T12:00:00.000000Z',
        grantor_runtime_id: 12345 as unknown as string,
      }),
    ).toThrow(/grantor_runtime_id/);
  });

  it('accepts minimal payload via the typed interface', () => {
    const p: LeaseLifecycleEventPayload = {
      lease_event_schema_version: 1,
      lease_id_hash: '0'.repeat(64),
      lifecycle: 'granted',
      observed_at: '2026-05-17T12:00:00.000000Z',
    };
    expect(() => validateLeaseLifecycleEventPayload(p)).not.toThrow();
  });
});

describe('policy_check_event payload conformance', () => {
  it('vectors file loads', () => {
    expect(POLICY_VECTORS.$schema_version).toBe(1);
    expect(POLICY_VECTORS.positive_vectors.length).toBe(4);
    expect(POLICY_VECTORS.negative_vectors.length).toBe(8);
  });

  for (const vec of POLICY_VECTORS.positive_vectors) {
    it(`positive: ${vec.name}`, () => {
      expect(() => validatePolicyCheckEventPayload(vec.payload)).not.toThrow();
    });
  }

  for (const vec of POLICY_VECTORS.negative_vectors) {
    it(`negative: ${vec.name}`, () => {
      try {
        validatePolicyCheckEventPayload(vec.payload);
        throw new Error(`expected ${vec.name} to throw, but it did not`);
      } catch (exc) {
        expect(exc).toBeInstanceOf(PayloadValidationError);
        expect((exc as Error).message).toContain(vec.expected_error_contains);
      }
    });
  }

  it('typed interface accepts minimal payload', () => {
    const p: PolicyCheckEventPayload = {
      policy_event_schema_version: 1,
      policy_id: 'p',
      rule_id: 'r',
      decision: 'allow',
      observed_at: '2026-05-17T12:00:00.000000Z',
    };
    expect(() => validatePolicyCheckEventPayload(p)).not.toThrow();
  });

  it('expression body forbidden explicitly (ADR-0004 § 2 case #10)', () => {
    expect(() =>
      validatePolicyCheckEventPayload({
        policy_event_schema_version: 1,
        policy_id: 'p',
        rule_id: 'r',
        decision: 'deny',
        observed_at: '2026-05-17T12:00:00.000000Z',
        expression: 'amount > 10000',
      }),
    ).toThrow(/forbidden field/);
  });

  it('evidence_refs max 256', () => {
    const refs = Array.from({ length: 257 }, (_, i) =>
      i.toString(16).padStart(64, '0'),
    );
    expect(() =>
      validatePolicyCheckEventPayload({
        policy_event_schema_version: 1,
        policy_id: 'p',
        rule_id: 'r',
        decision: 'allow',
        observed_at: '2026-05-17T12:00:00.000000Z',
        evidence_refs: refs,
      }),
    ).toThrow(/max 256 entries/);
  });
});
