// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Minimal DER (Distinguished Encoding Rules) reader.
 *
 * Scope: enough to parse RFC-3161 TimeStampResp, RFC-5652 CMS
 * SignedData, RFC-3161 TSTInfo, and the subset of X.509 needed to
 * extract a leaf RSA public key. Hand-rolled rather than pulling in a
 * full ASN.1 library — we read sequentially and extract specific
 * fields by tag.
 *
 * Not a general-purpose ASN.1 library. Does NOT handle indefinite-
 * length encodings (forbidden in DER anyway), does NOT validate every
 * field's tag, does NOT handle constructed BIT STRINGs.
 *
 * Reading discipline: every parse function takes a Uint8Array and
 * returns either the parsed value or throws DerParseError. The
 * caller knows the expected structure from the spec.
 */

export class DerParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DerParseError';
  }
}

/** Parsed TLV (Tag-Length-Value) chunk. */
export interface DerTlv {
  /** ASN.1 tag byte (0x30 for SEQUENCE, 0x02 for INTEGER, etc.). */
  readonly tag: number;
  /** Length of the value portion (in bytes). */
  readonly length: number;
  /** Offset within the original buffer where the value starts. */
  readonly valueStart: number;
  /** Offset where this TLV ends (valueStart + length). */
  readonly end: number;
  /** Reference into the original buffer. */
  readonly buffer: Uint8Array;
}

/** Read one TLV starting at `offset` in `buffer`. */
export function readTlv(buffer: Uint8Array, offset: number): DerTlv {
  if (offset >= buffer.length) {
    throw new DerParseError(`offset ${offset} past end of buffer (${buffer.length})`);
  }
  const tag = buffer[offset] as number;
  let cursor = offset + 1;
  if (cursor >= buffer.length) {
    throw new DerParseError('truncated: missing length byte');
  }
  let length: number;
  const firstLen = buffer[cursor] as number;
  cursor += 1;
  if ((firstLen & 0x80) === 0) {
    length = firstLen;
  } else {
    const lenBytes = firstLen & 0x7f;
    if (lenBytes === 0) {
      throw new DerParseError('indefinite-length form not allowed in DER');
    }
    if (lenBytes > 4) {
      throw new DerParseError(`length field too large (${lenBytes} bytes)`);
    }
    if (cursor + lenBytes > buffer.length) {
      throw new DerParseError('truncated: length octets extend past buffer');
    }
    length = 0;
    for (let i = 0; i < lenBytes; i++) {
      length = (length << 8) | (buffer[cursor + i] as number);
    }
    cursor += lenBytes;
  }
  if (cursor + length > buffer.length) {
    throw new DerParseError(
      `truncated: value of length ${length} extends past buffer end`,
    );
  }
  return { tag, length, valueStart: cursor, end: cursor + length, buffer };
}

/** Read sequential TLVs inside a SEQUENCE/SET value. */
export function readSequence(tlv: DerTlv): DerTlv[] {
  const out: DerTlv[] = [];
  let cursor = tlv.valueStart;
  while (cursor < tlv.end) {
    const item = readTlv(tlv.buffer, cursor);
    out.push(item);
    cursor = item.end;
  }
  return out;
}

/** Return the raw value bytes of a TLV (a fresh slice). */
export function getValueBytes(tlv: DerTlv): Uint8Array {
  return tlv.buffer.slice(tlv.valueStart, tlv.end);
}

/** Decode an INTEGER. Throws if larger than safe integer range. */
export function readInteger(tlv: DerTlv): bigint {
  if (tlv.tag !== 0x02) {
    throw new DerParseError(`expected INTEGER (0x02), got tag 0x${tlv.tag.toString(16)}`);
  }
  let result = 0n;
  for (let i = 0; i < tlv.length; i++) {
    result = (result << 8n) | BigInt(tlv.buffer[tlv.valueStart + i] as number);
  }
  // Two's complement for signed: if high bit set, subtract.
  if (tlv.length > 0 && ((tlv.buffer[tlv.valueStart] as number) & 0x80) !== 0) {
    result -= 1n << BigInt(tlv.length * 8);
  }
  return result;
}

/** Decode an OID. */
export function readOid(tlv: DerTlv): string {
  if (tlv.tag !== 0x06) {
    throw new DerParseError(`expected OBJECT IDENTIFIER (0x06), got tag 0x${tlv.tag.toString(16)}`);
  }
  const bytes = tlv.buffer;
  const start = tlv.valueStart;
  const end = tlv.end;
  if (end <= start) return '';
  const first = bytes[start] as number;
  const arc1 = Math.floor(first / 40);
  const arc2 = first % 40;
  const arcs: string[] = [String(arc1), String(arc2)];
  let i = start + 1;
  while (i < end) {
    let value = 0n;
    while (i < end) {
      const b = bytes[i] as number;
      i += 1;
      value = (value << 7n) | BigInt(b & 0x7f);
      if ((b & 0x80) === 0) break;
    }
    arcs.push(value.toString());
  }
  return arcs.join('.');
}

/** Decode an OCTET STRING. */
export function readOctetString(tlv: DerTlv): Uint8Array {
  if (tlv.tag !== 0x04) {
    throw new DerParseError(`expected OCTET STRING (0x04), got tag 0x${tlv.tag.toString(16)}`);
  }
  return getValueBytes(tlv);
}

/** Decode a BIT STRING. Returns the raw bits (without the leading "unused bits" byte). */
export function readBitString(tlv: DerTlv): { unusedBits: number; bytes: Uint8Array } {
  if (tlv.tag !== 0x03) {
    throw new DerParseError(`expected BIT STRING (0x03), got tag 0x${tlv.tag.toString(16)}`);
  }
  if (tlv.length === 0) {
    throw new DerParseError('BIT STRING is empty');
  }
  const unusedBits = tlv.buffer[tlv.valueStart] as number;
  const bytes = tlv.buffer.slice(tlv.valueStart + 1, tlv.end);
  return { unusedBits, bytes };
}

/** Decode a GeneralizedTime to a Date. Format: YYYYMMDDhhmmss[.uuuuuu]Z. */
export function readGeneralizedTime(tlv: DerTlv): Date {
  if (tlv.tag !== 0x18) {
    throw new DerParseError(`expected GeneralizedTime (0x18), got tag 0x${tlv.tag.toString(16)}`);
  }
  const text = new TextDecoder('ascii').decode(getValueBytes(tlv));
  // Strict: must end with Z.
  if (!text.endsWith('Z')) {
    throw new DerParseError(`GeneralizedTime not in UTC Z form: ${text}`);
  }
  const stripped = text.slice(0, -1);
  // Match YYYYMMDDhhmmss with optional fractional seconds.
  const m = /^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?:\.(\d+))?$/.exec(stripped);
  if (!m) {
    throw new DerParseError(`GeneralizedTime not parseable: ${text}`);
  }
  const [, yy, mo, dd, hh, mi, ss, frac] = m;
  // Build a JS Date in UTC. JS uses ms precision; truncate sub-ms.
  const isoFrac = frac ? `.${frac.slice(0, 3).padEnd(3, '0')}` : '';
  const iso = `${yy}-${mo}-${dd}T${hh}:${mi}:${ss}${isoFrac}Z`;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    throw new DerParseError(`GeneralizedTime produced invalid Date: ${text}`);
  }
  return d;
}

/** Return the DER bytes of this TLV (including tag+length+value). */
export function tlvDer(tlv: DerTlv): Uint8Array {
  // Find the start of this TLV. We track valueStart but tag is at the
  // position before length-bytes; reconstruct by walking back.
  // Easier: build from the buffer using known offsets.
  const tagAt = _tagOffsetOf(tlv);
  return tlv.buffer.slice(tagAt, tlv.end);
}

function _tagOffsetOf(tlv: DerTlv): number {
  // We know valueStart and length and the buffer. Walk back from
  // valueStart to find the tag offset: there is exactly 1 byte for the
  // tag, then 1 or more length bytes.
  // length-form bytes count: length < 0x80 → 1 byte; else 1 + (firstLen & 0x7f).
  // We can compute this from the recorded length.
  // Actually it's simpler: tagOffset = valueStart - 1 - lenOctets.
  let lenOctets: number;
  if (tlv.length < 0x80) {
    lenOctets = 1;
  } else if (tlv.length < 0x100) {
    lenOctets = 2;
  } else if (tlv.length < 0x10000) {
    lenOctets = 3;
  } else if (tlv.length < 0x1000000) {
    lenOctets = 4;
  } else {
    lenOctets = 5;
  }
  return tlv.valueStart - lenOctets - 1;
}
