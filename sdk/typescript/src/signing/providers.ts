// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Concrete `KeyProvider` implementations — TypeScript mirror of
 * `sdk/python/src/attestplane/signing/providers.py` (architect plan § 1 D
 * + T6 review decision 4).
 *
 * Four providers:
 *
 * - `InMemoryKeyProvider` — tests / dev; optional 32-byte seed for
 *   deterministic keys.
 * - `FileKeyProvider` — PKCS#8 PEM file on disk.
 * - `EnvKeyProvider` — PKCS#8 PEM bytes from `process.env`.
 * - `MultiSignerProvider` — plurality (any-of-n) composite per architect
 *   plan § 1 H. NOT a `KeyProvider` subclass: returns an array.
 *
 * Ed25519 recipe (load-bearing R1 risk mitigation):
 *
 * - **Seed → KeyObject**: PKCS#8 DER wrap path (RFC 8410). Node 22's
 *   JWK importer requires the public `x` alongside `d`, which would
 *   force us to recompute the point first — the PKCS#8 path wraps the
 *   raw 32-byte seed with a constant 16-byte prefix, byte-equal to the
 *   blob `cryptography`'s `Ed25519PrivateKey.from_private_bytes(seed)`
 *   produces when serialised. This deviates from the architect's
 *   initial JWK recipe per the T6 implementation revision dated
 *   2026-05-17 (see `docs/architecture/adr_0005_t6_review_20260517.md`).
 * - **SPKI DER export**: via the intermediate
 *   `createPublicKey(privateKey).export({format:'der', type:'spki'})` so
 *   the public-key bytes are byte-equal to Python's
 *   `Ed25519PrivateKey.public_key().public_bytes(DER, SubjectPublicKeyInfo)`.
 */

import {
  type KeyObject,
  createPrivateKey,
  createPublicKey,
  generateKeyPairSync,
} from 'node:crypto';
import { readFileSync } from 'node:fs';

import {
  KeyProvider,
  KeyProviderError,
  SIGNATURE_SCHEMA_VERSION,
  type SigningMaterial,
  deriveKeyId,
} from './base.js';

const ED25519_SEED_LEN = 32;

/**
 * RFC 8410 Ed25519 PKCS#8 wrapper — constant 16-byte prefix concatenated
 * with the 32-byte seed produces a valid 48-byte PKCS#8 DER blob. Used
 * because Node 22's JWK importer requires the public `x` field alongside
 * `d`, which would force us to recompute the public point first — the
 * PKCS#8 path sidesteps that entirely and is byte-equal to the recipe
 * used by Python `cryptography`'s `Ed25519PrivateKey.from_private_bytes()`.
 *
 * Decode: `SEQUENCE { INTEGER 0, AlgorithmIdentifier {OID 1.3.101.112},
 * OCTET STRING { OCTET STRING <32 byte seed> } }`.
 */
const PKCS8_ED25519_PREFIX = Buffer.from('302e020100300506032b657004220420', 'hex');

export function seedToPrivateKey(seed: Uint8Array): KeyObject {
  if (seed.length !== ED25519_SEED_LEN) {
    throw new KeyProviderError(
      `Ed25519 seed must be exactly ${ED25519_SEED_LEN} bytes, got ${seed.length}`,
    );
  }
  const pkcs8 = Buffer.concat([PKCS8_ED25519_PREFIX, Buffer.from(seed)]);
  return createPrivateKey({ key: pkcs8, format: 'der', type: 'pkcs8' });
}

export function exportPublicKeyDer(privateKey: KeyObject): Uint8Array {
  const pub = createPublicKey(privateKey);
  return new Uint8Array(pub.export({ format: 'der', type: 'spki' }));
}

function loadPemPrivateKey(
  pemBytes: Buffer | string,
  passphrase: Buffer | undefined,
  context: string,
): KeyObject {
  let key: KeyObject;
  try {
    key = createPrivateKey(
      passphrase !== undefined
        ? { key: pemBytes, format: 'pem', passphrase }
        : { key: pemBytes, format: 'pem' },
    );
  } catch (exc) {
    throw new KeyProviderError(`${context}: failed to load PEM key: ${(exc as Error).message}`);
  }
  if (key.asymmetricKeyType !== 'ed25519') {
    throw new KeyProviderError(
      `${context}: key is not Ed25519 (got asymmetricKeyType=${String(key.asymmetricKeyType)})`,
    );
  }
  return key;
}

function materialFromPrivateKey(privateKey: KeyObject): SigningMaterial {
  const publicKeyDer = exportPublicKeyDer(privateKey);
  return {
    privateKey,
    publicKeyDer,
    signingCertChain: [],
    keyId: deriveKeyId(publicKeyDer),
  };
}

// ----- InMemoryKeyProvider -----

export interface InMemoryKeyProviderOptions {
  readonly seed?: Uint8Array;
  readonly provider_id?: string;
}

/**
 * Holds an Ed25519 keypair in process memory.
 *
 * Suitable for tests, ephemeral substrates, and deployments where the
 * key is generated at startup and never persisted.
 *
 * When `seed` is supplied, the same seed always produces the same
 * Ed25519 key — required for conformance vectors. When `seed` is
 * absent, a fresh random key is generated via Node `crypto`
 * `generateKeyPairSync('ed25519')`.
 */
export class InMemoryKeyProvider extends KeyProvider {
  readonly provider_id: string;
  readonly schema_version = SIGNATURE_SCHEMA_VERSION;
  private readonly _privateKey: KeyObject;

  constructor(options: InMemoryKeyProviderOptions = {}) {
    super();
    const providerId = options.provider_id ?? 'in-memory';
    if (!providerId) {
      throw new Error('InMemoryKeyProvider provider_id must be non-empty');
    }
    this.provider_id = providerId;
    if (options.seed !== undefined) {
      this._privateKey = seedToPrivateKey(options.seed);
    } else {
      const { privateKey } = generateKeyPairSync('ed25519');
      this._privateKey = privateKey;
    }
  }

  getSigningMaterial(): SigningMaterial {
    return materialFromPrivateKey(this._privateKey);
  }
}

// ----- FileKeyProvider -----

export interface FileKeyProviderOptions {
  readonly passphrase?: Uint8Array;
  readonly provider_id?: string;
}

/**
 * Loads an Ed25519 private key from a PKCS#8 PEM file on disk.
 *
 * The file is read on EVERY `getSigningMaterial()` call; intentional
 * design so file rotation (deployer replaces the file out-of-band) is
 * picked up on the next signing call.
 */
export class FileKeyProvider extends KeyProvider {
  readonly provider_id: string;
  readonly schema_version = SIGNATURE_SCHEMA_VERSION;
  private readonly _path: string;
  private readonly _passphrase: Buffer | undefined;

  constructor(path: string, options: FileKeyProviderOptions = {}) {
    super();
    if (!path) {
      throw new Error('FileKeyProvider path must be non-empty');
    }
    this._path = path;
    this._passphrase =
      options.passphrase !== undefined ? Buffer.from(options.passphrase) : undefined;
    this.provider_id = options.provider_id ?? `file:${path}`;
  }

  getSigningMaterial(): SigningMaterial {
    let pemBytes: Buffer;
    try {
      pemBytes = readFileSync(this._path);
    } catch (exc) {
      const err = exc as NodeJS.ErrnoException;
      if (err.code === 'ENOENT') {
        throw new KeyProviderError(`FileKeyProvider: key file not found at ${this._path}`);
      }
      throw new KeyProviderError(`FileKeyProvider: cannot read ${this._path}: ${err.message}`);
    }
    const key = loadPemPrivateKey(pemBytes, this._passphrase, `FileKeyProvider(${this._path})`);
    return materialFromPrivateKey(key);
  }
}

// ----- EnvKeyProvider -----

export interface EnvKeyProviderOptions {
  readonly passphrase?: Uint8Array;
  readonly provider_id?: string;
}

/**
 * Loads an Ed25519 private key from `process.env[envVar]`.
 *
 * The env var must contain a PEM-encoded PKCS#8 key (typical when a
 * secret manager injects the key at runtime).
 */
export class EnvKeyProvider extends KeyProvider {
  readonly provider_id: string;
  readonly schema_version = SIGNATURE_SCHEMA_VERSION;
  private readonly _envVar: string;
  private readonly _passphrase: Buffer | undefined;

  constructor(envVar: string, options: EnvKeyProviderOptions = {}) {
    super();
    if (!envVar) {
      throw new Error('EnvKeyProvider envVar must be non-empty');
    }
    this._envVar = envVar;
    this._passphrase =
      options.passphrase !== undefined ? Buffer.from(options.passphrase) : undefined;
    this.provider_id = options.provider_id ?? `env:${envVar}`;
  }

  getSigningMaterial(): SigningMaterial {
    const pemText = process.env[this._envVar];
    if (pemText === undefined) {
      throw new KeyProviderError(
        `EnvKeyProvider: env var ${JSON.stringify(this._envVar)} is not set`,
      );
    }
    if (pemText.trim().length === 0) {
      throw new KeyProviderError(
        `EnvKeyProvider: env var ${JSON.stringify(this._envVar)} is empty`,
      );
    }
    const key = loadPemPrivateKey(pemText, this._passphrase, `EnvKeyProvider(${this._envVar})`);
    return materialFromPrivateKey(key);
  }
}

// ----- MultiSignerProvider -----

/**
 * Plurality (any-of-n) composite per architect plan § 1 H.
 *
 * Holds N `KeyProvider` instances and exposes their signing materials
 * as a list. The `Signer` iterates and produces one `SignatureRecord`
 * per provider per signed event.
 *
 * Intentionally NOT a `KeyProvider` subclass: a `KeyProvider` returns
 * one `SigningMaterial`; this composite returns a list.
 *
 * Verification semantics: any valid signature from any trust-rooted
 * `key_id` counts as "segment signed". Plurality, NOT k-of-n threshold
 * (architect plan § 1 H — threshold explicitly out of scope).
 */
export class MultiSignerProvider {
  private readonly _providers: readonly KeyProvider[];

  constructor(providers: readonly KeyProvider[]) {
    if (providers.length === 0) {
      throw new Error('MultiSignerProvider requires at least one provider');
    }
    const seen = new Set<string>();
    for (const p of providers) {
      if (seen.has(p.provider_id)) {
        throw new Error('MultiSignerProvider providers must have distinct provider_id values');
      }
      seen.add(p.provider_id);
      if (p.schema_version !== SIGNATURE_SCHEMA_VERSION) {
        throw new Error(
          `provider ${JSON.stringify(p.provider_id)} has schema_version=` +
            `${p.schema_version}; this composite handles only ` +
            `SIGNATURE_SCHEMA_VERSION=${SIGNATURE_SCHEMA_VERSION}`,
        );
      }
    }
    this._providers = [...providers];
  }

  get provider_ids(): readonly string[] {
    return this._providers.map((p) => p.provider_id);
  }

  getSigningMaterials(): SigningMaterial[] {
    return this._providers.map((p) => p.getSigningMaterial());
  }
}
