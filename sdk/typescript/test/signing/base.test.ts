// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';

import {
  DEFAULT_SIGNATURE_POLICY,
  KeyBoundaryError,
  KeyProvider,
  SIGNATURE_SCHEMA_VERSION,
  type SignatureRecord,
  SigningError,
  type SigningMaterial,
  deriveKeyId,
  makeSignaturePolicy,
  validateSignatureRecord,
} from '../../src/signing/base.js';

const FAKE_PUB_DER = new Uint8Array([
  0x30,
  0x2a,
  0x30,
  0x05,
  0x06,
  0x03,
  0x2b,
  0x65,
  0x70,
  0x03,
  0x21,
  0x00,
  ...new Array(32).fill(0xaa),
]);

const FAKE_KEY_ID = deriveKeyId(FAKE_PUB_DER);

function makeRecord(overrides: Partial<SignatureRecord> = {}): SignatureRecord {
  return {
    signature_schema_version: SIGNATURE_SCHEMA_VERSION,
    signed_seq: 0,
    signed_event_hash: new Uint8Array(32).fill(1),
    signature: new Uint8Array(64).fill(2),
    key_id: FAKE_KEY_ID,
    public_key_der: FAKE_PUB_DER,
    signing_cert_chain: [],
    signed_at: new Date('2026-05-17T12:00:00Z'),
    signature_mode: 'segment_head',
    signed_payload: new Uint8Array([0x7b, 0x7d]),
    ...overrides,
  };
}

describe('deriveKeyId', () => {
  it('returns 32 hex chars', () => {
    expect(FAKE_KEY_ID).toMatch(/^[0-9a-f]{32}$/);
  });

  it('rejects empty input', () => {
    expect(() => deriveKeyId(new Uint8Array(0))).toThrow(SigningError);
  });

  it('is deterministic', () => {
    expect(deriveKeyId(FAKE_PUB_DER)).toBe(FAKE_KEY_ID);
  });
});

describe('validateSignatureRecord', () => {
  it('accepts a well-formed record', () => {
    expect(() => validateSignatureRecord(makeRecord())).not.toThrow();
  });

  it('rejects wrong schema version', () => {
    expect(() => validateSignatureRecord(makeRecord({ signature_schema_version: 99 }))).toThrow(
      /signature_schema_version/,
    );
  });

  it('rejects negative seq', () => {
    expect(() => validateSignatureRecord(makeRecord({ signed_seq: -1 }))).toThrow(/signed_seq/);
  });

  it('rejects wrong-length event hash', () => {
    expect(() =>
      validateSignatureRecord(makeRecord({ signed_event_hash: new Uint8Array(31) })),
    ).toThrow(/signed_event_hash/);
  });

  it('rejects wrong-length signature', () => {
    expect(() => validateSignatureRecord(makeRecord({ signature: new Uint8Array(32) }))).toThrow(
      /64 bytes/,
    );
  });

  it('rejects empty key_id', () => {
    expect(() => validateSignatureRecord(makeRecord({ key_id: '' }))).toThrow(/key_id/);
  });

  it('rejects empty public_key_der', () => {
    expect(() =>
      validateSignatureRecord(makeRecord({ public_key_der: new Uint8Array(0) })),
    ).toThrow(/public_key_der/);
  });

  it('rejects empty signed_payload', () => {
    expect(() =>
      validateSignatureRecord(makeRecord({ signed_payload: new Uint8Array(0) })),
    ).toThrow(/signed_payload/);
  });

  it('rejects unknown signature_mode', () => {
    expect(() =>
      validateSignatureRecord(makeRecord({ signature_mode: 'bogus' as 'segment_head' })),
    ).toThrow(/signature_mode/);
  });

  it('rejects key_id that does not derive from public_key_der', () => {
    expect(() => validateSignatureRecord(makeRecord({ key_id: '0'.repeat(32) }))).toThrow(/derive/);
  });
});

describe('makeSignaturePolicy', () => {
  it('returns defaults when called with no input', () => {
    expect(makeSignaturePolicy()).toEqual(DEFAULT_SIGNATURE_POLICY);
  });

  it('merges partial overrides', () => {
    const p = makeSignaturePolicy({ batch_size: 7, per_event: true });
    expect(p.batch_size).toBe(7);
    expect(p.per_event).toBe(true);
    expect(p.max_idle_seconds).toBe(DEFAULT_SIGNATURE_POLICY.max_idle_seconds);
  });

  it('rejects non-positive batch_size', () => {
    expect(() => makeSignaturePolicy({ batch_size: 0 })).toThrow(SigningError);
  });

  it('rejects non-positive max_idle_seconds', () => {
    expect(() => makeSignaturePolicy({ max_idle_seconds: 0 })).toThrow(SigningError);
  });
});

describe('KeyProvider forbidden-verb gate', () => {
  it('rejects subclass that declares revoke', () => {
    class BadProvider extends KeyProvider {
      readonly provider_id = 'bad';
      readonly schema_version = SIGNATURE_SCHEMA_VERSION;
      getSigningMaterial(): SigningMaterial {
        throw new Error('unused');
      }
      revoke(): void {
        /* forbidden */
      }
    }
    expect(() => new BadProvider()).toThrow(KeyBoundaryError);
  });

  for (const verb of ['rotate', 'delete', 'replace'] as const) {
    it(`rejects subclass that declares ${verb}`, () => {
      const cls = class extends KeyProvider {
        readonly provider_id = `bad:${verb}`;
        readonly schema_version = SIGNATURE_SCHEMA_VERSION;
        getSigningMaterial(): SigningMaterial {
          throw new Error('unused');
        }
      };
      // Inject the forbidden verb via prototype.
      (cls.prototype as Record<string, unknown>)[verb] = () => {
        /* forbidden */
      };
      expect(() => new cls()).toThrow(KeyBoundaryError);
    });
  }

  it('private/underscored methods do not trip the gate', () => {
    class OkProvider extends KeyProvider {
      readonly provider_id = 'ok';
      readonly schema_version = SIGNATURE_SCHEMA_VERSION;
      getSigningMaterial(): SigningMaterial {
        throw new Error('unused');
      }
      _delete(): void {
        /* underscored is fine */
      }
    }
    expect(() => new OkProvider()).not.toThrow();
  });
});
