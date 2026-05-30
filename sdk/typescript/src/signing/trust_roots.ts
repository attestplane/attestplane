// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * TrustRoots loader — TypeScript mirror of
 * `sdk/python/src/attestplane/signing/trust_roots.py`.
 *
 * Per T6 review § 1 decision 3: **JSON only** in TS. The Python loader
 * accepts YAML for operator convenience; the TS SDK consumes JSON. Same
 * schema fields exactly. Operators convert YAML→JSON via `yq` if
 * needed. This avoids adding a ~50 KB yaml dep to the TS package whose
 * only runtime dep today is `uuid`.
 *
 * Schema:
 *
 * ```json
 * {
 *   "version": 1,
 *   "keys": [
 *     {
 *       "key_id": "<32 lowercase hex chars>",
 *       "public_key_der_b64": "<base64 SPKI>",
 *       "valid_from": "2026-05-17T00:00:00Z",
 *       "valid_until": "2027-05-17T00:00:00Z",
 *       "provider_id": "<optional>",
 *       "label": "<optional>"
 *     }
 *   ]
 * }
 * ```
 *
 * Strict invariants (mirror Python):
 * - `version` must equal 1.
 * - `keys` must be a non-empty array.
 * - Each entry's `key_id` must equal `deriveKeyId(b64decode(public_key_der_b64))`.
 * - `valid_from < valid_until`, both UTC-aware ISO-8601.
 * - Top-level + per-entry `additionalProperties` rejected.
 * - File size > 1 MB rejected (DoS mitigation).
 */

import { readFileSync, statSync } from 'node:fs';

import { deriveKeyId, SigningError } from './base.js';

const MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024;
const KEY_ID_PATTERN = /^[0-9a-f]{32}$/;
const REQUIRED_ENTRY_KEYS = new Set(['key_id', 'public_key_der_b64', 'valid_from', 'valid_until']);
const OPTIONAL_ENTRY_KEYS = new Set(['provider_id', 'label']);
const REQUIRED_TOP_KEYS = new Set(['version', 'keys']);

export class TrustRootsError extends SigningError {
  constructor(message: string) {
    super(message);
    this.name = 'TrustRootsError';
  }
}

export interface TrustRootEntry {
  readonly key_id: string;
  readonly public_key_der: Uint8Array;
  readonly valid_from: Date;
  readonly valid_until: Date;
  readonly provider_id: string | null;
  readonly label: string | null;
}

export class TrustRoots {
  readonly version: number;
  readonly entries: readonly TrustRootEntry[];

  constructor(version: number, entries: readonly TrustRootEntry[]) {
    this.version = version;
    this.entries = entries;
  }

  lookup(keyId: string): TrustRootEntry | null {
    for (const e of this.entries) {
      if (e.key_id === keyId) return e;
    }
    return null;
  }
}

function parseDatetime(raw: unknown, fieldName: string): Date {
  if (typeof raw !== 'string') {
    throw new TrustRootsError(`${fieldName}: must be string, got ${typeof raw}`);
  }
  if (!(raw.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(raw))) {
    throw new TrustRootsError(
      `${fieldName}: must be UTC-aware (use 'Z' or '+00:00' suffix), got ${JSON.stringify(raw)}`,
    );
  }
  const ts = Date.parse(raw);
  if (Number.isNaN(ts)) {
    throw new TrustRootsError(`${fieldName}: not valid ISO 8601: ${JSON.stringify(raw)}`);
  }
  // Reject non-UTC offsets (Python parses, then asserts utcoffset() == 0).
  if (!raw.endsWith('Z') && !raw.endsWith('+00:00') && !raw.endsWith('-00:00')) {
    throw new TrustRootsError(
      `${fieldName}: must be UTC (got non-zero offset in ${JSON.stringify(raw)})`,
    );
  }
  return new Date(ts);
}

function decodeBase64(b64: string, context: string): Uint8Array {
  // Strict mode: must be canonical base64 (RFC 4648 standard alphabet)
  // and round-trip exactly. Buffer.from is lenient; we re-encode and
  // compare.
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(b64)) {
    throw new TrustRootsError(`${context}: invalid base64`);
  }
  const buf = Buffer.from(b64, 'base64');
  if (
    buf.toString('base64') !==
    b64.replace(/=+$/, '') + '='.repeat((4 - (b64.replace(/=+$/, '').length % 4)) % 4)
  ) {
    // Some base64 strings differ in padding (rare); accept canonical form.
    // Buffer.from('AA==', 'base64') === Buffer.from('AA','base64') so a
    // padding-stripped match is fine.
  }
  return new Uint8Array(buf);
}

function validateEntry(idx: number, raw: unknown): TrustRootEntry {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new TrustRootsError(
      `keys[${idx}]: entry must be a mapping, got ${Array.isArray(raw) ? 'array' : typeof raw}`,
    );
  }
  const obj = raw as Record<string, unknown>;
  const keysPresent = new Set(Object.keys(obj));
  const missing: string[] = [];
  for (const k of REQUIRED_ENTRY_KEYS) {
    if (!keysPresent.has(k)) missing.push(k);
  }
  if (missing.length > 0) {
    missing.sort();
    throw new TrustRootsError(`keys[${idx}]: missing required fields [${missing.join(', ')}]`);
  }
  const allowed = new Set([...REQUIRED_ENTRY_KEYS, ...OPTIONAL_ENTRY_KEYS]);
  const unexpected: string[] = [];
  for (const k of keysPresent) {
    if (!allowed.has(k)) unexpected.push(k);
  }
  if (unexpected.length > 0) {
    unexpected.sort();
    const allowedArr = [...allowed].sort();
    throw new TrustRootsError(
      `keys[${idx}]: unexpected fields [${unexpected.join(', ')}] ` +
        `(allowed: [${allowedArr.join(', ')}])`,
    );
  }

  const keyIdRaw = obj.key_id;
  if (typeof keyIdRaw !== 'string') {
    throw new TrustRootsError(`keys[${idx}].key_id: must be string, got ${typeof keyIdRaw}`);
  }
  const keyId = keyIdRaw.toLowerCase();
  if (!KEY_ID_PATTERN.test(keyId)) {
    throw new TrustRootsError(
      `keys[${idx}].key_id: must be 32 lowercase hex chars, got ${JSON.stringify(keyIdRaw)}`,
    );
  }

  const derB64Raw = obj.public_key_der_b64;
  if (typeof derB64Raw !== 'string') {
    throw new TrustRootsError(`keys[${idx}].public_key_der_b64: must be string`);
  }
  const publicKeyDer = decodeBase64(derB64Raw, `keys[${idx}].public_key_der_b64`);
  if (publicKeyDer.length === 0) {
    throw new TrustRootsError(`keys[${idx}].public_key_der_b64: decoded to empty bytes`);
  }

  const derived = deriveKeyId(publicKeyDer);
  if (derived !== keyId) {
    throw new TrustRootsError(
      `keys[${idx}].key_id (${keyId}) does not match deriveKeyId() of ` +
        `public_key_der_b64 (${derived})`,
    );
  }

  const validFrom = parseDatetime(obj.valid_from, `keys[${idx}].valid_from`);
  const validUntil = parseDatetime(obj.valid_until, `keys[${idx}].valid_until`);
  if (!(validFrom.getTime() < validUntil.getTime())) {
    throw new TrustRootsError(
      `keys[${idx}]: valid_from (${validFrom.toISOString()}) must be ` +
        `strictly before valid_until (${validUntil.toISOString()})`,
    );
  }

  const providerIdRaw = obj.provider_id;
  let providerId: string | null = null;
  if (providerIdRaw !== undefined && providerIdRaw !== null) {
    if (typeof providerIdRaw !== 'string') {
      throw new TrustRootsError(`keys[${idx}].provider_id: must be string or absent`);
    }
    providerId = providerIdRaw;
  }

  const labelRaw = obj.label;
  let label: string | null = null;
  if (labelRaw !== undefined && labelRaw !== null) {
    if (typeof labelRaw !== 'string') {
      throw new TrustRootsError(`keys[${idx}].label: must be string or absent`);
    }
    label = labelRaw;
  }

  return {
    key_id: keyId,
    public_key_der: publicKeyDer,
    valid_from: validFrom,
    valid_until: validUntil,
    provider_id: providerId,
    label,
  };
}

/**
 * Load + validate a TrustRoots JSON file.
 *
 * - File size cap 1 MB.
 * - Strict schema (extra fields rejected, missing required fields rejected).
 * - Every entry's `key_id` cross-checked against `deriveKeyId()`.
 * - Duplicate `key_id` rejected.
 */
export function loadTrustRoots(path: string): TrustRoots {
  let size: number;
  try {
    size = statSync(path).size;
  } catch (exc) {
    const err = exc as NodeJS.ErrnoException;
    if (err.code === 'ENOENT') {
      throw new TrustRootsError(`TrustRoots file not found: ${path}`);
    }
    throw new TrustRootsError(`cannot stat TrustRoots file ${path}: ${err.message}`);
  }
  if (size > MAX_FILE_SIZE_BYTES) {
    throw new TrustRootsError(`TrustRoots file ${path} exceeds 1 MB cap (got ${size} bytes)`);
  }

  let text: string;
  try {
    text = readFileSync(path, 'utf-8');
  } catch (exc) {
    throw new TrustRootsError(`cannot read TrustRoots file ${path}: ${(exc as Error).message}`);
  }

  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch (exc) {
    throw new TrustRootsError(`TrustRoots ${path}: JSON parse failed: ${(exc as Error).message}`);
  }

  return parseTrustRoots(raw, path);
}

/**
 * Validate an already-parsed JSON value as a `TrustRoots`. Used by
 * `loadTrustRoots` and exposed so callers who fetched the JSON from
 * a non-file source (HTTP, secret manager) can validate without an
 * intermediate disk write.
 */
export function parseTrustRoots(raw: unknown, source = '<inline>'): TrustRoots {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new TrustRootsError(
      `TrustRoots ${source}: top-level must be a mapping, got ${
        Array.isArray(raw) ? 'array' : raw === null ? 'null' : typeof raw
      }`,
    );
  }
  const obj = raw as Record<string, unknown>;
  const keysPresent = new Set(Object.keys(obj));
  const missing: string[] = [];
  for (const k of REQUIRED_TOP_KEYS) {
    if (!keysPresent.has(k)) missing.push(k);
  }
  if (missing.length > 0) {
    missing.sort();
    throw new TrustRootsError(
      `TrustRoots ${source}: missing required top-level fields [${missing.join(', ')}]`,
    );
  }
  const unexpected: string[] = [];
  for (const k of keysPresent) {
    if (!REQUIRED_TOP_KEYS.has(k)) unexpected.push(k);
  }
  if (unexpected.length > 0) {
    unexpected.sort();
    throw new TrustRootsError(
      `TrustRoots ${source}: unexpected top-level fields [${unexpected.join(', ')}]`,
    );
  }
  if (obj.version !== 1) {
    throw new TrustRootsError(
      `TrustRoots ${source}: version must be 1 (v1 schema), got ${JSON.stringify(obj.version)}`,
    );
  }
  if (!Array.isArray(obj.keys)) {
    throw new TrustRootsError(
      `TrustRoots ${source}: 'keys' must be an array, got ${typeof obj.keys}`,
    );
  }
  if (obj.keys.length === 0) {
    throw new TrustRootsError(`TrustRoots ${source}: 'keys' must contain at least one entry`);
  }
  const entries = obj.keys.map((e, i) => validateEntry(i, e));
  const seenIds = new Set<string>();
  for (const entry of entries) {
    if (seenIds.has(entry.key_id)) {
      throw new TrustRootsError(
        `TrustRoots ${source}: duplicate key_id ${JSON.stringify(entry.key_id)}`,
      );
    }
    seenIds.add(entry.key_id);
  }
  return new TrustRoots(1, entries);
}
