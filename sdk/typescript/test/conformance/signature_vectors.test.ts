// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * 16-assertion T6 conformance gate per
 * `docs/architecture/adr_0005_t6_review_20260517.md` § 4.
 *
 * Reads the frozen `sdk/python/tests/conformance/signature_vectors.json`
 * (T7 artefact) and replays every vector through the TypeScript signing
 * stack. Any drift between Python and TypeScript SDKs surfaces here.
 *
 * Locked from R2 mitigation: `readFileSync(...) + JSON.parse(...)`. No
 * `import ... assert/with { type: 'json' }` (unstable across Node 22
 * minors).
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { canonicalize } from '../../src/canonical.js';
import { chainExtend, genesisHead, SCHEMA_VERSION } from '../../src/hashchain.js';
import {
  buildPerEventPayload,
  buildSegmentHeadPayload,
  deserializeSignatureRecord,
  deriveKeyId,
  InMemoryKeyProvider,
  parseTrustRoots,
  Signer,
  type SerializedSignatureRecord,
  type SignatureRecord,
  type SignatureStatus,
  type TrustRoots,
  verifyChainWithSignatures,
} from '../../src/index.js';
import { type ChainHead, type ChainedEvent, makeEventDraft } from '../../src/types.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const VECTORS_PATH = resolve(
  __dirname,
  '..',
  '..',
  '..',
  'python',
  'tests',
  'conformance',
  'signature_vectors.json',
);

interface RawTrustRoot {
  key_id: string;
  public_key_der_b64: string;
  valid_from: string;
  valid_until: string;
  provider_id?: string;
  label?: string;
}

interface RawVector {
  name: string;
  input: {
    chain_id: string;
    mode: 'segment_head' | 'per_event';
    seed_hex: string;
    signed_event_hash_hex: string;
    signed_seq: number;
  };
  canonical_payload_b64: string;
  record?: SerializedSignatureRecord;
  records?: SerializedSignatureRecord[];
  trust_roots: RawTrustRoot[];
  expected_verifier_status: SignatureStatus;
}

interface RawVectorsFile {
  $schema_version: number;
  frozen_at: string;
  shared_chain: {
    chain_id_prefix: string;
    verification_time: string;
    events: { seq: number; event_hash_hex: string }[];
  };
  vectors: RawVector[];
}

const VECTORS: RawVectorsFile = JSON.parse(readFileSync(VECTORS_PATH, 'utf-8')) as RawVectorsFile;

function hexToBytes(hex: string): Uint8Array {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

function b64ToBytes(b64: string): Uint8Array {
  return new Uint8Array(Buffer.from(b64, 'base64'));
}

function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

/** Reconstruct the shared 5-event chain frozen in `signature_vectors.json`. */
function rebuildChain(): ChainedEvent[] {
  const NOW = new Date('2026-05-17T12:00:00.000Z');
  const chain: ChainedEvent[] = [];
  let head: ChainHead = genesisHead();
  for (let i = 0; i < 5; i++) {
    const draft = makeEventDraft({
      event_type: 'eval_event',
      actor: `a${i}`,
      payload: { i },
    });
    const ev = chainExtend(head, draft, {
      now: NOW,
      event_id: `00000000-0000-7000-8000-${i.toString().padStart(12, '0')}`,
    });
    chain.push(ev);
    head = { seq: ev.seq, event_hash: ev.event_hash };
  }
  return chain;
}

function trustRootsFromVector(vec: RawVector): TrustRoots {
  return parseTrustRoots(
    {
      version: 1,
      keys: vec.trust_roots.map((tr) => ({
        key_id: tr.key_id,
        public_key_der_b64: tr.public_key_der_b64,
        valid_from: tr.valid_from,
        valid_until: tr.valid_until,
      })),
    },
    `vector:${vec.name}`,
  );
}

function recordsOf(vec: RawVector): SignatureRecord[] {
  const serialised = vec.records ?? (vec.record ? [vec.record] : []);
  return serialised.map((r) => deserializeSignatureRecord(r));
}

describe('T6 conformance: signature_vectors.json (16 assertions)', () => {
  const CHAIN = rebuildChain();
  const NOW = new Date('2026-05-17T12:00:00.000Z');
  const ZERO_SEED = new Uint8Array(32); // 0x00 × 32
  const ONE_SEED = new Uint8Array(32).fill(0x01);

  const VEC1 = VECTORS.vectors[0] as RawVector;
  const VEC2 = VECTORS.vectors[1] as RawVector;
  const VEC3 = VECTORS.vectors[2] as RawVector;
  const VEC4 = VECTORS.vectors[3] as RawVector;
  const VEC5 = VECTORS.vectors[4] as RawVector;

  it('sanity — file loads + has 5 vectors', () => {
    expect(VECTORS.$schema_version).toBe(1);
    expect(VECTORS.vectors.length).toBe(5);
    expect(CHAIN.length).toBe(5);
    // The TS-rebuilt chain matches the frozen event_hashes (sanity).
    for (let i = 0; i < 5; i++) {
      const expectedHex = VECTORS.shared_chain.events[i]?.event_hash_hex ?? '';
      const ev = CHAIN[i] as ChainedEvent;
      expect(Buffer.from(ev.event_hash).toString('hex')).toBe(expectedHex);
    }
  });

  // Assertion #1 (vec1) — segment-head payload byte-equal.
  it('#1 vec1: buildSegmentHeadPayload byte-equal to canonical_payload_b64', () => {
    const head: ChainHead = {
      seq: 4,
      event_hash: (CHAIN[4] as ChainedEvent).event_hash,
    };
    const ours = buildSegmentHeadPayload('vec-1', head);
    expect(bytesEqual(ours, b64ToBytes(VEC1.canonical_payload_b64))).toBe(true);
  });

  // Assertion #2 (vec1) — deriveKeyId of vector pubkey matches.
  it('#2 vec1: deriveKeyId(public_key_der_b64) === record.key_id', () => {
    const record = VEC1.record as SerializedSignatureRecord;
    expect(deriveKeyId(b64ToBytes(record.public_key_der_b64))).toBe(record.key_id);
  });

  // Assertion #3 (vec1) — R1 catch: TS InMemoryKeyProvider SPKI byte-equal.
  it('#3 vec1: InMemoryKeyProvider(seed=0x00×32).publicKeyDer byte-equal to vector', () => {
    const provider = new InMemoryKeyProvider({ seed: ZERO_SEED });
    const mat = provider.getSigningMaterial();
    const record = VEC1.record as SerializedSignatureRecord;
    const expected = b64ToBytes(record.public_key_der_b64);
    expect(bytesEqual(mat.publicKeyDer, expected)).toBe(true);
  });

  // Assertion #4 (vec1) — verifier valid, count=5, first_bad=null.
  it('#4 vec1: verifyChainWithSignatures → valid, count=5, first_bad=null', () => {
    const records = recordsOf(VEC1);
    const trustRoots = trustRootsFromVector(VEC1);
    const result = verifyChainWithSignatures(CHAIN, records, {
      chain_id: VEC1.input.chain_id,
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    expect(result.signature_status).toBe('valid');
    expect(result.signed_segment_count).toBe(5);
    expect(result.first_bad_signature_index).toBeNull();
  });

  // Assertion #5 (vec2) — per-event payload byte-equal.
  it('#5 vec2: buildPerEventPayload byte-equal to canonical_payload_b64', () => {
    const ours = buildPerEventPayload((CHAIN[2] as ChainedEvent).event);
    expect(bytesEqual(ours, b64ToBytes(VEC2.canonical_payload_b64))).toBe(true);
  });

  // Assertion #6 (vec2) — per-event verifier valid, count=1.
  it('#6 vec2: verifier returns valid, count=1', () => {
    const records = recordsOf(VEC2);
    const trustRoots = trustRootsFromVector(VEC2);
    const result = verifyChainWithSignatures(CHAIN, records, {
      chain_id: VEC2.input.chain_id,
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    expect(result.signature_status).toBe('valid');
    expect(result.signed_segment_count).toBe(1);
  });

  // Assertion #7 (vec3) — multi-signer plurality: both valid, count=5.
  it('#7 vec3: both multi-signer records valid, bundle valid, count=5', () => {
    const records = recordsOf(VEC3);
    expect(records.length).toBe(2);
    const trustRoots = trustRootsFromVector(VEC3);
    const result = verifyChainWithSignatures(CHAIN, records, {
      chain_id: VEC3.input.chain_id,
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    expect(result.signature_status).toBe('valid');
    expect(result.signed_segment_count).toBe(5);
    expect(result.signature_results.every((r) => r.status === 'valid')).toBe(true);
  });

  // Assertion #8 (vec3) — same payload, different key_id+signature.
  it('#8 vec3: two records share signed_payload, differ in key_id+signature', () => {
    const records = recordsOf(VEC3);
    const a = records[0] as SignatureRecord;
    const b = records[1] as SignatureRecord;
    expect(bytesEqual(a.signed_payload, b.signed_payload)).toBe(true);
    expect(a.key_id).not.toBe(b.key_id);
    expect(bytesEqual(a.signature, b.signature)).toBe(false);
  });

  // Assertion #9 (vec4) — unknown_key, first_bad=0.
  it('#9 vec4: verifier returns unknown_key, first_bad=0', () => {
    const records = recordsOf(VEC4);
    const trustRoots = trustRootsFromVector(VEC4);
    const result = verifyChainWithSignatures(CHAIN, records, {
      chain_id: VEC4.input.chain_id,
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    expect(result.signature_status).toBe('unknown_key');
    expect(result.first_bad_signature_index).toBe(0);
    expect(result.signed_segment_count).toBe(0);
  });

  // Assertion #10 (vec4) — reason includes "not in trust roots".
  it('#10 vec4: reason includes "not in trust roots"', () => {
    const records = recordsOf(VEC4);
    const trustRoots = trustRootsFromVector(VEC4);
    const result = verifyChainWithSignatures(CHAIN, records, {
      chain_id: VEC4.input.chain_id,
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    const firstReason = result.signature_results[0]?.reason ?? '';
    expect(firstReason).toContain('not in trust roots');
  });

  // Assertion #11 (vec5) — invalid, first_bad=0.
  it('#11 vec5: verifier returns invalid, first_bad=0', () => {
    const records = recordsOf(VEC5);
    const trustRoots = trustRootsFromVector(VEC5);
    const result = verifyChainWithSignatures(CHAIN, records, {
      chain_id: VEC5.input.chain_id,
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    expect(result.signature_status).toBe('invalid');
    expect(result.first_bad_signature_index).toBe(0);
    expect(result.signed_segment_count).toBe(0);
  });

  // Assertion #12 (vec5) — reason includes "Ed25519 verify failed".
  it('#12 vec5: reason includes "Ed25519 verify failed"', () => {
    const records = recordsOf(VEC5);
    const trustRoots = trustRootsFromVector(VEC5);
    const result = verifyChainWithSignatures(CHAIN, records, {
      chain_id: VEC5.input.chain_id,
      trust_roots: trustRoots,
      verification_time: NOW,
    });
    const firstReason = result.signature_results[0]?.reason ?? '';
    expect(firstReason).toContain('Ed25519 verify failed');
  });

  // Assertion #13 (all) — every signature is exactly 64 bytes (Ed25519).
  it('#13 every record signature is exactly 64 bytes', () => {
    for (const vec of VECTORS.vectors) {
      for (const rec of recordsOf(vec)) {
        expect(rec.signature.length).toBe(64);
      }
    }
  });

  // Assertion #14 (all) — every key_id matches /^[0-9a-f]{32}$/.
  it('#14 every key_id matches /^[0-9a-f]{32}$/', () => {
    const re = /^[0-9a-f]{32}$/;
    for (const vec of VECTORS.vectors) {
      const serialised = vec.records ?? (vec.record ? [vec.record] : []);
      for (const r of serialised) {
        expect(re.test(r.key_id)).toBe(true);
      }
    }
  });

  // Assertion #15 (v1+v5) — same seed → identical key_id.
  it('#15 seed=0x00×32 always produces key_id=339e2ff917630507b6a423b5ce084e28', () => {
    const provider = new InMemoryKeyProvider({ seed: ZERO_SEED });
    const mat = provider.getSigningMaterial();
    expect(mat.keyId).toBe('339e2ff917630507b6a423b5ce084e28');
    expect((VEC1.record as SerializedSignatureRecord).key_id).toBe(mat.keyId);
    expect((VEC5.record as SerializedSignatureRecord).key_id).toBe(mat.keyId);
  });

  // Assertion #16 (vec1) — end-to-end byte-equal signature.
  it('#16 vec1: TS Signer.signSegmentHead byte-equal to vector signature_hex', () => {
    const provider = new InMemoryKeyProvider({ seed: ZERO_SEED });
    const signer = new Signer({
      chain_id: 'vec-1',
      key_provider: provider,
      now: () => NOW,
    });
    const head: ChainHead = {
      seq: 4,
      event_hash: (CHAIN[4] as ChainedEvent).event_hash,
    };
    const records = signer.signSegmentHead(head);
    expect(records.length).toBe(1);
    const ours = (records[0] as SignatureRecord).signature;
    const expected = hexToBytes((VEC1.record as SerializedSignatureRecord).signature_hex);
    expect(bytesEqual(ours, expected)).toBe(true);
  });

  // Defensive — silence unused-var warnings (ONE_SEED kept for future
  // expansion via per_event vector derivation if needed).
  it('vec2 seed=0x01×32 sanity (informational)', () => {
    void ONE_SEED;
    void canonicalize;
    expect(SCHEMA_VERSION).toBe(1);
  });
});
