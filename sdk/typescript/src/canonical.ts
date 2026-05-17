// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Restricted-JCS canonicalization for audit-event hashing (TypeScript SDK).
 *
 * Implements the same restricted JSON profile as `sdk/python/src/attestplane/
 * canonical.py`. Both SDKs MUST produce byte-identical output for the same
 * input; correctness is validated continuously by the cross-language
 * conformance test that replays `sdk/python/tests/conformance/vectors.json`.
 *
 * Restricted profile (per ADR-0002):
 * - Strings are UTF-8 and must be NFC-normalized.
 * - Integers (number or bigint) are limited to the signed 64-bit range.
 * - Floats / NaN / Infinity are forbidden.
 * - Object keys are strings, emitted in code-point order, no duplicates.
 * - Datetimes are RFC 3339 UTC microsecond strings with a `Z` suffix.
 * - Uint8Array is encoded as base64url without padding.
 */

const ASCII_CONTROL_LIMIT = 0x20;
const INT64_MIN_BIGINT = -(2n ** 63n);
const INT64_MAX_BIGINT = 2n ** 63n - 1n;

const ESCAPES = new Map<number, string>([
  [0x08, '\\b'],
  [0x09, '\\t'],
  [0x0a, '\\n'],
  [0x0c, '\\f'],
  [0x0d, '\\r'],
  [0x22, '\\"'],
  [0x5c, '\\\\'],
]);

export class CanonicalizationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CanonicalizationError';
  }
}

export function canonicalize(value: unknown): Uint8Array {
  const out: string[] = [];
  emit(value, out, '$');
  return new TextEncoder().encode(out.join(''));
}

function emit(value: unknown, out: string[], path: string): void {
  if (value === null || value === undefined) {
    out.push('null');
    return;
  }
  if (typeof value === 'boolean') {
    out.push(value ? 'true' : 'false');
    return;
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new CanonicalizationError(
        `${path}: non-finite numbers (NaN/Infinity) are forbidden in canonical payloads`,
      );
    }
    if (!Number.isInteger(value)) {
      throw new CanonicalizationError(
        `${path}: float values are forbidden in canonical payloads (use integers, base64-encoded bytes, or string representations)`,
      );
    }
    // JS Number safely represents integers up to 2^53 - 1. Anything outside
    // the signed 64-bit range would be expressed as bigint by the caller.
    out.push(value.toString());
    return;
  }
  if (typeof value === 'bigint') {
    if (value < INT64_MIN_BIGINT || value > INT64_MAX_BIGINT) {
      throw new CanonicalizationError(`${path}: integer ${value} outside signed 64-bit range`);
    }
    out.push(value.toString());
    return;
  }
  if (typeof value === 'string') {
    emitString(value, out, path);
    return;
  }
  if (value instanceof Uint8Array) {
    emitString(toBase64UrlNoPad(value), out, path);
    return;
  }
  if (value instanceof Date) {
    emitDate(value, out, path);
    return;
  }
  if (Array.isArray(value)) {
    emitArray(value, out, path);
    return;
  }
  if (typeof value === 'object') {
    emitObject(value as Record<string, unknown>, out, path);
    return;
  }
  throw new CanonicalizationError(`${path}: unsupported type ${typeof value} in canonical payload`);
}

function emitString(value: string, out: string[], path: string): void {
  if (value.normalize('NFC') !== value) {
    throw new CanonicalizationError(
      `${path}: string is not Unicode-NFC normalized; normalize before passing to the substrate`,
    );
  }
  out.push('"');
  for (const ch of value) {
    const code = ch.codePointAt(0);
    if (code === undefined) continue;
    const mapped = ESCAPES.get(code);
    if (mapped !== undefined) {
      out.push(mapped);
    } else if (code < ASCII_CONTROL_LIMIT) {
      out.push(`\\u${code.toString(16).padStart(4, '0')}`);
    } else {
      out.push(ch);
    }
  }
  out.push('"');
}

function emitDate(value: Date, out: string[], path: string): void {
  const ms = value.getTime();
  if (Number.isNaN(ms)) {
    throw new CanonicalizationError(`${path}: invalid Date (NaN time value)`);
  }
  // JS Date is always interpreted as UTC milliseconds since epoch, so timezone
  // mismatch is not possible at the API boundary. We zero-pad milliseconds out
  // to six digits to match Python's microsecond formatting; values supplied at
  // sub-millisecond precision must be encoded as strings until a typed
  // Timestamp type is introduced.
  const yyyy = value.getUTCFullYear().toString().padStart(4, '0');
  const mm = (value.getUTCMonth() + 1).toString().padStart(2, '0');
  const dd = value.getUTCDate().toString().padStart(2, '0');
  const hh = value.getUTCHours().toString().padStart(2, '0');
  const mi = value.getUTCMinutes().toString().padStart(2, '0');
  const ss = value.getUTCSeconds().toString().padStart(2, '0');
  const milli = value.getUTCMilliseconds().toString().padStart(3, '0');
  const iso = `${yyyy}-${mm}-${dd}T${hh}:${mi}:${ss}.${milli}000Z`;
  emitString(iso, out, path);
}

function emitObject(value: Record<string, unknown>, out: string[], path: string): void {
  out.push('{');
  const keys = Object.keys(value).sort();
  const seen = new Set<string>();
  for (let i = 0; i < keys.length; i++) {
    const key = keys[i] as string;
    if (seen.has(key)) {
      throw new CanonicalizationError(`${path}: duplicate object key ${JSON.stringify(key)}`);
    }
    seen.add(key);
    if (i > 0) out.push(',');
    emitString(key, out, `${path}.${key}`);
    out.push(':');
    emit(value[key], out, `${path}.${key}`);
  }
  out.push('}');
}

function emitArray(value: unknown[], out: string[], path: string): void {
  out.push('[');
  for (let i = 0; i < value.length; i++) {
    if (i > 0) out.push(',');
    emit(value[i], out, `${path}[${i}]`);
  }
  out.push(']');
}

function toBase64UrlNoPad(bytes: Uint8Array): string {
  const b64 = Buffer.from(bytes).toString('base64');
  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
