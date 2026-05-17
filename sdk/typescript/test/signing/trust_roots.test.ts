// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { InMemoryKeyProvider } from '../../src/signing/providers.js';
import { TrustRootsError, loadTrustRoots, parseTrustRoots } from '../../src/signing/trust_roots.js';

function makeValidPayload() {
  const provider = new InMemoryKeyProvider({
    seed: new Uint8Array(32).fill(0x05),
  });
  const mat = provider.getSigningMaterial();
  return {
    keyId: mat.keyId,
    pubB64: Buffer.from(mat.publicKeyDer).toString('base64'),
    valid: {
      version: 1,
      keys: [
        {
          key_id: mat.keyId,
          public_key_der_b64: Buffer.from(mat.publicKeyDer).toString('base64'),
          valid_from: '2026-01-01T00:00:00Z',
          valid_until: '2027-01-01T00:00:00Z',
        },
      ],
    },
  };
}

describe('parseTrustRoots', () => {
  it('accepts a valid v1 payload', () => {
    const { valid, keyId } = makeValidPayload();
    const tr = parseTrustRoots(valid);
    expect(tr.entries).toHaveLength(1);
    expect(tr.entries[0]?.key_id).toBe(keyId);
    expect(tr.lookup(keyId)?.key_id).toBe(keyId);
    expect(tr.lookup('does-not-exist')).toBeNull();
  });

  it('rejects non-object top level', () => {
    expect(() => parseTrustRoots([] as unknown)).toThrow(TrustRootsError);
    expect(() => parseTrustRoots(null)).toThrow(TrustRootsError);
  });

  it('rejects wrong version', () => {
    const { valid } = makeValidPayload();
    expect(() => parseTrustRoots({ ...valid, version: 2 })).toThrow(/version/);
  });

  it('rejects empty keys list', () => {
    const { valid } = makeValidPayload();
    expect(() => parseTrustRoots({ ...valid, keys: [] })).toThrow(/at least one/);
  });

  it('rejects unexpected top-level fields', () => {
    const { valid } = makeValidPayload();
    expect(() => parseTrustRoots({ ...valid, extra: 'no' } as unknown)).toThrow(/unexpected/);
  });

  it('rejects entry missing required fields', () => {
    const { valid } = makeValidPayload();
    const broken = {
      ...valid,
      keys: [{ key_id: valid.keys[0]?.key_id }],
    };
    expect(() => parseTrustRoots(broken)).toThrow(/missing required/);
  });

  it('rejects entry with unexpected fields', () => {
    const { valid } = makeValidPayload();
    const broken = {
      ...valid,
      keys: [{ ...(valid.keys[0] as object), bogus: 'x' }],
    };
    expect(() => parseTrustRoots(broken)).toThrow(/unexpected fields/);
  });

  it('rejects key_id that does not match derived value', () => {
    const { valid } = makeValidPayload();
    const broken = {
      ...valid,
      keys: [
        {
          ...(valid.keys[0] as object),
          key_id: '0'.repeat(32),
        },
      ],
    };
    expect(() => parseTrustRoots(broken)).toThrow(/does not match/);
  });

  it('rejects malformed key_id format', () => {
    const { valid } = makeValidPayload();
    const broken = {
      ...valid,
      keys: [{ ...(valid.keys[0] as object), key_id: 'ZZ' }],
    };
    expect(() => parseTrustRoots(broken)).toThrow(/lowercase hex/);
  });

  it('rejects valid_from >= valid_until', () => {
    const { valid } = makeValidPayload();
    const broken = {
      ...valid,
      keys: [
        {
          ...(valid.keys[0] as object),
          valid_from: '2027-01-01T00:00:00Z',
          valid_until: '2026-01-01T00:00:00Z',
        },
      ],
    };
    expect(() => parseTrustRoots(broken)).toThrow(/strictly before/);
  });

  it('rejects naive (offset-less) datetime', () => {
    const { valid } = makeValidPayload();
    const broken = {
      ...valid,
      keys: [
        {
          ...(valid.keys[0] as object),
          valid_from: '2026-01-01T00:00:00',
        },
      ],
    };
    expect(() => parseTrustRoots(broken)).toThrow(/UTC-aware/);
  });

  it('rejects duplicate key_id', () => {
    const { valid } = makeValidPayload();
    const dup = {
      ...valid,
      keys: [valid.keys[0] as object, valid.keys[0] as object],
    };
    expect(() => parseTrustRoots(dup)).toThrow(/duplicate/);
  });
});

describe('loadTrustRoots (filesystem)', () => {
  let tmp: string;
  beforeAll(() => {
    tmp = mkdtempSync(join(tmpdir(), 'attestplane-tr-'));
  });
  afterAll(() => {
    rmSync(tmp, { recursive: true, force: true });
  });

  it('reads and parses a valid file', () => {
    const { valid } = makeValidPayload();
    const path = join(tmp, 'roots.json');
    writeFileSync(path, JSON.stringify(valid));
    const tr = loadTrustRoots(path);
    expect(tr.version).toBe(1);
  });

  it('throws on missing file', () => {
    expect(() => loadTrustRoots(join(tmp, 'missing.json'))).toThrow(/not found/);
  });

  it('rejects files > 1 MB', () => {
    const path = join(tmp, 'big.json');
    writeFileSync(path, `{}\n${'x'.repeat(1024 * 1024 + 1)}`);
    expect(() => loadTrustRoots(path)).toThrow(/exceeds 1 MB/);
  });

  it('reports JSON parse failure with path context', () => {
    const path = join(tmp, 'bad.json');
    writeFileSync(path, '{not valid json');
    expect(() => loadTrustRoots(path)).toThrow(/JSON parse failed/);
  });
});
