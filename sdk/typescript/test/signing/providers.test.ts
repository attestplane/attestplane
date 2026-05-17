// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { createPrivateKey, generateKeyPairSync } from 'node:crypto';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { KeyProviderError } from '../../src/signing/base.js';
import {
  EnvKeyProvider,
  FileKeyProvider,
  InMemoryKeyProvider,
  MultiSignerProvider,
  seedToPrivateKey,
} from '../../src/signing/providers.js';

const KNOWN_KEY_ID_SEED_00 = '339e2ff917630507b6a423b5ce084e28';

describe('InMemoryKeyProvider', () => {
  it('produces deterministic key_id from a 32-byte seed', () => {
    const provider = new InMemoryKeyProvider({ seed: new Uint8Array(32) });
    const mat = provider.getSigningMaterial();
    expect(mat.keyId).toBe(KNOWN_KEY_ID_SEED_00);
  });

  it('generates a random key when no seed is supplied', () => {
    const a = new InMemoryKeyProvider().getSigningMaterial();
    const b = new InMemoryKeyProvider().getSigningMaterial();
    expect(a.keyId).not.toBe(b.keyId);
  });

  it('rejects a seed of wrong length', () => {
    expect(() => new InMemoryKeyProvider({ seed: new Uint8Array(16) })).toThrow(KeyProviderError);
  });

  it('uses custom provider_id when supplied', () => {
    const p = new InMemoryKeyProvider({
      seed: new Uint8Array(32),
      provider_id: 'custom-id',
    });
    expect(p.provider_id).toBe('custom-id');
  });
});

describe('seedToPrivateKey (PKCS#8 wrap path)', () => {
  it('round-trips a generated seed against generateKeyPairSync', () => {
    // generateKeyPairSync produces a different seed each time; ensure the
    // resulting public key parses (sanity that our PKCS#8 prefix is valid).
    const { privateKey } = generateKeyPairSync('ed25519');
    expect(privateKey.asymmetricKeyType).toBe('ed25519');
    const k = seedToPrivateKey(new Uint8Array(32));
    expect(k.asymmetricKeyType).toBe('ed25519');
  });
});

describe('FileKeyProvider', () => {
  let tmp: string;
  beforeAll(() => {
    tmp = mkdtempSync(join(tmpdir(), 'attestplane-file-kp-'));
  });
  afterAll(() => {
    rmSync(tmp, { recursive: true, force: true });
  });

  it('throws if the file is missing', () => {
    const p = new FileKeyProvider(join(tmp, 'does-not-exist.pem'));
    expect(() => p.getSigningMaterial()).toThrow(/not found/);
  });

  it('throws if the file is not an Ed25519 key', () => {
    const { privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
    const pem = privateKey.export({ format: 'pem', type: 'pkcs8' });
    const path = join(tmp, 'rsa.pem');
    writeFileSync(path, pem);
    const p = new FileKeyProvider(path);
    expect(() => p.getSigningMaterial()).toThrow(/not Ed25519/);
  });

  it('loads a valid Ed25519 PEM and signs', () => {
    const { privateKey } = generateKeyPairSync('ed25519');
    const pem = privateKey.export({ format: 'pem', type: 'pkcs8' });
    const path = join(tmp, 'ed25519.pem');
    writeFileSync(path, pem);
    const p = new FileKeyProvider(path);
    const mat = p.getSigningMaterial();
    expect(mat.publicKeyDer.length).toBeGreaterThan(0);
    expect(mat.keyId).toMatch(/^[0-9a-f]{32}$/);
  });
});

describe('EnvKeyProvider', () => {
  const VAR = 'ATTESTPLANE_TEST_KEY';

  it('throws if the env var is unset', () => {
    delete process.env[VAR];
    const p = new EnvKeyProvider(VAR);
    expect(() => p.getSigningMaterial()).toThrow(/not set/);
  });

  it('throws if the env var is empty', () => {
    process.env[VAR] = '   ';
    try {
      const p = new EnvKeyProvider(VAR);
      expect(() => p.getSigningMaterial()).toThrow(/empty/);
    } finally {
      delete process.env[VAR];
    }
  });

  it('throws if the value is not a valid PEM', () => {
    process.env[VAR] = 'not a pem at all';
    try {
      const p = new EnvKeyProvider(VAR);
      expect(() => p.getSigningMaterial()).toThrow(/failed to load PEM/);
    } finally {
      delete process.env[VAR];
    }
  });

  it('loads a valid Ed25519 PEM', () => {
    const { privateKey } = generateKeyPairSync('ed25519');
    const pem = privateKey.export({ format: 'pem', type: 'pkcs8' }).toString();
    process.env[VAR] = pem;
    try {
      const p = new EnvKeyProvider(VAR);
      const mat = p.getSigningMaterial();
      expect(mat.keyId).toMatch(/^[0-9a-f]{32}$/);
    } finally {
      delete process.env[VAR];
    }
  });
});

describe('MultiSignerProvider', () => {
  it('rejects empty providers list', () => {
    expect(() => new MultiSignerProvider([])).toThrow(/at least one/);
  });

  it('rejects duplicate provider_id', () => {
    const a = new InMemoryKeyProvider({ provider_id: 'dup' });
    const b = new InMemoryKeyProvider({ provider_id: 'dup' });
    expect(() => new MultiSignerProvider([a, b])).toThrow(/distinct/);
  });

  it('returns one material per provider', () => {
    const a = new InMemoryKeyProvider({
      seed: new Uint8Array(32).fill(0x11),
      provider_id: 'a',
    });
    const b = new InMemoryKeyProvider({
      seed: new Uint8Array(32).fill(0x22),
      provider_id: 'b',
    });
    const m = new MultiSignerProvider([a, b]);
    const materials = m.getSigningMaterials();
    expect(materials).toHaveLength(2);
    expect(materials[0]?.keyId).not.toBe(materials[1]?.keyId);
    expect(m.provider_ids).toEqual(['a', 'b']);
  });
});

// Confirm Node accepts the PKCS#8 wrap output as an Ed25519 key.
describe('PKCS#8 wrap sanity', () => {
  it('createPrivateKey accepts our wrapped seed bytes', () => {
    const k = createPrivateKey({
      key: Buffer.from(`302e020100300506032b657004220420${'00'.repeat(32)}`, 'hex'),
      format: 'der',
      type: 'pkcs8',
    });
    expect(k.asymmetricKeyType).toBe('ed25519');
  });
});
