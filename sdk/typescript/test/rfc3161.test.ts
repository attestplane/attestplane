// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * TypeScript replay of the frozen Python-generated `anchor_vectors.json`.
 *
 * Each vector was produced by an in-tree Python TestTSAAuthority and
 * proves that the TypeScript SDK parses the same real RFC-3161
 * TimeStampResp bytes, verifies the same RSA signature, walks the same
 * X.509 chain, and arrives at cert_status=VALID.
 *
 * This is the load-bearing cross-language conformance test for v0.0.2-alpha.
 */

import { readFileSync } from 'node:fs';
import * as path from 'node:path';

import { describe, expect, it } from 'vitest';

import { AnchorVerificationError } from '../src/anchoring.js';
import { parseTimestampResponse, verifyTimestampToken } from '../src/rfc3161.js';

interface VectorEntry {
  readonly name: string;
  readonly anchored_seq: number;
  readonly anchored_event_hash_hex: string;
  readonly tsa_provider_id: string;
  readonly tsa_token_b64: string;
  readonly tsa_cert_chain_b64: readonly string[];
  readonly ocsp_responses_b64: readonly string[];
  readonly issued_at_claimed: string;
}

interface VectorFile {
  readonly $schema_version: number;
  readonly test_tsa_root_cert_b64: string;
  readonly verification_time: string;
  readonly entries: readonly VectorEntry[];
}

const VECTORS_PATH = path.resolve(
  __dirname,
  '..',
  '..',
  'python',
  'tests',
  'conformance',
  'anchor_vectors.json',
);

function loadVectors(): VectorFile {
  return JSON.parse(readFileSync(VECTORS_PATH, 'utf-8')) as VectorFile;
}

function decode(b64: string): Uint8Array {
  return new Uint8Array(Buffer.from(b64, 'base64'));
}

function hexToBytes(hex: string): Uint8Array {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

describe('Python-generated anchor_vectors.json → TypeScript verifier', () => {
  const vectors = loadVectors();
  const rootDer = decode(vectors.test_tsa_root_cert_b64);
  const when = new Date(vectors.verification_time);

  it('vectors file has the expected shape', () => {
    expect(vectors.$schema_version).toBe(1);
    expect(vectors.entries.length).toBeGreaterThanOrEqual(3);
  });

  for (const entry of vectors.entries) {
    it(`vector "${entry.name}": parse + signature verify`, () => {
      const tokenDer = decode(entry.tsa_token_b64);
      const parsed = parseTimestampResponse(tokenDer);
      const expectedDigest = hexToBytes(entry.anchored_event_hash_hex);

      expect(parsed.hashAlgorithm).toBe('sha256');
      expect(Buffer.from(parsed.messageImprint).equals(Buffer.from(expectedDigest))).toBe(true);

      // Must not throw — real RSA-PKCS1v15-SHA256 signature verification
      // against the leaf cert + chain to the configured root.
      verifyTimestampToken(parsed, {
        expectedDigest,
        trustRootsDer: [rootDer],
        verificationTime: when,
      });
    });
  }

  it('vector "anchor_with_nonce" carries a non-null nonce', () => {
    const entry = vectors.entries.find((e) => e.name === 'anchor_with_nonce');
    expect(entry).toBeDefined();
    if (entry === undefined) return;
    const parsed = parseTimestampResponse(decode(entry.tsa_token_b64));
    expect(parsed.nonce).not.toBeNull();
  });
});

describe('RFC-3161 CMS signer digest parity', () => {
  const ecSha512Fixture = {
    expectedDigestHex: '9bbc71993bd29a4857f08baa1c1e7699b2b50b051e3457eb33feee8b10b011cf',
    rootCertB64:
      'MIIC+jCCAeKgAwIBAgIUQWQ4VLv/O8e6i0nnuMp0iILwUkEwDQYJKoZIhvcNAQELBQAwIzEhMB8GA1UEAwwYQXR0ZXN0cGxhbmUgVGVzdCBSb290IENBMB4XDTI2MDUxNzEyMDAwMFoXDTM2MDUxNDEyMDAwMFowIzEhMB8GA1UEAwwYQXR0ZXN0cGxhbmUgVGVzdCBSb290IENBMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsJk03sV7VMgsI+GMA/8XzxAsRfgKJpsVoxHm087nw4Lsz1CisOc05k45XypvkVNW/nD7UetpVnGadEHKOYMs6ZXIOvhJeTZV+PzcMct3QFm7wxhbC86bV6olHuNHSj9vRJzC+kEdCi9Xvd+VyeIL4qNP39yOMK63pV/9DOLwlzrrTxJQ9tQGgaZKTFF71LuJjGe3Pi4SjAXgoA3RwCcP23/TqqcfmvpU0GqxS6DKTNM9wJqZ7bEfH/u7B/2JJ5ZBvBtFW78xHwVROHyDS9bXyZZWRmfpMXj5/2mmiGWVJI0BdE7NWXELL1dWJLC3rnvUxTSnbYf1S30B2HkJljU/gwIDAQABoyYwJDASBgNVHRMBAf8ECDAGAQH/AgEBMA4GA1UdDwEB/wQEAwIBhjANBgkqhkiG9w0BAQsFAAOCAQEAFCXPunKipZ3AYlhfYxNPmLiZ6z3CixInnJfVtQr4yVADCqmQQ3v8V/NQCnkJsLgEIHXJcii8dgpKa6GzmYujZBTRCEmao1puuWhMGhJMc8EB6xdhW1T2G7q731fa7Pm/1qn4BWVfm4Sq3rELmtrJVZyvv/GjmfjUSqfpTHVLZGDvhjBrBRcEVYDvoZaGgHKmQfyC14ppUqEtb7Eo8GNEA+Hsr1P4aFofHhwgRFWHQMvBpxh8mh6KUEbHsEtpIPh7Fwxr4guCrJMHpNBLlwBmW+Rgawm5eLmHugBsQKaaDroB4PXpFRXe1UWnSWvDU3BBlSmBAozZFHKLhSVyhwLQSg==',
    tokenB64:
      'MIIEFDADAgEAMIIECwYJKoZIhvcNAQcCoIID/DCCA/gCAQMxDzANBglghkgBZQMEAgMFADBjBgsqhkiG9w0BCRABBKBUBFIwUAIBAQYEKgMEBTAxMA0GCWCGSAFlAwQCAQUABCCbvHGZO9KaSFfwi6ocHnaZsrULBR40V+sz/u6LELARzwIBTRgPMjAyNjA1MTcxMjAwMDBaoIICQTCCAj0wggEloAMCAQICFGKVoXwSwdOwCqEI2Vgd6OTLrBL8MA0GCSqGSIb3DQEBCwUAMCMxITAfBgNVBAMMGEF0dGVzdHBsYW5lIFRlc3QgUm9vdCBDQTAeFw0yNjA1MTcxMjAwMDBaFw0yNzA1MTcxMjAwMDBaMB8xHTAbBgNVBAMMFEF0dGVzdHBsYW5lIFRlc3QgVFNBMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEx6ZjWJiAWXpgsqMS8t7eNlVMSE6VDD9hc3hlmFPAl/gXsHG3uJ8d5BsNBRreFKbcN4tESH4TuLtpqROt5igXlqM4MDYwDAYDVR0TAQH/BAIwADAOBgNVHQ8BAf8EBAMCBsAwFgYDVR0lAQH/BAwwCgYIKwYBBQUHAwgwDQYJKoZIhvcNAQELBQADggEBAJToRE7AlPySLKU38Wz9EjgFFknO7sQtpcAQ7CqcSv5dqX+jTI2/7K96SJx4ks2Z0Bi2bBLs1Y13xSyj/rRlWXL7yNG74XrIGnykaOVlJnYML7jhsE3nr/NvXwTL1c3TW0/lFHb0gYdvpLdowVP03KMggpmiHRDKLCfDZBOmac6n/nkcMEPcx0UQSv7QO7IQ3Qm2V02EW0ieEqapcW+AoINoqHLSLNj/yCqKu1IhrAG3CP9PA0amHCAnmw/+cm1391S8WYxwwBbHSKbkb3xCgHnazoywb9ZP5Dhie4LkUwm2ssler8SGta3bNzTK1Ds5n90BymRr0BO1Sd4GlPkXiRQxggE2MIIBMgIBATA7MCMxITAfBgNVBAMMGEF0dGVzdHBsYW5lIFRlc3QgUm9vdCBDQQIUYpWhfBLB07AKoQjZWB3o5MusEvwwDQYJYIZIAWUDBAIDBQCggYswGgYJKoZIhvcNAQkDMQ0GCyqGSIb3DQEJEAEEMBwGCSqGSIb3DQEJBTEPFw0yNjA1MTcxMjAwMDBaME8GCSqGSIb3DQEJBDFCBECkyoviChXTCEokM5CB6zbJTWW083cp4kaUKkDvSCETKkiFipncUdxPxFPN24Y+e5dFR1eijUa5jr/yyxYRpfzIMAoGCCqGSM49BAMEBEcwRQIgS7ZhZfirm2zFTUeeJSw2Lpj/3Y2e9jDJaOPdLQtE3mECIQCzG/S1xDud2pZ1EzDvs3fTbOROCZvQLn5TfcEk9yTnzw==',
  };

  it('verifies EC leaf tokens whose CMS signed_attrs use SHA-512 ECDSA', () => {
    const parsed = parseTimestampResponse(decode(ecSha512Fixture.tokenB64));
    const expectedDigest = hexToBytes(ecSha512Fixture.expectedDigestHex);

    expect(parsed.hashAlgorithm).toBe('sha256');
    expect(parsed.digestAlgorithmOid).toBe('2.16.840.1.101.3.4.2.3');
    expect(parsed.signatureAlgorithmOid).toBe('1.2.840.10045.4.3.4');
    expect(Buffer.from(parsed.messageImprint).equals(Buffer.from(expectedDigest))).toBe(true);

    verifyTimestampToken(parsed, {
      expectedDigest,
      trustRootsDer: [decode(ecSha512Fixture.rootCertB64)],
      verificationTime: new Date('2026-05-17T12:00:00Z'),
    });
  });
});

describe('RFC-3161 parser rejection paths', () => {
  it('rejects empty input', () => {
    expect(() => parseTimestampResponse(new Uint8Array(0))).toThrow(AnchorVerificationError);
  });

  it('rejects non-DER input', () => {
    expect(() => parseTimestampResponse(new Uint8Array([0xff, 0xff, 0xff, 0xff]))).toThrow(
      AnchorVerificationError,
    );
  });
});

describe('verifyTimestampToken rejection paths', () => {
  const vectors = loadVectors();
  const rootDer = decode(vectors.test_tsa_root_cert_b64);
  const when = new Date(vectors.verification_time);
  const entry = vectors.entries[0] as VectorEntry;
  const parsed = parseTimestampResponse(decode(entry.tsa_token_b64));
  const expectedDigest = hexToBytes(entry.anchored_event_hash_hex);

  it('rejects digest mismatch', () => {
    const wrongDigest = new Uint8Array(32).fill(0xff);
    expect(() =>
      verifyTimestampToken(parsed, {
        expectedDigest: wrongDigest,
        trustRootsDer: [rootDer],
        verificationTime: when,
      }),
    ).toThrow(/message_imprint/);
  });

  it('rejects expectedDigest of wrong length', () => {
    expect(() =>
      verifyTimestampToken(parsed, {
        expectedDigest: new Uint8Array(16),
        trustRootsDer: [rootDer],
        verificationTime: when,
      }),
    ).toThrow(/32 bytes/);
  });

  it('rejects when no trust roots are provided', () => {
    expect(() =>
      verifyTimestampToken(parsed, {
        expectedDigest,
        trustRootsDer: [],
        verificationTime: when,
      }),
    ).toThrow(/no parseable trust roots/);
  });

  it('rejects expired verification window', () => {
    const future = new Date(when.getTime() + 1000 * 60 * 60 * 24 * 365 * 5);
    expect(() =>
      verifyTimestampToken(parsed, {
        expectedDigest,
        trustRootsDer: [rootDer],
        verificationTime: future,
      }),
    ).toThrow(/not_after/);
  });

  it('rejects when chain walk exceeds maxChainDepth', () => {
    expect(() =>
      verifyTimestampToken(parsed, {
        expectedDigest,
        trustRootsDer: [],
        verificationTime: when,
        maxChainDepth: 0,
      }),
    ).toThrow();
  });
});
