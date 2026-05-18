// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Tests for replay_event payload + verify_replay_manifest (P1.1 / A.9).
 * Replays sdk/python/tests/conformance/replay_event_vectors.json byte-for-byte.
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  PayloadValidationError,
  type ReplayEventPayload,
  validateReplayEventPayload,
} from '../src/event_payloads.js';
import { type ReplayManifest, verifyReplayManifest } from '../src/replay_verifier.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const VECTORS_PATH = resolve(
  __dirname,
  '..',
  '..',
  'python',
  'tests',
  'conformance',
  'replay_event_vectors.json',
);

interface VerifierVector {
  name: string;
  description?: string;
  chain: { seq: number; event_type: string; payload: Record<string, unknown> }[];
  manifest: {
    replay_run_id: string;
    original_run_id: string;
    expected_deterministic: boolean;
    snapshot_id_ref?: string;
  };
  expected_result: {
    ok: boolean;
    coverage: 'deterministic' | 'non_deterministic' | 'no_replay_event';
    matching_seq: number | null;
  };
}

interface VectorsFile {
  $schema_version: number;
  positive_vectors: { name: string; payload: Record<string, unknown> }[];
  negative_vectors: {
    name: string;
    expected_error_contains: string;
    payload: Record<string, unknown>;
  }[];
  verifier_vectors: VerifierVector[];
}

const VECTORS: VectorsFile = JSON.parse(readFileSync(VECTORS_PATH, 'utf-8')) as VectorsFile;

describe('replay_event payload conformance', () => {
  it('vectors file loads', () => {
    expect(VECTORS.$schema_version).toBe(1);
    expect(VECTORS.positive_vectors.length).toBe(4);
    expect(VECTORS.negative_vectors.length).toBe(10);
    expect(VECTORS.verifier_vectors.length).toBe(4);
  });

  for (const vec of VECTORS.positive_vectors) {
    it(`positive: ${vec.name}`, () => {
      expect(() => validateReplayEventPayload(vec.payload)).not.toThrow();
    });
  }

  for (const vec of VECTORS.negative_vectors) {
    it(`negative: ${vec.name}`, () => {
      try {
        validateReplayEventPayload(vec.payload);
        throw new Error(`expected ${vec.name} to throw`);
      } catch (exc) {
        expect(exc).toBeInstanceOf(PayloadValidationError);
        expect((exc as Error).message).toContain(vec.expected_error_contains);
      }
    });
  }

  it('typed interface accepts minimal payload', () => {
    const p: ReplayEventPayload = {
      replay_event_schema_version: 1,
      replay_run_id: 'r',
      original_run_id: 'o',
      input_hash_match: true,
      artifact_hash_match: true,
      audit_chain_match: true,
      deterministic_result: true,
      observed_at: '2026-05-17T12:00:00.000000Z',
    };
    expect(() => validateReplayEventPayload(p)).not.toThrow();
  });

  it('AND cross-check is load-bearing', () => {
    // AND of (true, false, true) is false; deterministic_result asserted true → reject.
    expect(() =>
      validateReplayEventPayload({
        replay_event_schema_version: 1,
        replay_run_id: 'x',
        original_run_id: 'y',
        input_hash_match: true,
        artifact_hash_match: false,
        audit_chain_match: true,
        deterministic_result: true,
        observed_at: '2026-05-17T12:00:00.000000Z',
      }),
    ).toThrow(/must equal logical AND/);
  });

  it('rejects boolean field given as integer 1', () => {
    expect(() =>
      validateReplayEventPayload({
        replay_event_schema_version: 1,
        replay_run_id: 'x',
        original_run_id: 'y',
        input_hash_match: 1,
        artifact_hash_match: true,
        audit_chain_match: true,
        deterministic_result: true,
        observed_at: '2026-05-17T12:00:00.000000Z',
      }),
    ).toThrow(/must be boolean/);
  });
});

describe('verify_replay_manifest — read-only walker', () => {
  for (const vec of VECTORS.verifier_vectors) {
    it(`verifier vector: ${vec.name}`, () => {
      const manifest: ReplayManifest = {
        replay_run_id: vec.manifest.replay_run_id,
        original_run_id: vec.manifest.original_run_id,
        expected_deterministic: vec.manifest.expected_deterministic,
        ...(vec.manifest.snapshot_id_ref !== undefined
          ? { snapshot_id_ref: vec.manifest.snapshot_id_ref }
          : {}),
      };
      const result = verifyReplayManifest(vec.chain, manifest);
      expect(result.ok).toBe(vec.expected_result.ok);
      expect(result.coverage).toBe(vec.expected_result.coverage);
      expect(result.matching_seq).toBe(vec.expected_result.matching_seq);
    });
  }

  it('is pure (same input → same output)', () => {
    const chain = [
      {
        seq: 0,
        event_type: 'replay_event',
        payload: {
          replay_event_schema_version: 1,
          replay_run_id: 'r1',
          original_run_id: 'o1',
          input_hash_match: true,
          artifact_hash_match: true,
          audit_chain_match: true,
          deterministic_result: true,
          observed_at: '2026-05-17T12:00:00.000000Z',
        },
      },
    ];
    const manifest: ReplayManifest = {
      replay_run_id: 'r1',
      original_run_id: 'o1',
      expected_deterministic: true,
    };
    const r1 = verifyReplayManifest(chain, manifest);
    const r2 = verifyReplayManifest(chain, manifest);
    expect(r1).toEqual(r2);
    expect(r1.ok).toBe(true);
  });

  it('picks latest matching seq', () => {
    const chain = [
      {
        seq: 1,
        event_type: 'replay_event',
        payload: {
          replay_event_schema_version: 1,
          replay_run_id: 'r',
          original_run_id: 'o',
          input_hash_match: true,
          artifact_hash_match: false,
          audit_chain_match: true,
          deterministic_result: false,
          observed_at: '2026-05-17T12:00:00.000000Z',
        },
      },
      {
        seq: 7,
        event_type: 'replay_event',
        payload: {
          replay_event_schema_version: 1,
          replay_run_id: 'r',
          original_run_id: 'o',
          input_hash_match: true,
          artifact_hash_match: true,
          audit_chain_match: true,
          deterministic_result: true,
          observed_at: '2026-05-17T12:01:00.000000Z',
        },
      },
    ];
    const result = verifyReplayManifest(chain, {
      replay_run_id: 'r',
      original_run_id: 'o',
      expected_deterministic: true,
    });
    expect(result.ok).toBe(true);
    expect(result.matching_seq).toBe(7);
  });

  it('handles malformed chain gracefully', () => {
    const result = verifyReplayManifest(
      'not an array' as unknown as Parameters<typeof verifyReplayManifest>[0],
      { replay_run_id: 'x', original_run_id: 'y', expected_deterministic: true },
    );
    expect(result.ok).toBe(false);
    expect(result.reason).toMatch(/must be array/);
  });
});
