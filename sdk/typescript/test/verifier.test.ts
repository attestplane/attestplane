// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';

import { chainExtend, genesisHead } from '../src/hashchain.js';
import { type ProofBundle, ProofBundleBuilder } from '../src/proof_bundle.js';
import { type ChainHead, type ChainedEvent, makeEventDraft } from '../src/types.js';
import { verifyProofBundle } from '../src/verifier.js';
import { resolveVerifyTaxonomyVersion } from '../src/verify_reason_codes.js';
import {
  VERIFY_REASON_REQUIRED_FIELD_MISSING,
  VERIFY_REASON_SIGNATURE_MISSING,
} from '../src/verify_reason_codes.js';

function buildChain(): ChainedEvent[] {
  let head: ChainHead = genesisHead();
  const event = chainExtend(
    head,
    makeEventDraft({ actor: 'agent', event_type: 'eval_event', payload: { ok: true } }),
    {
      event_id: '00000000-0000-7000-8000-000000000001',
      now: new Date('2026-05-19T00:00:00.000Z'),
    },
  );
  head = { seq: event.seq, event_hash: event.event_hash };
  return [event];
}

function bundleWithOneEvent(): ProofBundle {
  const builder = new ProofBundleBuilder({ chain_id: 'strict-ts', producer_runtime: 'test' });
  builder.extend(buildChain());
  return builder.build({ now: new Date('2026-05-19T00:00:00.000Z') });
}

function signedBundle(): ProofBundle {
  const bundle = JSON.parse(JSON.stringify(bundleWithOneEvent())) as Record<string, unknown>;
  const event = (bundle.events as Array<Record<string, unknown>>)[0];
  if (event === undefined) {
    throw new Error('expected a bundle event');
  }
  bundle.signatures = [
    {
      signature_schema_version: 1,
      signed_seq: 0,
      signed_event_hash_hex: event.event_hash_hex,
      signature_hex: 'a'.repeat(128),
      key_id: 'b'.repeat(32),
      public_key_der_b64: Buffer.from('public-key').toString('base64'),
      signing_cert_chain_b64: [],
      signed_at: '2026-05-19T00:00:00.000Z',
      signature_mode: 'per_event',
      signed_payload_b64: Buffer.from('payload').toString('base64'),
    },
  ];
  return bundle as unknown as ProofBundle;
}

describe('verifyProofBundle strict schema options', () => {
  it('preserves default unsigned bundle behavior', () => {
    const result = verifyProofBundle(bundleWithOneEvent());

    expect(result.ok).toBe(true);
    expect(result.primary_reason).toBeNull();
    expect(result.secondary_reasons).toEqual([]);
    expect(result.signed_attestation_schema_ok).toBe(true);
    expect(result.signed_attestation_schema_reason).toBeNull();
  });

  it('requires at least one signed attestation when strict schema is enabled', () => {
    const result = verifyProofBundle(bundleWithOneEvent(), { requireSignedAttestation: true });

    expect(result.ok).toBe(false);
    expect(result.error_code).toBe('bundle.schema.incomplete');
    expect(result.primary_reason).toBe(VERIFY_REASON_SIGNATURE_MISSING);
    expect(result.signed_attestation_schema_ok).toBe(false);
    expect(result.signed_attestation_schema_reason).toContain('signatures');
  });

  it('accepts the minimum signed-attestation schema when strict schema is enabled', () => {
    const result = verifyProofBundle(signedBundle(), { requireSignedAttestation: true });

    expect(result.ok).toBe(true);
    expect(result.error_code).toBe('VERIFY_OK');
    expect(result.primary_reason).toBeNull();
    expect(result.signed_attestation_schema_ok).toBe(true);
  });

  it('keeps requireNonEmpty fail-closed on empty bundles', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'empty-ts', producer_runtime: 'test' });
    const result = verifyProofBundle(builder.build(), { requireNonEmpty: true });

    expect(result.ok).toBe(false);
    expect(result.error_code).toBe('VERIFY_REQUIRED_FIELDS_MISSING');
    expect(result.primary_reason).toBe(VERIFY_REASON_REQUIRED_FIELD_MISSING);
    expect(result.signed_attestation_schema_ok).toBe(true);
  });

  it('does not require signed attestations when only requireNonEmpty is enabled', () => {
    const result = verifyProofBundle(bundleWithOneEvent(), { requireNonEmpty: true });

    expect(result.ok).toBe(true);
    expect(result.error_code).toBe('VERIFY_OK');
    expect(result.signed_attestation_schema_ok).toBe(true);
    expect(result.signed_attestation_schema_reason).toBeNull();
  });

  it('surfaces the resolved taxonomy_version on the public result object', () => {
    const result = verifyProofBundle(bundleWithOneEvent());

    expect(result.taxonomy_version).toBe(resolveVerifyTaxonomyVersion());
    expect(String(result.taxonomy_version)).toBe('1');
  });

  it('surfaces null taxonomy_version for legacy bundles without the field', () => {
    const bundle = JSON.parse(JSON.stringify(bundleWithOneEvent())) as Record<string, unknown>;
    const chainMetadata = bundle.chain_metadata as Record<string, unknown>;
    chainMetadata.evidence_taxonomy_version = undefined;

    const result = verifyProofBundle(bundle as unknown);

    expect(result.taxonomy_version).toBeNull();
  });
});
