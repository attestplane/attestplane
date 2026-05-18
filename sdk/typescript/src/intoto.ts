// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * in-toto Statement v1 + DSSE shape helpers for Attestplane evidence.
 *
 * These helpers only build and parse deterministic statement/envelope shapes.
 * They do not sign, verify signatures, manage keys, submit transparency-log
 * entries, or implement a complete SLSA provenance pipeline.
 */

import type { ProofBundle } from './proof_bundle.js';

export const PREDICATE_TYPE_V1 = 'https://attestplane.io/v1/agent-runtime-event' as const;
export const DSSE_PAYLOAD_TYPE = 'application/vnd.in-toto+json' as const;
export const STATEMENT_TYPE = 'https://in-toto.io/Statement/v1' as const;

export class IntotoError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'IntotoError';
  }
}

export interface IntotoSubject {
  readonly name: string;
  readonly digest: {
    readonly sha256: string;
  };
}

export interface IntotoStatement {
  readonly _type: typeof STATEMENT_TYPE;
  readonly subject: readonly IntotoSubject[];
  readonly predicateType: typeof PREDICATE_TYPE_V1;
  readonly predicate: {
    readonly chain_metadata: ProofBundle['chain_metadata'];
    readonly events: ProofBundle['events'];
    readonly verification_report: ProofBundle['verification_report'];
    readonly framework_mappings: ProofBundle['framework_mappings'];
    readonly forbidden_fields: ProofBundle['forbidden_fields'];
  };
}

export interface DsseSignature {
  readonly keyid: string;
  readonly sig: string;
}

export interface DsseEnvelope {
  readonly payloadType: typeof DSSE_PAYLOAD_TYPE;
  readonly payload: string;
  readonly signatures: readonly DsseSignature[];
}

export function proofBundleToInTotoStatement(bundle: ProofBundle): IntotoStatement {
  if (bundle === null || typeof bundle !== 'object') {
    throw new IntotoError('bundle must be an object');
  }
  const chainMetadata = bundle.chain_metadata;
  if (
    chainMetadata === null ||
    typeof chainMetadata !== 'object' ||
    !chainMetadata.chain_id ||
    !chainMetadata.head_hash_hex
  ) {
    throw new IntotoError('bundle.chain_metadata must include chain_id and head_hash_hex');
  }
  return {
    _type: STATEMENT_TYPE,
    subject: [
      {
        name: chainMetadata.chain_id,
        digest: { sha256: chainMetadata.head_hash_hex },
      },
    ],
    predicateType: PREDICATE_TYPE_V1,
    predicate: {
      chain_metadata: chainMetadata,
      events: bundle.events,
      verification_report: bundle.verification_report,
      framework_mappings: bundle.framework_mappings,
      forbidden_fields: bundle.forbidden_fields,
    },
  };
}

export function canonicalJsonBytes(value: unknown): Uint8Array {
  const encoded = JSON.stringify(sortJsonValue(value));
  if (encoded === undefined) {
    throw new IntotoError('value is not JSON serializable');
  }
  return new TextEncoder().encode(encoded);
}

function sortJsonValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map((item) => sortJsonValue(item));
  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value).sort()) {
      out[key] = sortJsonValue((value as Record<string, unknown>)[key]);
    }
    return out;
  }
  return value;
}

export function statementToDsseEnvelope(
  statement: IntotoStatement,
  options: { readonly signatures?: readonly DsseSignature[] } = {},
): DsseEnvelope {
  return {
    payloadType: DSSE_PAYLOAD_TYPE,
    payload: Buffer.from(canonicalJsonBytes(statement)).toString('base64'),
    signatures: options.signatures ?? [],
  };
}

export function dsseEnvelopeToStatement(envelope: DsseEnvelope): IntotoStatement {
  if (envelope === null || typeof envelope !== 'object') {
    throw new IntotoError('envelope must be an object');
  }
  if (envelope.payloadType !== DSSE_PAYLOAD_TYPE) {
    throw new IntotoError(
      `unexpected payloadType: ${JSON.stringify(envelope.payloadType)}; expected ${JSON.stringify(DSSE_PAYLOAD_TYPE)}`,
    );
  }
  if (typeof envelope.payload !== 'string') {
    throw new IntotoError('envelope.payload must be a base64 string');
  }
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(envelope.payload) || envelope.payload.length % 4 !== 0) {
    throw new IntotoError('failed to base64-decode payload: invalid base64');
  }
  let decoded: string;
  try {
    decoded = Buffer.from(envelope.payload, 'base64').toString('utf-8');
  } catch (exc) {
    throw new IntotoError(`failed to base64-decode payload: ${String(exc)}`);
  }
  let statement: unknown;
  try {
    statement = JSON.parse(decoded);
  } catch (exc) {
    throw new IntotoError(`payload is not valid JSON: ${String(exc)}`);
  }
  if (statement === null || typeof statement !== 'object' || Array.isArray(statement)) {
    throw new IntotoError('payload JSON must be an object');
  }
  return statement as IntotoStatement;
}
