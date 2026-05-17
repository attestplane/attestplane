// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * RFC-3161 TimeStampResp parsing + TimeStampToken signature verification
 * (TypeScript port of `sdk/python/src/attestplane/anchoring/rfc3161.py`).
 *
 * Built on `src/der.ts` (hand-rolled DER reader) + Node's stdlib
 * `crypto.verify` for RSA-PKCS1v15-SHA256. No additional npm
 * dependencies — the TypeScript SDK keeps the same lean dep tree as
 * v0.0.1-alpha while gaining real signature verification.
 *
 * The parser handles the specific structures defined in RFC-3161,
 * RFC-5652 (CMS SignedData), and the X.509 subset needed to extract
 * the RSA public key from a leaf cert's SubjectPublicKeyInfo.
 *
 * Cross-language conformance: TS reproduces Python's
 * parse_timestamp_response semantics byte-for-byte. The
 * anchor_vectors.json fixtures verify in both languages.
 */

import { type KeyObject, createPublicKey, createVerify } from 'node:crypto';

import { AnchorVerificationError } from './anchoring.js';
import {
  DerParseError,
  type DerTlv,
  getValueBytes,
  readBitString,
  readGeneralizedTime,
  readInteger,
  readOctetString,
  readOid,
  readSequence,
  readTlv,
  tlvDer,
} from './der.js';

// Well-known OIDs used in the structures we parse.
const OID_SIGNED_DATA = '1.2.840.113549.1.7.2';
const OID_TST_INFO = '1.2.840.113549.1.9.16.1.4';

/** Subset of TSTInfo + SignerInfo extracted from a TimeStampResp. */
export interface ParsedTimestampTs {
  readonly policyOid: string;
  readonly hashAlgorithm: string;
  readonly messageImprint: Uint8Array;
  readonly genTime: Date;
  readonly serialNumber: bigint;
  readonly nonce: bigint | null;
  readonly leafCertDer: Uint8Array;
  readonly signedAttrsDer: Uint8Array;
  readonly signature: Uint8Array;
  readonly digestAlgorithmOid: string;
  readonly signatureAlgorithmOid: string;
}

function topSequence(buffer: Uint8Array): DerTlv {
  const tlv = readTlv(buffer, 0);
  if (tlv.tag !== 0x30) {
    throw new AnchorVerificationError(
      `expected SEQUENCE (0x30) at top, got 0x${tlv.tag.toString(16)}`,
    );
  }
  return tlv;
}

function tryWrapAsSet(buffer: Uint8Array): Uint8Array {
  // Some CMS SignerInfo signedAttrs are encoded with IMPLICIT [0]
  // (tag 0xA0) but the signature input is computed over the SET-tagged
  // form (0x31). Rewrite the first byte to 0x31 to match.
  if (buffer.length === 0) return buffer;
  const out = new Uint8Array(buffer);
  if (out[0] === 0xa0 || out[0] === 0xa1) {
    out[0] = 0x31;
  }
  return out;
}

/** Parse a DER-encoded TimeStampResp into the substantive fields we verify. */
export function parseTimestampResponse(responseDer: Uint8Array): ParsedTimestampTs {
  let response: DerTlv;
  try {
    response = topSequence(responseDer);
  } catch (exc) {
    if (exc instanceof DerParseError) {
      throw new AnchorVerificationError(`timestamp response is not valid DER: ${exc.message}`);
    }
    throw exc;
  }
  const responseFields = readSequence(response);
  if (responseFields.length < 1) {
    throw new AnchorVerificationError('timestamp response: missing PKIStatusInfo');
  }

  // PKIStatusInfo ::= SEQUENCE { status INTEGER, statusString OPTIONAL, failInfo OPTIONAL }
  const statusInfo = responseFields[0] as DerTlv;
  if (statusInfo.tag !== 0x30) {
    throw new AnchorVerificationError('PKIStatusInfo is not a SEQUENCE');
  }
  const statusItems = readSequence(statusInfo);
  if (statusItems.length === 0) {
    throw new AnchorVerificationError('PKIStatusInfo: missing status');
  }
  const status = Number(readInteger(statusItems[0] as DerTlv));
  // 0 = granted, 1 = grantedWithMods, others = rejection.
  if (status !== 0 && status !== 1) {
    throw new AnchorVerificationError(`TSA refused request: PKIStatus=${status}`);
  }

  if (responseFields.length < 2) {
    throw new AnchorVerificationError('TimeStampResp: missing TimeStampToken');
  }

  // TimeStampToken is a ContentInfo (CMS SignedData).
  const contentInfo = responseFields[1] as DerTlv;
  if (contentInfo.tag !== 0x30) {
    throw new AnchorVerificationError('TimeStampToken is not a ContentInfo SEQUENCE');
  }
  const contentInfoFields = readSequence(contentInfo);
  if (contentInfoFields.length < 2) {
    throw new AnchorVerificationError('ContentInfo: missing fields');
  }
  const contentTypeOid = readOid(contentInfoFields[0] as DerTlv);
  if (contentTypeOid !== OID_SIGNED_DATA) {
    throw new AnchorVerificationError(
      `TimeStampToken content_type is not signed_data: ${contentTypeOid}`,
    );
  }
  const contentExplicit = contentInfoFields[1] as DerTlv;
  if (contentExplicit.tag !== 0xa0) {
    throw new AnchorVerificationError('ContentInfo content not in EXPLICIT [0]');
  }
  const signedDataItems = readSequence(readSequence(contentExplicit)[0] as DerTlv);
  // SignedData ::= SEQUENCE { version, digestAlgorithms SET, encapContentInfo,
  //                           certificates [0] IMPLICIT OPTIONAL, crls [1] IMPLICIT OPTIONAL,
  //                           signerInfos SET }
  // version is first INTEGER; digestAlgorithms is SET; encapContentInfo is SEQUENCE.
  if (signedDataItems.length < 4) {
    throw new AnchorVerificationError('SignedData: too few fields');
  }
  // signedDataItems[0] = version, [1] = digestAlgorithms SET, [2] = encapContentInfo SEQUENCE.
  const encapContentInfo = signedDataItems[2] as DerTlv;
  if (encapContentInfo.tag !== 0x30) {
    throw new AnchorVerificationError('EncapsulatedContentInfo not a SEQUENCE');
  }
  const encapFields = readSequence(encapContentInfo);
  if (encapFields.length < 2) {
    throw new AnchorVerificationError('EncapsulatedContentInfo missing eContent');
  }
  const eContentTypeOid = readOid(encapFields[0] as DerTlv);
  if (eContentTypeOid !== OID_TST_INFO) {
    throw new AnchorVerificationError(`encap content_type is not tst_info: ${eContentTypeOid}`);
  }
  const eContentExplicit = encapFields[1] as DerTlv;
  if (eContentExplicit.tag !== 0xa0) {
    throw new AnchorVerificationError('eContent not in EXPLICIT [0]');
  }
  // Inside EXPLICIT [0] is OCTET STRING containing TSTInfo DER bytes.
  const eContentInner = readTlv(eContentExplicit.buffer, eContentExplicit.valueStart);
  const tstInfoDer = readOctetString(eContentInner);
  const tstInfo = topSequence(tstInfoDer);
  const tstFields = readSequence(tstInfo);
  // TSTInfo ::= SEQUENCE { version, policy OID, messageImprint, serialNumber, genTime,
  //                        accuracy OPTIONAL, ordering BOOLEAN OPTIONAL, nonce OPTIONAL,
  //                        tsa [0] OPTIONAL, extensions [1] OPTIONAL }
  if (tstFields.length < 5) {
    throw new AnchorVerificationError('TSTInfo: too few fields');
  }
  const policyOid = readOid(tstFields[1] as DerTlv);
  const messageImprintSeq = tstFields[2] as DerTlv;
  if (messageImprintSeq.tag !== 0x30) {
    throw new AnchorVerificationError('MessageImprint is not a SEQUENCE');
  }
  const messageImprintFields = readSequence(messageImprintSeq);
  // MessageImprint ::= SEQUENCE { hashAlgorithm AlgorithmIdentifier, hashedMessage OCTET STRING }
  const hashAlgOid = readOid(readSequence(messageImprintFields[0] as DerTlv)[0] as DerTlv);
  const hashAlgorithm = hashAlgOid === '2.16.840.1.101.3.4.2.1' ? 'sha256' : hashAlgOid;
  const hashedMessage = readOctetString(messageImprintFields[1] as DerTlv);
  const serialNumber = readInteger(tstFields[3] as DerTlv);
  const genTime = readGeneralizedTime(tstFields[4] as DerTlv);

  // Optional nonce (INTEGER, tag 0x02).
  let nonce: bigint | null = null;
  for (let i = 5; i < tstFields.length; i++) {
    const f = tstFields[i] as DerTlv;
    if (f.tag === 0x02) {
      nonce = readInteger(f);
      break;
    }
  }

  // Extract the leaf cert from the optional certificates [0] IMPLICIT field.
  // It's tag 0xA0 (context [0] constructed) right after encapContentInfo.
  let certsField: DerTlv | null = null;
  for (let i = 3; i < signedDataItems.length; i++) {
    const f = signedDataItems[i] as DerTlv;
    if (f.tag === 0xa0) {
      certsField = f;
      break;
    }
  }
  if (certsField === null) {
    throw new AnchorVerificationError('SignedData has no certificates');
  }
  const certs = readSequence(certsField);
  if (certs.length === 0) {
    throw new AnchorVerificationError('certificates set is empty');
  }
  const leafCertDer = tlvDer(certs[0] as DerTlv);

  // Find signerInfos SET (last SET in signedDataItems).
  let signerInfosField: DerTlv | null = null;
  for (let i = signedDataItems.length - 1; i >= 0; i--) {
    const f = signedDataItems[i] as DerTlv;
    if (f.tag === 0x31) {
      signerInfosField = f;
      break;
    }
  }
  if (signerInfosField === null) {
    throw new AnchorVerificationError('SignerInfos SET not found');
  }
  const signerInfos = readSequence(signerInfosField);
  if (signerInfos.length !== 1) {
    throw new AnchorVerificationError(`expected exactly one SignerInfo, got ${signerInfos.length}`);
  }
  const signerInfo = signerInfos[0] as DerTlv;
  // SignerInfo ::= SEQUENCE { version, sid, digestAlgorithm, signedAttrs [0] IMPLICIT OPTIONAL,
  //                           signatureAlgorithm, signature, unsignedAttrs [1] OPTIONAL }
  const siFields = readSequence(signerInfo);
  // Find signedAttrs (tag 0xA0).
  let signedAttrs: DerTlv | null = null;
  let digestAlgo: DerTlv | null = null;
  let signatureAlgo: DerTlv | null = null;
  let signatureField: DerTlv | null = null;
  let sawSid = false;
  for (let i = 0; i < siFields.length; i++) {
    const f = siFields[i] as DerTlv;
    if (i === 0) continue; // version
    if (!sawSid) {
      sawSid = true;
      continue; // sid
    }
    if (digestAlgo === null && f.tag === 0x30) {
      digestAlgo = f;
      continue;
    }
    if (f.tag === 0xa0 && signedAttrs === null) {
      signedAttrs = f;
      continue;
    }
    if (signatureAlgo === null && f.tag === 0x30) {
      signatureAlgo = f;
      continue;
    }
    if (signatureField === null && f.tag === 0x04) {
      signatureField = f;
      break;
    }
  }
  if (
    signedAttrs === null ||
    signatureAlgo === null ||
    signatureField === null ||
    digestAlgo === null
  ) {
    throw new AnchorVerificationError('SignerInfo missing required fields');
  }

  const signedAttrsDer = tryWrapAsSet(tlvDer(signedAttrs));
  const signature = readOctetString(signatureField);
  const digestAlgorithmOid = readOid(readSequence(digestAlgo)[0] as DerTlv);
  const signatureAlgorithmOid = readOid(readSequence(signatureAlgo)[0] as DerTlv);

  return {
    policyOid,
    hashAlgorithm,
    messageImprint: hashedMessage,
    genTime,
    serialNumber,
    nonce,
    leafCertDer,
    signedAttrsDer,
    signature,
    digestAlgorithmOid,
    signatureAlgorithmOid,
  };
}

// ----- X.509 helpers --------------------------------------------------------

interface ParsedCertificate {
  readonly der: Uint8Array;
  readonly subjectDer: Uint8Array;
  readonly issuerDer: Uint8Array;
  readonly notBefore: Date;
  readonly notAfter: Date;
  readonly publicKey: KeyObject;
  /** TBSCertificate bytes (the portion signed by issuer). */
  readonly tbsBytes: Uint8Array;
  readonly signatureAlgorithmOid: string;
  readonly signature: Uint8Array;
  /** Whether BasicConstraints.cA is true. */
  readonly isCa: boolean;
}

function readUtcOrGeneralizedTime(tlv: DerTlv): Date {
  // UTCTime (0x17) format: YYMMDDhhmmssZ
  // GeneralizedTime (0x18) format: YYYYMMDDhhmmss[.fff]Z
  if (tlv.tag === 0x18) {
    return readGeneralizedTime(tlv);
  }
  if (tlv.tag !== 0x17) {
    throw new AnchorVerificationError(
      `expected UTCTime/GeneralizedTime, got 0x${tlv.tag.toString(16)}`,
    );
  }
  const text = new TextDecoder('ascii').decode(getValueBytes(tlv));
  if (!text.endsWith('Z')) {
    throw new AnchorVerificationError(`UTCTime not in UTC Z form: ${text}`);
  }
  const stripped = text.slice(0, -1);
  const m = /^(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})$/.exec(stripped);
  if (!m) {
    throw new AnchorVerificationError(`UTCTime not parseable: ${text}`);
  }
  const yy = Number(m[1]);
  const year = yy < 50 ? 2000 + yy : 1900 + yy;
  return new Date(`${year}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}Z`);
}

function parseCertificate(der: Uint8Array): ParsedCertificate {
  const cert = topSequence(der);
  const certFields = readSequence(cert);
  if (certFields.length < 3) {
    throw new AnchorVerificationError('Certificate: too few fields');
  }
  const tbs = certFields[0] as DerTlv;
  const sigAlg = certFields[1] as DerTlv;
  const sigField = certFields[2] as DerTlv;

  const tbsFields = readSequence(tbs);
  // TBSCertificate ::= SEQUENCE { [0] EXPLICIT Version OPTIONAL, serialNumber INTEGER,
  //                               signature AlgorithmIdentifier, issuer Name, validity Validity,
  //                               subject Name, subjectPublicKeyInfo SubjectPublicKeyInfo,
  //                               ... extensions [3] EXPLICIT OPTIONAL }
  let cursor = 0;
  // Optional version [0] EXPLICIT.
  if ((tbsFields[cursor] as DerTlv).tag === 0xa0) {
    cursor += 1;
  }
  cursor += 1; // serialNumber
  cursor += 1; // signature AlgorithmIdentifier
  const issuerDer = tlvDer(tbsFields[cursor] as DerTlv);
  cursor += 1;
  const validity = tbsFields[cursor] as DerTlv;
  cursor += 1;
  const subjectDer = tlvDer(tbsFields[cursor] as DerTlv);
  cursor += 1;
  const spki = tbsFields[cursor] as DerTlv;
  cursor += 1;

  const validityFields = readSequence(validity);
  const notBefore = readUtcOrGeneralizedTime(validityFields[0] as DerTlv);
  const notAfter = readUtcOrGeneralizedTime(validityFields[1] as DerTlv);

  // Convert SPKI to a Node KeyObject.
  let publicKey: KeyObject;
  try {
    publicKey = createPublicKey({ key: Buffer.from(tlvDer(spki)), format: 'der', type: 'spki' });
  } catch (exc) {
    throw new AnchorVerificationError(
      `failed to parse SubjectPublicKeyInfo: ${exc instanceof Error ? exc.message : String(exc)}`,
    );
  }

  // BasicConstraints CA flag: walk extensions if present.
  let isCa = false;
  while (cursor < tbsFields.length) {
    const f = tbsFields[cursor] as DerTlv;
    cursor += 1;
    if (f.tag !== 0xa3) continue; // extensions are [3] EXPLICIT
    const extsSeq = readSequence(f)[0] as DerTlv;
    const exts = readSequence(extsSeq);
    for (const ext of exts) {
      // Each ext: SEQUENCE { extnID OID, critical BOOLEAN OPT, extnValue OCTET STRING }
      const extFields = readSequence(ext);
      const oid = readOid(extFields[0] as DerTlv);
      if (oid !== '2.5.29.19') continue; // basicConstraints
      // extnValue is the last OCTET STRING.
      const valueBytes = readOctetString(extFields[extFields.length - 1] as DerTlv);
      const bcSeq = readTlv(valueBytes, 0);
      const bcFields = readSequence(bcSeq);
      if (bcFields.length > 0) {
        const cTlv = bcFields[0] as DerTlv;
        if (cTlv.tag === 0x01) {
          // BOOLEAN: cA. Non-zero value = true.
          isCa = (cTlv.buffer[cTlv.valueStart] as number) !== 0;
        }
      }
    }
  }

  // signature BIT STRING.
  const { unusedBits: _unused, bytes: sigBytes } = readBitString(sigField);
  const signatureAlgorithmOid = readOid(readSequence(sigAlg)[0] as DerTlv);

  return {
    der,
    subjectDer,
    issuerDer,
    notBefore,
    notAfter,
    publicKey,
    tbsBytes: tlvDer(tbs),
    signatureAlgorithmOid,
    signature: sigBytes,
    isCa,
  };
}

function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

function verifyRsaSha256(publicKey: KeyObject, data: Uint8Array, signature: Uint8Array): boolean {
  const v = createVerify('RSA-SHA256');
  v.update(Buffer.from(data));
  v.end();
  return v.verify(publicKey, Buffer.from(signature));
}

// ----- Public verification API ----------------------------------------------

export interface VerifyTimestampOptions {
  readonly expectedDigest: Uint8Array;
  readonly trustRootsDer: readonly Uint8Array[];
  readonly intermediatesDer?: readonly Uint8Array[];
  readonly verificationTime?: Date;
  readonly maxChainDepth?: number;
}

/**
 * Verify a parsed TimeStampToken against the expected message digest +
 * trust roots + intermediates.
 *
 * Mirrors the Python `verify_timestamp_token` API including multi-hop
 * intermediate chain walking, time-validity checks at every cert, and
 * BasicConstraints.cA enforcement on each intermediate.
 *
 * Throws `AnchorVerificationError` on any failure.
 */
export function verifyTimestampToken(
  parsed: ParsedTimestampTs,
  options: VerifyTimestampOptions,
): void {
  const {
    expectedDigest,
    trustRootsDer,
    intermediatesDer = [],
    verificationTime,
    maxChainDepth = 8,
  } = options;

  if (expectedDigest.length !== 32) {
    throw new AnchorVerificationError(
      `expectedDigest must be 32 bytes, got ${expectedDigest.length}`,
    );
  }
  if (parsed.hashAlgorithm !== 'sha256') {
    throw new AnchorVerificationError(
      `unexpected message-imprint hash algorithm: ${parsed.hashAlgorithm}`,
    );
  }
  if (!bytesEqual(parsed.messageImprint, expectedDigest)) {
    throw new AnchorVerificationError('message_imprint does not match expected digest');
  }

  let leaf: ParsedCertificate;
  try {
    leaf = parseCertificate(parsed.leafCertDer);
  } catch (exc) {
    throw new AnchorVerificationError(
      `leaf cert is not valid DER: ${exc instanceof Error ? exc.message : String(exc)}`,
    );
  }

  // Verify the TSA signature over signedAttrs using the leaf cert's
  // public key.
  if (!verifyRsaSha256(leaf.publicKey, parsed.signedAttrsDer, parsed.signature)) {
    throw new AnchorVerificationError('TSA signature does not verify against leaf cert');
  }

  // Time validity for the leaf.
  const when = verificationTime ?? new Date();
  if (when < leaf.notBefore) {
    throw new AnchorVerificationError(
      `verification_time ${when.toISOString()} precedes leaf cert not_before ${leaf.notBefore.toISOString()}`,
    );
  }
  if (when > leaf.notAfter) {
    throw new AnchorVerificationError(
      `verification_time ${when.toISOString()} exceeds leaf cert not_after ${leaf.notAfter.toISOString()}`,
    );
  }

  // Chain walk.
  const intermediates: ParsedCertificate[] = [];
  for (const der of intermediatesDer) {
    try {
      intermediates.push(parseCertificate(der));
    } catch {
      // Skip malformed intermediates.
    }
  }
  const roots: ParsedCertificate[] = [];
  for (const der of trustRootsDer) {
    try {
      roots.push(parseCertificate(der));
    } catch {
      // Skip malformed roots.
    }
  }
  if (roots.length === 0) {
    throw new AnchorVerificationError('no parseable trust roots provided');
  }

  let current = leaf;
  const visited = new Set<string>();
  visited.add(
    `${bytesToHexString(current.subjectDer)}:${bytesToHexString(current.tbsBytes.slice(0, 4))}`,
  );

  for (let hop = 0; hop < maxChainDepth; hop++) {
    const matchedRoot = findIssuer(current, roots);
    if (matchedRoot !== null) {
      verifyLink(current, matchedRoot, when);
      return;
    }
    const matchedIntermediate = findIssuer(current, intermediates);
    if (matchedIntermediate === null) {
      throw new AnchorVerificationError(
        `at hop ${hop}: cert issuer not in trust roots or intermediates`,
      );
    }
    if (!matchedIntermediate.isCa) {
      throw new AnchorVerificationError(
        `at hop ${hop}: candidate issuer is not a CA (missing BasicConstraints.cA=True)`,
      );
    }
    verifyLink(current, matchedIntermediate, when);
    const key = bytesToHexString(matchedIntermediate.subjectDer);
    if (visited.has(key)) {
      throw new AnchorVerificationError(`chain cycle detected at hop ${hop}`);
    }
    visited.add(key);
    current = matchedIntermediate;
  }
  throw new AnchorVerificationError(
    `chain depth exceeded maxChainDepth=${maxChainDepth} without reaching a configured trust root`,
  );
}

function findIssuer(
  child: ParsedCertificate,
  pool: readonly ParsedCertificate[],
): ParsedCertificate | null {
  for (const cand of pool) {
    if (bytesEqual(cand.subjectDer, child.issuerDer)) return cand;
  }
  return null;
}

function verifyLink(child: ParsedCertificate, issuer: ParsedCertificate, when: Date): void {
  if (when < issuer.notBefore) {
    throw new AnchorVerificationError(
      `verification_time precedes issuer cert not_before ${issuer.notBefore.toISOString()}`,
    );
  }
  if (when > issuer.notAfter) {
    throw new AnchorVerificationError(
      `verification_time exceeds issuer cert not_after ${issuer.notAfter.toISOString()}`,
    );
  }
  if (!verifyRsaSha256(issuer.publicKey, child.tbsBytes, child.signature)) {
    throw new AnchorVerificationError('cert signature does not verify against issuer');
  }
}

function bytesToHexString(b: Uint8Array): string {
  let out = '';
  for (let i = 0; i < b.length; i++) {
    out += (b[i] as number).toString(16).padStart(2, '0');
  }
  return out;
}
