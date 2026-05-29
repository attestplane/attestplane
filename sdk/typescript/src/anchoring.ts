// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * RFC-3161 anchoring (TypeScript port of `sdk/python/src/attestplane/anchoring/`).
 *
 * Ships the design skeleton — types, abstract base, mock provider,
 * multi-TSA composite, and an anchor-aware verifier API. Real
 * cryptography-backed providers (Free TSA, DigiCert) ship in a
 * follow-up alongside `anchor_vectors.json` cross-language fixtures.
 *
 * Surface parity with the Python module: anyone reading the Python
 * skeleton at `attestplane.anchoring` finds the same shapes here.
 */

import { createHash } from 'node:crypto';

import { type VerificationResult, verifyChain } from './hashchain.js';
import { parseTimestampResponse, verifyTimestampToken } from './rfc3161.js';
import type { ChainedEvent } from './types.js';

export const ANCHOR_SCHEMA_VERSION = 1 as const;

export type AnchorStatus = 'unanchored' | 'pending' | 'anchored' | 'failed_permanent';

export type CertStatus =
  | 'VALID'
  | 'VALID_UNVERIFIED'
  | 'MISSING_LTV_ARTIFACTS'
  | 'EXPIRED_VALID_AT_ISSUANCE'
  | 'REVOKED';
export type AnchorVerificationStatus = 'verified' | 'failed' | 'not_performed' | 'quarantined';

// ----- Error hierarchy -----

export class AnchorError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AnchorError';
  }
}

export class TSAUnavailableError extends AnchorError {
  constructor(message: string) {
    super(message);
    this.name = 'TSAUnavailableError';
  }
}

export class AnchorVerificationError extends AnchorError {
  constructor(message: string) {
    super(message);
    this.name = 'AnchorVerificationError';
  }
}

// ----- Anchor data model -----

export interface AnchorRecord {
  readonly anchor_schema_version: number;
  readonly anchored_seq: number;
  readonly anchored_event_hash: Uint8Array;
  readonly tsa_provider_id: string;
  readonly tsa_token: Uint8Array;
  readonly tsa_cert_chain: readonly Uint8Array[];
  readonly ocsp_responses: readonly Uint8Array[];
  readonly issued_at_claimed: Date;
}

export function validateAnchorRecord(a: AnchorRecord): void {
  if (a.anchor_schema_version !== ANCHOR_SCHEMA_VERSION) {
    throw new AnchorError(
      `AnchorRecord.anchor_schema_version must be ${ANCHOR_SCHEMA_VERSION}, got ${a.anchor_schema_version}`,
    );
  }
  if (a.anchored_event_hash.length !== 32) {
    throw new AnchorError(
      `AnchorRecord.anchored_event_hash must be 32 bytes, got ${a.anchored_event_hash.length}`,
    );
  }
  if (a.anchored_seq < 0) {
    throw new AnchorError('AnchorRecord.anchored_seq must be ≥ 0');
  }
  if (!a.tsa_provider_id) {
    throw new AnchorError('AnchorRecord.tsa_provider_id must be non-empty');
  }
}

export interface AnchorPolicy {
  readonly batch_size: number;
  readonly max_idle_seconds: number;
  readonly per_event: boolean;
}

export const DEFAULT_ANCHOR_POLICY: AnchorPolicy = Object.freeze({
  batch_size: 64,
  max_idle_seconds: 60,
  per_event: false,
});

export function makeAnchorPolicy(input?: Partial<AnchorPolicy>): AnchorPolicy {
  const merged = { ...DEFAULT_ANCHOR_POLICY, ...input };
  if (merged.batch_size < 1) {
    throw new AnchorError('AnchorPolicy.batch_size must be ≥ 1');
  }
  if (merged.max_idle_seconds < 1) {
    throw new AnchorError('AnchorPolicy.max_idle_seconds must be ≥ 1');
  }
  return Object.freeze({ ...merged });
}

export interface TimestampRequest {
  readonly digest: Uint8Array;
  readonly nonce?: Uint8Array;
}

export function makeTimestampRequest(input: TimestampRequest): TimestampRequest {
  if (input.digest.length !== 32) {
    throw new AnchorError(
      `TimestampRequest.digest must be 32 bytes (SHA-256), got ${input.digest.length}`,
    );
  }
  return Object.freeze({ ...input });
}

// ----- Abstract provider -----

const FORBIDDEN_PROVIDER_METHODS = new Set([
  'mutate',
  'rewrite',
  'replace',
  'revoke',
  'retract',
  'delete',
  'remove',
]);

/**
 * Abstract base for any TSA provider implementation.
 *
 * TypeScript analogue of Python's `TSAProvider` ABC. The
 * forbidden-mutating-verb check runs in the constructor (TS has no
 * `__init_subclass__` equivalent).
 */
export abstract class TSAProvider {
  abstract readonly provider_id: string;
  abstract readonly schema_version: number;

  constructor() {
    const proto = Object.getPrototypeOf(this) as object;
    const offenders: string[] = [];
    for (const name of Object.getOwnPropertyNames(proto)) {
      if (name === 'constructor') continue;
      if (name.startsWith('_')) continue;
      if (FORBIDDEN_PROVIDER_METHODS.has(name)) {
        offenders.push(name);
      }
    }
    if (offenders.length > 0) {
      offenders.sort();
      throw new AnchorError(
        `${this.constructor.name} defines forbidden mutating method(s) [${offenders.join(', ')}]; TSA providers do not own anchor validity. See ADR-0003 § 4.`,
      );
    }
  }

  abstract requestTimestamp(
    request: TimestampRequest,
    options?: { readonly anchoredSeq?: number; readonly now?: Date },
  ): AnchorRecord;
}

// ----- Mock provider -----

export interface MockTSAProviderInput {
  readonly provider_id?: string;
  readonly fixed_time?: Date;
  readonly fail_with?: Error;
}

export class MockTSAProvider extends TSAProvider {
  readonly provider_id: string;
  readonly schema_version = ANCHOR_SCHEMA_VERSION;
  private readonly _fixed_time: Date | null;
  private readonly _fail_with: Error | null;

  constructor(input: MockTSAProviderInput = {}) {
    super();
    const pid = input.provider_id ?? 'mock.tsa.local';
    if (!pid) {
      throw new Error('MockTSAProvider provider_id must be non-empty');
    }
    this.provider_id = pid;
    this._fixed_time = input.fixed_time ?? null;
    this._fail_with = input.fail_with ?? null;
  }

  requestTimestamp(
    request: TimestampRequest,
    options: { readonly anchoredSeq?: number; readonly now?: Date } = {},
  ): AnchorRecord {
    if (this._fail_with !== null) {
      throw this._fail_with;
    }
    const when = this._fixed_time ?? options.now ?? new Date();
    if (Number.isNaN(when.getTime())) {
      throw new TSAUnavailableError('MockTSAProvider requires a valid Date');
    }

    const sha = (label: string): Uint8Array => {
      const h = createHash('sha256');
      h.update(label);
      h.update(request.digest);
      return new Uint8Array(h.digest());
    };

    const record: AnchorRecord = {
      anchor_schema_version: ANCHOR_SCHEMA_VERSION,
      anchored_seq: options.anchoredSeq ?? 0,
      anchored_event_hash: request.digest,
      tsa_provider_id: this.provider_id,
      tsa_token: sha('mock-token:'),
      tsa_cert_chain: [sha('mock-cert:')],
      ocsp_responses: [sha('mock-ocsp:')],
      issued_at_claimed: when,
    };
    validateAnchorRecord(record);
    return record;
  }
}

// ----- Multi-provider composite -----

export interface MultiTSAProviderInput {
  readonly providers: readonly TSAProvider[];
  readonly tolerate_partial?: boolean;
}

export class MultiTSAProvider {
  private readonly _providers: readonly TSAProvider[];
  private readonly _tolerate_partial: boolean;

  constructor(input: MultiTSAProviderInput) {
    if (input.providers.length === 0) {
      throw new Error('MultiTSAProvider requires at least one provider');
    }
    const ids = new Set<string>();
    for (const p of input.providers) {
      if (ids.has(p.provider_id)) {
        throw new Error('MultiTSAProvider providers must have distinct provider_id values');
      }
      if (p.schema_version !== ANCHOR_SCHEMA_VERSION) {
        throw new Error(
          `provider '${p.provider_id}' has schema_version=${p.schema_version}; ` +
            `this composite only handles ANCHOR_SCHEMA_VERSION=${ANCHOR_SCHEMA_VERSION}`,
        );
      }
      ids.add(p.provider_id);
    }
    this._providers = [...input.providers];
    this._tolerate_partial = input.tolerate_partial ?? false;
  }

  get providerIds(): readonly string[] {
    return this._providers.map((p) => p.provider_id);
  }

  requestTimestamps(
    request: TimestampRequest,
    options?: { readonly anchoredSeq?: number; readonly now?: Date },
  ): AnchorRecord[] {
    const results: AnchorRecord[] = [];
    let firstError: TSAUnavailableError | null = null;
    for (const provider of this._providers) {
      try {
        results.push(provider.requestTimestamp(request, options));
      } catch (exc) {
        if (exc instanceof TSAUnavailableError) {
          if (!this._tolerate_partial) throw exc;
          if (firstError === null) firstError = exc;
        } else {
          throw exc;
        }
      }
    }
    if (this._tolerate_partial && results.length === 0 && firstError !== null) {
      throw firstError;
    }
    return results;
  }
}

// ----- Verifier -----

export interface SingleAnchorResult {
  readonly seq: number;
  readonly provider: string;
  readonly valid: boolean;
  readonly cert_status: CertStatus;
  readonly ltv_artifacts_present: boolean;
  readonly reason: string | null;
}

export interface AnchorVerificationResult {
  readonly chain_ok: boolean;
  readonly chain_reason: string | null;
  readonly anchored_seqs: ReadonlySet<number>;
  readonly unanchored_seqs: ReadonlySet<number>;
  readonly anchor_results: readonly SingleAnchorResult[];
  readonly verification_status: AnchorVerificationStatus;
  readonly quarantine_reason: string | null;
  readonly ok: boolean;
}

function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

export interface VerifyChainWithAnchorsOptions {
  readonly trustRootsDer?: readonly Uint8Array[];
  readonly intermediatesDer?: readonly Uint8Array[];
  readonly verificationTime?: Date;
  readonly maxChainDepth?: number;
}

export function verifyChainWithAnchors(
  events: readonly ChainedEvent[],
  anchors: readonly AnchorRecord[],
  options: VerifyChainWithAnchorsOptions = {},
): AnchorVerificationResult {
  const chainResult: VerificationResult = verifyChain(events);
  const seqsInChain = new Set(events.map((e) => e.seq));
  const anchorResults: SingleAnchorResult[] = [];
  const anchoredSeqs = new Set<number>();

  for (const anchor of anchors) {
    const provider = anchor.tsa_provider_id;

    if (anchor.anchor_schema_version !== ANCHOR_SCHEMA_VERSION) {
      anchorResults.push({
        seq: anchor.anchored_seq,
        provider,
        valid: false,
        cert_status: 'MISSING_LTV_ARTIFACTS',
        ltv_artifacts_present: false,
        reason: `anchor_schema_version=${anchor.anchor_schema_version}; this verifier handles version ${ANCHOR_SCHEMA_VERSION} only`,
      });
      continue;
    }

    if (!seqsInChain.has(anchor.anchored_seq)) {
      anchorResults.push({
        seq: anchor.anchored_seq,
        provider,
        valid: false,
        cert_status: 'MISSING_LTV_ARTIFACTS',
        ltv_artifacts_present: anchor.tsa_cert_chain.length > 0,
        reason: `anchored_seq=${anchor.anchored_seq} not in chain`,
      });
      continue;
    }

    const target = events[anchor.anchored_seq] as ChainedEvent;
    if (!bytesEqual(target.event_hash, anchor.anchored_event_hash)) {
      anchorResults.push({
        seq: anchor.anchored_seq,
        provider,
        valid: false,
        cert_status: 'MISSING_LTV_ARTIFACTS',
        ltv_artifacts_present: anchor.tsa_cert_chain.length > 0,
        reason: `anchored_event_hash mismatch at seq ${anchor.anchored_seq}`,
      });
      continue;
    }

    if (Number.isNaN(anchor.issued_at_claimed.getTime())) {
      anchorResults.push({
        seq: anchor.anchored_seq,
        provider,
        valid: false,
        cert_status: 'MISSING_LTV_ARTIFACTS',
        ltv_artifacts_present: anchor.tsa_cert_chain.length > 0,
        reason: 'issued_at_claimed is not a valid Date',
      });
      continue;
    }

    const ltv = anchor.tsa_cert_chain.length > 0 && anchor.ocsp_responses.length > 0;
    if (!ltv) {
      anchorResults.push({
        seq: anchor.anchored_seq,
        provider,
        valid: false,
        cert_status: 'MISSING_LTV_ARTIFACTS',
        ltv_artifacts_present: false,
        reason:
          'tsa_cert_chain or ocsp_responses is empty; CAdES-A long-term validation requires both',
      });
      continue;
    }

    // If trust roots are configured, do real signature verification.
    if (options.trustRootsDer && options.trustRootsDer.length > 0) {
      try {
        const parsed = parseTimestampResponse(anchor.tsa_token);
        const verifyOpts: import('./rfc3161.js').VerifyTimestampOptions = {
          expectedDigest: anchor.anchored_event_hash,
          trustRootsDer: options.trustRootsDer,
          intermediatesDer: [...anchor.tsa_cert_chain, ...(options.intermediatesDer ?? [])],
          ...(options.verificationTime !== undefined
            ? { verificationTime: options.verificationTime }
            : {}),
          ...(options.maxChainDepth !== undefined ? { maxChainDepth: options.maxChainDepth } : {}),
        };
        verifyTimestampToken(parsed, verifyOpts);
      } catch (exc) {
        if (exc instanceof AnchorVerificationError) {
          anchorResults.push({
            seq: anchor.anchored_seq,
            provider,
            valid: false,
            cert_status: 'MISSING_LTV_ARTIFACTS',
            ltv_artifacts_present: true,
            reason: exc.message,
          });
          continue;
        }
        throw exc;
      }
      anchorResults.push({
        seq: anchor.anchored_seq,
        provider,
        valid: true,
        cert_status: 'VALID',
        ltv_artifacts_present: true,
        reason: null,
      });
    } else {
      anchorResults.push({
        seq: anchor.anchored_seq,
        provider,
        valid: true,
        cert_status: 'VALID_UNVERIFIED',
        ltv_artifacts_present: true,
        reason: null,
      });
    }
    anchoredSeqs.add(anchor.anchored_seq);
  }

  const unanchoredSeqs = new Set<number>();
  for (const seq of seqsInChain) {
    if (!anchoredSeqs.has(seq)) unanchoredSeqs.add(seq);
  }

  const allAnchorsValid = anchorResults.every((a) => a.valid);
  const verificationStatus: AnchorVerificationStatus =
    anchorResults.length === 0 ? 'not_performed' : allAnchorsValid ? 'verified' : 'failed';
  return {
    chain_ok: chainResult.ok,
    chain_reason: chainResult.reason,
    anchored_seqs: anchoredSeqs,
    unanchored_seqs: unanchoredSeqs,
    anchor_results: anchorResults,
    verification_status: verificationStatus,
    quarantine_reason: null,
    ok: chainResult.ok && verificationStatus === 'verified',
  };
}
