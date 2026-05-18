// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';

import { CanonicalizationError, canonicalize } from '../src/canonical.js';
import { makeSubjectRef } from '../src/types.js';

const decode = (bytes: Uint8Array): string => new TextDecoder().decode(bytes);

describe('canonicalize / primitives', () => {
  it('null, booleans, integers', () => {
    expect(decode(canonicalize(null))).toBe('null');
    expect(decode(canonicalize(true))).toBe('true');
    expect(decode(canonicalize(false))).toBe('false');
    expect(decode(canonicalize(0))).toBe('0');
    expect(decode(canonicalize(42))).toBe('42');
    expect(decode(canonicalize(-1))).toBe('-1');
  });

  it('rejects floats', () => {
    expect(() => canonicalize(1.5)).toThrow(CanonicalizationError);
    expect(() => canonicalize(Number.NaN)).toThrow(CanonicalizationError);
    expect(() => canonicalize(Number.POSITIVE_INFINITY)).toThrow(CanonicalizationError);
    expect(() => canonicalize(Number.NEGATIVE_INFINITY)).toThrow(CanonicalizationError);
  });

  it('rejects unsafe integers', () => {
    expect(() => canonicalize(Number.MAX_SAFE_INTEGER + 1)).toThrow(CanonicalizationError);
    expect(() => canonicalize(Number.MIN_SAFE_INTEGER - 1)).toThrow(CanonicalizationError);
  });

  it('locks negative zero as canonical zero', () => {
    expect(Object.is(-0, 0)).toBe(false);
    expect(decode(canonicalize(-0))).toBe('0');
  });

  it('rejects bigint because JSON has no cross-language bigint type', () => {
    expect(() => canonicalize(1n)).toThrow(CanonicalizationError);
  });
});

describe('canonicalize / strings', () => {
  it('basic ASCII string', () => {
    expect(decode(canonicalize('hello'))).toBe('"hello"');
  });

  it('escapes special characters', () => {
    expect(decode(canonicalize('quote: "'))).toBe('"quote: \\""');
    expect(decode(canonicalize('back\\slash'))).toBe('"back\\\\slash"');
    expect(decode(canonicalize('tab\tin'))).toBe('"tab\\tin"');
    expect(decode(canonicalize('line\nbreak'))).toBe('"line\\nbreak"');
    expect(decode(canonicalize('\x01'))).toBe('"\\u0001"');
  });

  it('requires NFC normalization', () => {
    const nfc = 'é'; // é
    const nfd = 'é'; // e + combining acute
    expect(canonicalize(nfc)).toEqual(new TextEncoder().encode('"é"'));
    expect(() => canonicalize(nfd)).toThrow(CanonicalizationError);
  });

  it('rejects lone surrogate code points before UTF-8 encoding', () => {
    expect(() => canonicalize('\ud800')).toThrow(CanonicalizationError);
    expect(() => canonicalize('\udc00')).toThrow(CanonicalizationError);
  });

  it('does not normalize ordinary strings implicitly', () => {
    expect(decode(canonicalize('①'))).toBe('"①"');
    expect(() => canonicalize('A\u030a')).toThrow(CanonicalizationError);
  });
});

describe('canonicalize / dates', () => {
  it('rejects Date objects; timestamps must be explicit canonical strings', () => {
    expect(() => canonicalize(new Date('2026-05-17T12:00:00.000Z'))).toThrow(CanonicalizationError);
    expect(decode(canonicalize('2026-05-17T12:00:00.000000Z'))).toBe(
      '"2026-05-17T12:00:00.000000Z"',
    );
  });
});

describe('canonicalize / Uint8Array', () => {
  it('encodes as base64url without padding', () => {
    expect(decode(canonicalize(new Uint8Array([0, 1, 2])))).toBe('"AAEC"');
    expect(decode(canonicalize(new Uint8Array([97, 98, 99])))).toBe('"YWJj"');
    expect(decode(canonicalize(new Uint8Array(0)))).toBe('""');
  });
});

describe('canonicalize / objects', () => {
  it('emits keys in code-point sorted order', () => {
    expect(decode(canonicalize({ b: 1, a: 2 }))).toBe('{"a":2,"b":1}');
    expect(decode(canonicalize({ z: true, a: null, m: 'x' }))).toBe('{"a":null,"m":"x","z":true}');
  });

  it('is invariant under insertion order', () => {
    const a = canonicalize({ x: 1, y: 2, z: 3 });
    const b = canonicalize({ z: 3, y: 2, x: 1 });
    expect(a).toEqual(b);
  });

  it('handles nested objects', () => {
    const obj = { outer: { b: [1, 2, 3], a: 'x' } };
    expect(decode(canonicalize(obj))).toBe('{"outer":{"a":"x","b":[1,2,3]}}');
  });

  it('rejects undefined object property values instead of omitting them', () => {
    expect(() => canonicalize({ a: undefined })).toThrow(CanonicalizationError);
  });

  it('uses deterministic nested code-point key ordering', () => {
    const obj = { z: { '10': 1, '2': 2, A: 3, a: 4 }, a: 5 };
    expect(decode(canonicalize(obj))).toBe('{"a":5,"z":{"10":1,"2":2,"A":3,"a":4}}');
  });
});

describe('canonicalize / arrays', () => {
  it('preserves insertion order', () => {
    expect(decode(canonicalize([3, 1, 2]))).toBe('[3,1,2]');
    expect(decode(canonicalize([]))).toBe('[]');
  });

  it('rejects undefined array items and sparse array holes', () => {
    expect(() => canonicalize([1, undefined, 3])).toThrow(CanonicalizationError);
    const sparse = new Array<number>(3);
    sparse[0] = 1;
    sparse[2] = 3;
    expect(() => canonicalize(sparse)).toThrow(CanonicalizationError);
  });
});

describe('canonicalize / SubjectRef', () => {
  it('serializes as a plain object', () => {
    const ref = makeSubjectRef('opaque', 'abc');
    expect(decode(canonicalize(ref))).toBe('{"scheme":"opaque","value":"abc"}');
  });
});

describe('canonicalize / unsupported types', () => {
  it('rejects unsupported types', () => {
    expect(() => canonicalize(undefined)).toThrow(CanonicalizationError);
    expect(() => canonicalize(Symbol('x'))).toThrow(CanonicalizationError);
    expect(() => canonicalize(() => 0)).toThrow(CanonicalizationError);
  });
});
