// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Cross-language conformance tests for ProofBundle.policy_trace_refs
 * (ADR-0012 / P1.2). Replays sdk/python/tests/conformance/
 * proof_bundle_policy_trace_vectors.json byte-for-byte against the TS
 * ProofBundleBuilder.
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { POLICY_CHECK_EVENT, TOOL_CALL_EVENT } from '../src/event_types.js';
import { chainExtend, genesisHead } from '../src/hashchain.js';
import { ProofBundleBuilder } from '../src/proof_bundle.js';
import { type ChainHead, type ChainedEvent, makeEventDraft } from '../src/types.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const VECTORS_PATH = resolve(
  __dirname,
  '..',
  '..',
  'python',
  'tests',
  'conformance',
  'proof_bundle_policy_trace_vectors.json',
);

interface BuilderVector {
  name: string;
  description?: string;
  input: { chain_event_types: string[] };
  expected_policy_trace_refs_count?: number;
  expected_policy_trace_refs?: null;
  expected_field_absent: boolean;
  expected_seqs?: number[];
}

interface VectorsFile {
  $schema_version: number;
  builder_vectors: BuilderVector[];
}

const VECTORS: VectorsFile = JSON.parse(readFileSync(VECTORS_PATH, 'utf-8')) as VectorsFile;

const NOW = new Date('2026-05-17T12:00:00.000Z');

function buildChainFromEventTypes(eventTypes: string[]): ChainedEvent[] {
  const chain: ChainedEvent[] = [];
  let head: ChainHead = genesisHead();
  for (let i = 0; i < eventTypes.length; i++) {
    const etype = eventTypes[i] as string;
    const ev = chainExtend(
      head,
      makeEventDraft({ event_type: etype, actor: `a${i}`, payload: { i } }),
      {
        now: NOW,
        event_id: `00000000-0000-7000-8000-${i.toString().padStart(12, '0')}`,
      },
    );
    chain.push(ev);
    head = { seq: ev.seq, event_hash: ev.event_hash };
  }
  return chain;
}

function bytesToHex(bytes: Uint8Array): string {
  let out = '';
  for (let i = 0; i < bytes.length; i++) {
    out += (bytes[i] as number).toString(16).padStart(2, '0');
  }
  return out;
}

describe('ProofBundle.policy_trace_refs — ADR-0012 P1.2', () => {
  it('vectors file loads', () => {
    expect(VECTORS.$schema_version).toBe(1);
    expect(VECTORS.builder_vectors.length).toBe(4);
  });

  for (const vec of VECTORS.builder_vectors) {
    it(`builder vector: ${vec.name}`, () => {
      const chain = buildChainFromEventTypes(vec.input.chain_event_types);
      const builder = new ProofBundleBuilder({
        chain_id: 'vec-policy-trace',
        producer_runtime: 'conformance-test',
      });
      builder.extend(chain);
      const bundle = builder.build({ now: NOW });

      if (vec.expected_field_absent) {
        expect(bundle.policy_trace_refs).toBeUndefined();
        return;
      }

      expect(bundle.policy_trace_refs).toBeDefined();
      const refs = bundle.policy_trace_refs as readonly string[];
      expect(refs.length).toBe(vec.expected_policy_trace_refs_count);

      // Each ref must be 64-hex.
      for (const r of refs) {
        expect(r).toMatch(/^[0-9a-f]{64}$/);
      }

      if (vec.expected_seqs !== undefined) {
        const expected = vec.expected_seqs.map((seq) =>
          bytesToHex((chain[seq] as ChainedEvent).event_hash),
        );
        expect([...refs]).toEqual(expected);
      }
    });
  }

  it('backward compat: bundles without policy_check_event omit the key', () => {
    const chain = buildChainFromEventTypes([TOOL_CALL_EVENT, TOOL_CALL_EVENT, TOOL_CALL_EVENT]);
    const builder = new ProofBundleBuilder({
      chain_id: 'bc',
      producer_runtime: 'bc-test',
    });
    builder.extend(chain);
    const bundle = builder.build({ now: NOW });
    expect(bundle.policy_trace_refs).toBeUndefined();
  });

  it('refs are chain-seq ordered, not insertion-order', () => {
    const types = [TOOL_CALL_EVENT, POLICY_CHECK_EVENT, TOOL_CALL_EVENT, POLICY_CHECK_EVENT];
    const chain = buildChainFromEventTypes(types);
    const builder = new ProofBundleBuilder({ chain_id: 'ord', producer_runtime: 'ord' });
    builder.extend(chain);
    const bundle = builder.build({ now: NOW });
    const refs = bundle.policy_trace_refs as readonly string[];
    expect([...refs]).toEqual([
      bytesToHex((chain[1] as ChainedEvent).event_hash),
      bytesToHex((chain[3] as ChainedEvent).event_hash),
    ]);
  });

  it('refs have no duplicates', () => {
    const chain = buildChainFromEventTypes(Array(4).fill(POLICY_CHECK_EVENT));
    const builder = new ProofBundleBuilder({ chain_id: 'dup', producer_runtime: 'dup' });
    builder.extend(chain);
    const bundle = builder.build({ now: NOW });
    const refs = bundle.policy_trace_refs as readonly string[];
    expect(new Set(refs).size).toBe(refs.length);
  });
});
