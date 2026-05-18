// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Signer — TypeScript mirror of
 * `sdk/python/src/attestplane/signing/signer.py` per T6 review § 1
 * decision 5: sync-only API. Background-worker mode is explicitly
 * deferred (TS `anchoring.ts` already lacks the worker pattern; no
 * need to break parity here).
 *
 * Two payload builders are exposed (matching Python):
 *
 * - `buildSegmentHeadPayload(chain_id, head)` — canonical-JSON over a
 *   fixed 5-key object `{chain_id, event_hash, schema_version, seq,
 *   signature_schema_version}`. Cross-language byte-stable.
 * - `buildPerEventPayload(event)` — canonical AuditEvent bytes
 *   bytes. Byte-identical to what `hashEvent()` hashes; already locked
 *   by v0.0.1-alpha `vectors.json`.
 */

import { sign as ed25519Sign } from 'node:crypto';

import { canonicalize } from '../canonical.js';
import { SCHEMA_VERSION as CHAIN_SCHEMA_VERSION, canonicalizeAuditEvent } from '../hashchain.js';
import type { AuditEvent, ChainHead, ChainedEvent } from '../types.js';

import {
  type KeyProvider,
  SIGNATURE_SCHEMA_VERSION,
  type SignatureMode,
  type SignatureRecord,
  SigningError,
  type SigningMaterial,
} from './base.js';
import { MultiSignerProvider } from './providers.js';

function bytesToHex(bytes: Uint8Array): string {
  let out = '';
  for (let i = 0; i < bytes.length; i++) {
    out += (bytes[i] as number).toString(16).padStart(2, '0');
  }
  return out;
}

/**
 * Construct the canonical-JSON bytes signed in segment-head mode.
 *
 * Locked recipe per architect review § 3:
 *
 * ```
 * { "chain_id": "<str>",
 *   "event_hash": "<lowercase hex>",
 *   "schema_version": 1,
 *   "seq": <int>,
 *   "signature_schema_version": 1 }
 * ```
 *
 * Cross-language byte-stability gate (T6 conformance assertion #1).
 */
export function buildSegmentHeadPayload(chainId: string, head: ChainHead): Uint8Array {
  if (!chainId) {
    throw new SigningError('segment-head signing requires non-empty chain_id');
  }
  return canonicalize({
    chain_id: chainId,
    event_hash: bytesToHex(head.event_hash),
    schema_version: CHAIN_SCHEMA_VERSION,
    seq: head.seq,
    signature_schema_version: SIGNATURE_SCHEMA_VERSION,
  });
}

/**
 * Per-event mode signs the canonical bytes of the AuditEvent. Identical
 * to `hashEvent`'s canonicalization call → already cross-language byte
 * stable via `vectors.json`.
 */
export function buildPerEventPayload(event: AuditEvent): Uint8Array {
  return canonicalizeAuditEvent(event);
}

function resolveMaterials(provider: KeyProvider | MultiSignerProvider): SigningMaterial[] {
  if (provider instanceof MultiSignerProvider) {
    return provider.getSigningMaterials();
  }
  return [provider.getSigningMaterial()];
}

function makeSignatureRecord(
  mat: SigningMaterial,
  args: {
    signed_seq: number;
    signed_event_hash: Uint8Array;
    signed_payload: Uint8Array;
    signature_mode: SignatureMode;
    signed_at: Date;
  },
): SignatureRecord {
  // Ed25519 in node:crypto: algorithm=null per Node docs.
  const signature = new Uint8Array(
    ed25519Sign(null, Buffer.from(args.signed_payload), mat.privateKey),
  );
  return {
    signature_schema_version: SIGNATURE_SCHEMA_VERSION,
    signed_seq: args.signed_seq,
    signed_event_hash: args.signed_event_hash,
    signature,
    key_id: mat.keyId,
    public_key_der: mat.publicKeyDer,
    signing_cert_chain: mat.signingCertChain,
    signed_at: args.signed_at,
    signature_mode: args.signature_mode,
    signed_payload: args.signed_payload,
  };
}

export interface SignerOptions {
  readonly chain_id: string;
  readonly key_provider: KeyProvider | MultiSignerProvider;
  readonly now?: () => Date;
}

/**
 * Event-signing producer (sync-only TS variant).
 *
 * Methods:
 * - `signEvent(event)` — per-event mode; signs canonical AuditEvent bytes.
 * - `signSegmentHead(head)` — segment-head mode; signs the locked
 *   5-key payload.
 *
 * Each method returns `SignatureRecord[]` (one entry per signing
 * material, supporting `MultiSignerProvider` plurality).
 */
export class Signer {
  private readonly _chainId: string;
  private readonly _keyProvider: KeyProvider | MultiSignerProvider;
  private readonly _now: () => Date;

  constructor(options: SignerOptions) {
    if (!options.chain_id) {
      throw new Error('Signer chain_id must be non-empty');
    }
    this._chainId = options.chain_id;
    this._keyProvider = options.key_provider;
    this._now = options.now ?? (() => new Date());
  }

  signEvent(event: ChainedEvent): SignatureRecord[] {
    const materials = resolveMaterials(this._keyProvider);
    const signedAt = this._now();
    if (Number.isNaN(signedAt.getTime())) {
      throw new SigningError('Signer.signEvent requires a valid Date for now()');
    }
    const payload = buildPerEventPayload(event.event);
    return materials.map((mat) =>
      makeSignatureRecord(mat, {
        signed_seq: event.seq,
        signed_event_hash: event.event_hash,
        signed_payload: payload,
        signature_mode: 'per_event',
        signed_at: signedAt,
      }),
    );
  }

  signSegmentHead(head: ChainHead): SignatureRecord[] {
    if (head.seq < 0) {
      throw new SigningError(
        'Signer.signSegmentHead requires a real chain head (seq >= 0); ' +
          'refusing to sign genesis sentinel',
      );
    }
    const materials = resolveMaterials(this._keyProvider);
    const signedAt = this._now();
    if (Number.isNaN(signedAt.getTime())) {
      throw new SigningError('Signer.signSegmentHead requires a valid Date for now()');
    }
    const payload = buildSegmentHeadPayload(this._chainId, head);
    return materials.map((mat) =>
      makeSignatureRecord(mat, {
        signed_seq: head.seq,
        signed_event_hash: head.event_hash,
        signed_payload: payload,
        signature_mode: 'segment_head',
        signed_at: signedAt,
      }),
    );
  }
}
