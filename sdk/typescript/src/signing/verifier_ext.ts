// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Verifier extension — TypeScript mirror of
 * `sdk/python/src/attestplane/signing/verifier_ext.py`.
 *
 * Adds two functions alongside the existing
 * `verifyChainWithAnchors` in `../anchoring.ts`:
 *
 * - `verifyChainWithSignatures` — signature-only path.
 * - `verifyChainFull` — unified chain + signature + anchor.
 *
 * Pipeline ordering (architect review § 1 decision 8): chain →
 * signature → anchor. Each step always runs (no short-circuit) for
 * forensic completeness.
 *
 * Plurality priority (T6 review decision 7):
 * `valid > expired_key > invalid > unknown_key > unsigned`. Any single
 * `valid` signature for a seq lifts that seq to `valid`.
 *
 * Coverage (T6 review decision 7, option a): a `valid` segment-head
 * signature at seq=N covers seqs {previous-signed-head + 1 .. N} via
 * chain-integrity transitivity. Per-event signatures cover their
 * explicit `signed_seq` only.
 */

import { type KeyObject, createPublicKey, verify as ed25519Verify } from 'node:crypto';

import {
  type AnchorRecord,
  type AnchorVerificationResult,
  type SingleAnchorResult,
  type VerifyChainWithAnchorsOptions,
  verifyChainWithAnchors,
} from '../anchoring.js';
import type { ChainedEvent } from '../types.js';

import {
  SIGNATURE_SCHEMA_VERSION,
  type SignatureMode,
  type SignatureRecord,
  SigningError,
  deriveKeyId,
} from './base.js';
import { buildPerEventPayload, buildSegmentHeadPayload } from './signer.js';
import type { TrustRootEntry, TrustRoots } from './trust_roots.js';

export type SignatureStatus = 'unsigned' | 'valid' | 'invalid' | 'unknown_key' | 'expired_key';

/** Lower rank = better. Used to merge multiple signatures per seq. */
export const STATUS_RANK: Readonly<Record<SignatureStatus, number>> = Object.freeze({
  valid: 0,
  expired_key: 1,
  invalid: 2,
  unknown_key: 3,
  unsigned: 4,
});

export interface SingleSignatureResult {
  readonly record_index: number;
  readonly signed_seq: number;
  readonly key_id: string;
  readonly status: SignatureStatus;
  readonly reason: string | null;
}

export interface BundleVerificationResult {
  readonly chain_ok: boolean;
  readonly chain_reason: string | null;
  readonly anchored_seqs: ReadonlySet<number>;
  readonly unanchored_seqs: ReadonlySet<number>;
  readonly anchor_results: readonly SingleAnchorResult[];
  readonly signature_status: SignatureStatus;
  readonly signature_results: readonly SingleSignatureResult[];
  readonly signed_segment_count: number;
  readonly first_bad_signature_index: number | null;
  /**
   * `true` iff chain integrity + every anchor verify. Signature status
   * is deliberately NOT included (architect review § 1 decision 11);
   * callers wanting fail-closed signature semantics check
   * `signature_status === 'valid'` themselves.
   */
  readonly ok: boolean;
}

function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

function loadEd25519PublicKey(der: Uint8Array): KeyObject {
  return createPublicKey({
    key: Buffer.from(der),
    format: 'der',
    type: 'spki',
  });
}

function verifySingleSignature(
  record: SignatureRecord,
  index: number,
  eventsBySeq: Map<number, ChainedEvent>,
  chainId: string,
  trustRoots: TrustRoots,
  verificationTime: Date,
): SingleSignatureResult {
  const base = {
    record_index: index,
    signed_seq: record.signed_seq,
    key_id: record.key_id,
  };

  // 1. Schema version.
  if (record.signature_schema_version !== SIGNATURE_SCHEMA_VERSION) {
    return {
      ...base,
      status: 'invalid',
      reason:
        `signature_schema_version=${record.signature_schema_version} ` +
        `unsupported (expected ${SIGNATURE_SCHEMA_VERSION})`,
    };
  }

  if (record.signed_payload.length === 0) {
    return { ...base, status: 'invalid', reason: 'signed_payload is empty' };
  }

  // 2. Self-consistency: key_id derives from public_key_der.
  const derived = deriveKeyId(record.public_key_der);
  if (derived !== record.key_id) {
    return {
      ...base,
      status: 'invalid',
      reason: `record.key_id (${record.key_id}) does not derive from public_key_der (got ${derived})`,
    };
  }

  // 3. TrustRoots lookup.
  const entry: TrustRootEntry | null = trustRoots.lookup(record.key_id);
  if (entry === null) {
    return {
      ...base,
      status: 'unknown_key',
      reason: `key_id ${JSON.stringify(record.key_id)} not in trust roots`,
    };
  }

  // 4. Validity window.
  const vt = verificationTime.getTime();
  if (vt < entry.valid_from.getTime()) {
    return {
      ...base,
      status: 'expired_key',
      reason:
        `verification_time ${verificationTime.toISOString()} ` +
        `precedes valid_from ${entry.valid_from.toISOString()}`,
    };
  }
  if (vt > entry.valid_until.getTime()) {
    return {
      ...base,
      status: 'expired_key',
      reason:
        `verification_time ${verificationTime.toISOString()} ` +
        `exceeds valid_until ${entry.valid_until.toISOString()}`,
    };
  }

  // 5. Ed25519 signature verification.
  let pubkey: KeyObject;
  try {
    pubkey = loadEd25519PublicKey(record.public_key_der);
  } catch (exc) {
    return {
      ...base,
      status: 'invalid',
      reason: `public_key_der not parseable: ${(exc as Error).message}`,
    };
  }
  if (pubkey.asymmetricKeyType !== 'ed25519') {
    return {
      ...base,
      status: 'invalid',
      reason: `v1 supports Ed25519 keys only; got ${String(pubkey.asymmetricKeyType)}`,
    };
  }
  if (!bytesEqual(entry.public_key_der, record.public_key_der)) {
    return {
      ...base,
      status: 'invalid',
      reason:
        "record.public_key_der does not match trust-root entry's public_key_der " +
        '(same key_id, different bytes — tamper signal)',
    };
  }

  const ok = ed25519Verify(
    null,
    Buffer.from(record.signed_payload),
    pubkey,
    Buffer.from(record.signature),
  );
  if (!ok) {
    return {
      ...base,
      status: 'invalid',
      reason: 'Ed25519 verify failed',
    };
  }

  // 6. Payload semantics cross-check.
  const target = eventsBySeq.get(record.signed_seq);
  if (target === undefined) {
    return {
      ...base,
      status: 'invalid',
      reason: `signed_seq=${record.signed_seq} not in chain`,
    };
  }
  if (!bytesEqual(target.event_hash, record.signed_event_hash)) {
    return {
      ...base,
      status: 'invalid',
      reason: `signed_event_hash mismatch at seq=${record.signed_seq}`,
    };
  }

  if (record.signature_mode === 'segment_head') {
    const expected = buildSegmentHeadPayload(chainId, {
      seq: target.seq,
      event_hash: target.event_hash,
    });
    if (!bytesEqual(expected, record.signed_payload)) {
      let payloadChainId: string | unknown = '<unparseable>';
      try {
        const parsed = JSON.parse(Buffer.from(record.signed_payload).toString('utf-8')) as Record<
          string,
          unknown
        >;
        payloadChainId = parsed.chain_id;
      } catch {
        // payloadChainId stays as '<unparseable>'
      }
      return {
        ...base,
        status: 'invalid',
        reason: `signed_payload does not match expected canonical bytes for segment_head at seq=${record.signed_seq}; payload chain_id=${JSON.stringify(payloadChainId)}, verifier chain_id=${JSON.stringify(chainId)}`,
      };
    }
  } else {
    const expected = buildPerEventPayload(target.event);
    if (!bytesEqual(expected, record.signed_payload)) {
      return {
        ...base,
        status: 'invalid',
        reason: `signed_payload does not match canonicalize(event) for per_event at seq=${record.signed_seq}`,
      };
    }
  }

  return { ...base, status: 'valid', reason: null };
}

function mergeStatusAtSeq(perSeq: Map<number, SignatureStatus[]>): Map<number, SignatureStatus> {
  const result = new Map<number, SignatureStatus>();
  for (const [seq, statuses] of perSeq.entries()) {
    let best = statuses[0] as SignatureStatus;
    let bestRank = STATUS_RANK[best];
    for (let i = 1; i < statuses.length; i++) {
      const s = statuses[i] as SignatureStatus;
      const r = STATUS_RANK[s];
      if (r < bestRank) {
        best = s;
        bestRank = r;
      }
    }
    result.set(seq, best);
  }
  return result;
}

function computeSignedSegmentCount(
  events: readonly ChainedEvent[],
  perSeqStatus: Map<number, SignatureStatus>,
  perSeqModes: Map<number, Set<SignatureMode>>,
): number {
  const validSegmentHeads: number[] = [];
  const validPerEvents = new Set<number>();
  for (const [seq, status] of perSeqStatus.entries()) {
    if (status !== 'valid') continue;
    const modes = perSeqModes.get(seq) ?? new Set<SignatureMode>();
    if (modes.has('segment_head')) validSegmentHeads.push(seq);
    if (modes.has('per_event')) validPerEvents.add(seq);
  }
  validSegmentHeads.sort((a, b) => a - b);

  const covered = new Set<number>(validPerEvents);
  let prevHead = -1;
  for (const headSeq of validSegmentHeads) {
    for (let s = prevHead + 1; s <= headSeq; s++) {
      covered.add(s);
    }
    prevHead = headSeq;
  }

  const chainSeqs = new Set(events.map((e) => e.seq));
  let count = 0;
  for (const s of covered) {
    if (chainSeqs.has(s)) count++;
  }
  return count;
}

export interface VerifyChainWithSignaturesOptions {
  readonly chain_id: string;
  readonly trust_roots: TrustRoots;
  readonly verification_time?: Date;
}

export interface VerifyChainWithSignaturesResult {
  readonly signature_status: SignatureStatus;
  readonly signature_results: readonly SingleSignatureResult[];
  readonly signed_segment_count: number;
  readonly first_bad_signature_index: number | null;
}

export function verifyChainWithSignatures(
  events: readonly ChainedEvent[],
  signatures: readonly SignatureRecord[],
  options: VerifyChainWithSignaturesOptions,
): VerifyChainWithSignaturesResult {
  if (!options.chain_id) {
    throw new SigningError('verifyChainWithSignatures requires non-empty chain_id');
  }
  const actualWhen = options.verification_time ?? new Date();
  if (Number.isNaN(actualWhen.getTime())) {
    throw new SigningError('verifyChainWithSignatures requires a valid Date for verification_time');
  }

  const eventsBySeq = new Map<number, ChainedEvent>();
  for (const ev of events) eventsBySeq.set(ev.seq, ev);

  const results: SingleSignatureResult[] = [];
  const perSeqStatuses = new Map<number, SignatureStatus[]>();
  const perSeqModes = new Map<number, Set<SignatureMode>>();

  for (let i = 0; i < signatures.length; i++) {
    const rec = signatures[i] as SignatureRecord;
    const result = verifySingleSignature(
      rec,
      i,
      eventsBySeq,
      options.chain_id,
      options.trust_roots,
      actualWhen,
    );
    results.push(result);
    const seqList = perSeqStatuses.get(rec.signed_seq) ?? [];
    seqList.push(result.status);
    perSeqStatuses.set(rec.signed_seq, seqList);
    const modeSet = perSeqModes.get(rec.signed_seq) ?? new Set<SignatureMode>();
    modeSet.add(rec.signature_mode);
    perSeqModes.set(rec.signed_seq, modeSet);
  }

  const perSeqStatus = mergeStatusAtSeq(perSeqStatuses);

  let signatureStatus: SignatureStatus;
  if (signatures.length === 0) {
    signatureStatus = 'unsigned';
  } else {
    // Bundle-level = worst (highest rank) status across signed seqs.
    let worst: SignatureStatus = 'valid';
    let worstRank = STATUS_RANK.valid;
    for (const s of perSeqStatus.values()) {
      const r = STATUS_RANK[s];
      if (r > worstRank) {
        worst = s;
        worstRank = r;
      }
    }
    signatureStatus = worst;
  }

  const signedSegmentCount = computeSignedSegmentCount(events, perSeqStatus, perSeqModes);

  let firstBadIdx: number | null = null;
  for (const r of results) {
    if (r.status !== 'valid') {
      firstBadIdx = r.record_index;
      break;
    }
  }

  return {
    signature_status: signatureStatus,
    signature_results: results,
    signed_segment_count: signedSegmentCount,
    first_bad_signature_index: firstBadIdx,
  };
}

export interface VerifyChainFullOptions {
  readonly anchors?: readonly AnchorRecord[];
  readonly signatures?: readonly SignatureRecord[];
  readonly chain_id?: string;
  readonly trust_roots?: TrustRoots;
  readonly anchor_options?: VerifyChainWithAnchorsOptions;
  readonly verification_time?: Date;
}

export function verifyChainFull(
  events: readonly ChainedEvent[],
  options: VerifyChainFullOptions = {},
): BundleVerificationResult {
  const anchors = options.anchors ?? [];
  const signatures = options.signatures ?? [];

  const anchorOpts: VerifyChainWithAnchorsOptions = {
    ...(options.anchor_options ?? {}),
    ...(options.verification_time !== undefined
      ? { verificationTime: options.verification_time }
      : {}),
  };
  const anchorResult: AnchorVerificationResult = verifyChainWithAnchors(
    events,
    anchors,
    anchorOpts,
  );

  let sigStatus: SignatureStatus = 'unsigned';
  let sigResults: readonly SingleSignatureResult[] = [];
  let signedCount = 0;
  let firstBad: number | null = null;

  if (signatures.length > 0) {
    if (!options.chain_id || !options.trust_roots) {
      throw new SigningError(
        'verifyChainFull: signatures provided but chain_id or trust_roots is missing',
      );
    }
    const sigOpts: VerifyChainWithSignaturesOptions = {
      chain_id: options.chain_id,
      trust_roots: options.trust_roots,
      ...(options.verification_time !== undefined
        ? { verification_time: options.verification_time }
        : {}),
    };
    const sigOut = verifyChainWithSignatures(events, signatures, sigOpts);
    sigStatus = sigOut.signature_status;
    sigResults = sigOut.signature_results;
    signedCount = sigOut.signed_segment_count;
    firstBad = sigOut.first_bad_signature_index;
  }

  return {
    chain_ok: anchorResult.chain_ok,
    chain_reason: anchorResult.chain_reason,
    anchored_seqs: anchorResult.anchored_seqs,
    unanchored_seqs: anchorResult.unanchored_seqs,
    anchor_results: anchorResult.anchor_results,
    signature_status: sigStatus,
    signature_results: sigResults,
    signed_segment_count: signedCount,
    first_bad_signature_index: firstBad,
    ok: anchorResult.ok,
  };
}
