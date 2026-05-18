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
 * - Integers are JSON numbers in the JS safe-integer range and limited to the
 *   signed 64-bit range; bigint is rejected because JSON has no bigint type.
 * - Floats / NaN / Infinity are forbidden.
 * - Object keys are strings, emitted in code-point order, no duplicates.
 * - Datetimes are explicit RFC 3339 UTC microsecond strings with a `Z` suffix;
 *   Date objects are rejected to avoid implicit millisecond truncation.
 * - Uint8Array is encoded as base64url without padding.
 */

const ASCII_CONTROL_LIMIT = 0x20;
const INT64_MIN_BIGINT = -(2n ** 63n);
const INT64_MAX_BIGINT = 2n ** 63n - 1n;
const HIGH_SURROGATE_MIN = 0xd800;
const LOW_SURROGATE_MAX = 0xdfff;
const INT64_LITERAL = Symbol('attestplane.int64_literal');

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

export interface Int64LiteralForConformance {
  readonly [INT64_LITERAL]: true;
  readonly source: string;
}

export function int64LiteralForConformance(source: string): Int64LiteralForConformance {
  if (!/^-?\d+$/.test(source)) {
    throw new CanonicalizationError(`int64 literal source must be base-10 integer, got ${source}`);
  }
  const asBigint = BigInt(source);
  if (asBigint < INT64_MIN_BIGINT || asBigint > INT64_MAX_BIGINT) {
    throw new CanonicalizationError(`int64 literal ${source} outside signed 64-bit range`);
  }
  return { [INT64_LITERAL]: true, source };
}

function emit(value: unknown, out: string[], path: string): void {
  if (value === undefined) {
    throw new CanonicalizationError(
      `${path}: undefined is forbidden in canonical payloads; use null explicitly`,
    );
  }
  if (value === null) {
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
    if (!Number.isSafeInteger(value)) {
      throw new CanonicalizationError(
        `${path}: unsafe integer ${value} outside JavaScript safe-integer range`,
      );
    }
    const asBigint = BigInt(value);
    if (asBigint < INT64_MIN_BIGINT || asBigint > INT64_MAX_BIGINT) {
      throw new CanonicalizationError(`${path}: integer ${value} outside signed 64-bit range`);
    }
    out.push(value.toString());
    return;
  }
  if (typeof value === 'bigint') {
    throw new CanonicalizationError(`${path}: bigint is forbidden in canonical JSON payloads`);
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
    throw new CanonicalizationError(
      `${path}: Date objects are forbidden; pass an explicit RFC 3339 UTC timestamp string`,
    );
  }
  if (isInt64LiteralForConformance(value)) {
    out.push(value.source);
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

function isInt64LiteralForConformance(value: unknown): value is Int64LiteralForConformance {
  return (
    value !== null &&
    typeof value === 'object' &&
    (value as Partial<Int64LiteralForConformance>)[INT64_LITERAL] === true
  );
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
    if (code >= HIGH_SURROGATE_MIN && code <= LOW_SURROGATE_MAX) {
      throw new CanonicalizationError(`${path}: string contains lone surrogate code point`);
    }
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
    if (!Object.prototype.hasOwnProperty.call(value, i)) {
      throw new CanonicalizationError(`${path}[${i}]: sparse array holes are forbidden`);
    }
    if (i > 0) out.push(',');
    emit(value[i], out, `${path}[${i}]`);
  }
  out.push(']');
}

function toBase64UrlNoPad(bytes: Uint8Array): string {
  const b64 = Buffer.from(bytes).toString('base64');
  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
