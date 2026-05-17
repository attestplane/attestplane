// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Cross-language conformance: this test replays
 * `sdk/python/tests/conformance/vectors.json` through the TypeScript SDK and
 * asserts that every `event_hash_hex` reproduces byte-for-byte. If this
 * test fails, the Python and TypeScript SDKs have drifted and any
 * cross-SDK audit verification is broken — the release MUST be blocked.
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { createHash } from 'node:crypto';
import { canonicalize } from '../src/canonical.js';
import { SCHEMA_VERSION, chainExtend, genesisHead, headOf } from '../src/hashchain.js';
import {
  type ChainHead,
  type ChainedEvent,
  type EventDraft,
  type SubjectRef,
  type SubjectScheme,
  makeEventDraft,
  makeSubjectRef,
} from '../src/types.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const VECTORS_PATH = resolve(
  __dirname,
  '..',
  '..',
  'python',
  'tests',
  'conformance',
  'vectors.json',
);

interface RawSubjectRef {
  scheme: SubjectScheme;
  value: string;
}

interface RawDraft {
  event_type: string;
  actor: string;
  payload?: Record<string, unknown>;
  subject_ref?: RawSubjectRef;
  session_id?: string;
  reference_db_ref?: string;
  matched_input_ref?: string;
  human_verifier?: RawSubjectRef;
}

interface VectorEntry {
  name: string;
  description: string;
  seq: number;
  event_id: string;
  timestamp: string;
  draft: RawDraft;
  prev_hash_hex: string;
  canonical_bytes_sha256_hex: string;
  event_hash_hex: string;
}

interface VectorFile {
  schema_version: number;
  spec: string;
  generated_with: string;
  final_chain_head_hex: string;
  entries: VectorEntry[];
}

// JSON.parse silently rounds integers > Number.MAX_SAFE_INTEGER (2^53 - 1)
// to the nearest double, which would corrupt vector 8 (int64 boundary values).
// Node 22+ exposes the source literal to the reviver; we promote any literal
// outside the safe-integer range to BigInt, which the canonicalizer accepts.
function parseJsonWithBigInts(text: string): unknown {
  return JSON.parse(
    text,
    function reviver(
      this: unknown,
      _key: string,
      value: unknown,
      context?: { source?: string },
    ): unknown {
      if (typeof value !== 'number') return value;
      const source = context?.source;
      if (source === undefined) return value;
      if (!/^-?\d+$/.test(source)) return value;
      const asBig = BigInt(source);
      if (asBig > BigInt(Number.MAX_SAFE_INTEGER) || asBig < BigInt(-Number.MAX_SAFE_INTEGER)) {
        return asBig;
      }
      return value;
    },
  );
}

function loadVectors(): VectorFile {
  const text = readFileSync(VECTORS_PATH, 'utf-8');
  return parseJsonWithBigInts(text) as VectorFile;
}

function buildSubject(raw: RawSubjectRef | undefined): SubjectRef | null {
  if (!raw) return null;
  return makeSubjectRef(raw.scheme, raw.value);
}

function buildDraft(raw: RawDraft): EventDraft {
  return makeEventDraft({
    event_type: raw.event_type,
    actor: raw.actor,
    payload: raw.payload ?? {},
    subject_ref: buildSubject(raw.subject_ref),
    session_id: raw.session_id ?? null,
    reference_db_ref: raw.reference_db_ref ?? null,
    matched_input_ref: raw.matched_input_ref ?? null,
    human_verifier: buildSubject(raw.human_verifier),
  });
}

function bytesToHex(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString('hex');
}

function headFromEntry(entry: VectorEntry): ChainHead {
  return {
    seq: entry.seq,
    event_hash: Uint8Array.from(Buffer.from(entry.event_hash_hex, 'hex')),
  };
}

describe('cross-language conformance vs Python vectors.json', () => {
  const vectors = loadVectors();

  it('schema_version matches', () => {
    expect(vectors.schema_version).toBe(SCHEMA_VERSION);
  });

  it('expected 10 entries', () => {
    expect(vectors.entries).toHaveLength(10);
  });

  for (let index = 0; index < 10; index++) {
    const entry = vectors.entries[index] as VectorEntry;
    it(`vector ${index} (${entry.name}) reproduces event_hash`, () => {
      const draft = buildDraft(entry.draft);
      const head =
        index === 0 ? genesisHead() : headFromEntry(vectors.entries[index - 1] as VectorEntry);
      const ts = new Date(entry.timestamp);
      const chained = chainExtend(head, draft, { now: ts, event_id: entry.event_id });
      expect(bytesToHex(chained.event_hash)).toBe(entry.event_hash_hex);
      const sha = createHash('sha256').update(canonicalize(chained.event)).digest();
      expect(Buffer.from(sha).toString('hex')).toBe(entry.canonical_bytes_sha256_hex);
      expect(bytesToHex(chained.prev_hash)).toBe(entry.prev_hash_hex);
      expect(chained.seq).toBe(entry.seq);
    });
  }

  it('final chain head reproduces', () => {
    let head = genesisHead();
    const chain: ChainedEvent[] = [];
    for (const entry of vectors.entries) {
      const chained = chainExtend(head, buildDraft(entry.draft), {
        now: new Date(entry.timestamp),
        event_id: entry.event_id,
      });
      chain.push(chained);
      head = headOf(chain);
    }
    expect(bytesToHex(head.event_hash)).toBe(vectors.final_chain_head_hex);
  });
});
