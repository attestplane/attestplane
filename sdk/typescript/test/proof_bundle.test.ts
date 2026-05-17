// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Tests for src/proof_bundle.ts and src/verifier.ts. Mirror of
 * sdk/python/tests/test_proof_bundle.py.
 */

import * as fs from 'node:fs/promises';
import * as os from 'node:os';
import * as path from 'node:path';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { chainExtend, genesisHead } from '../src/hashchain.js';
import {
  DEFAULT_FORBIDDEN_FIELDS,
  ProofBundleBuilder,
  buildAuditorExport,
  type FrameworkMapping,
} from '../src/proof_bundle.js';
import { makeEventDraft, type ChainHead, type ChainedEvent } from '../src/types.js';
import {
  BundleSchemaError,
  BundleVerificationError,
  shortSummary,
  verifyProofBundle,
  verifyProofBundleFile,
} from '../src/verifier.js';

function buildGoodChain(n: number): ChainedEvent[] {
  const ts = new Date('2026-05-17T12:00:00.000Z');
  const chain: ChainedEvent[] = [];
  let head: ChainHead = genesisHead();
  for (let i = 0; i < n; i++) {
    const draft = makeEventDraft({
      event_type: i % 2 === 0 ? 'eval_event' : 'policy_check_event',
      actor: `agent://test/${i}`,
      payload: { index: i },
      session_id: `sess-${i}`,
    });
    const event = chainExtend(head, draft, {
      now: ts,
      event_id: `00000000-0000-7000-8000-${i.toString().padStart(12, '0')}`,
    });
    chain.push(event);
    head = { seq: event.seq, event_hash: event.event_hash };
  }
  return chain;
}

describe('ProofBundleBuilder', () => {
  it('builds an empty bundle with sentinel head', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'empty', producer_runtime: 'test' });
    const bundle = builder.build();
    expect(bundle.bundle_version).toBe(1);
    expect(bundle.events).toEqual([]);
    expect(bundle.verification_report.ok).toBe(true);
    expect(bundle.chain_metadata.head_seq).toBe(-1);
    expect(bundle.chain_metadata.head_hash_hex).toBe('0'.repeat(64));
  });

  it('builds a bundle from a chain', () => {
    const builder = new ProofBundleBuilder({
      chain_id: 'my-chain',
      producer_runtime: 'test v1.0',
    });
    builder.extend(buildGoodChain(3));
    const bundle = builder.build();
    expect(bundle.events.length).toBe(3);
    expect(bundle.verification_report.ok).toBe(true);
    expect(bundle.chain_metadata.head_seq).toBe(2);
  });

  it('embeds the default forbidden_fields list', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'x', producer_runtime: 'test' });
    const bundle = builder.build();
    expect(new Set(bundle.forbidden_fields)).toEqual(new Set(DEFAULT_FORBIDDEN_FIELDS));
    for (const term of ['secrets', 'tokens', 'jwts', 'private_keys', 'pii']) {
      expect(bundle.forbidden_fields).toContain(term);
    }
  });

  it('rejects framework mapping with bad event index', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'fm', producer_runtime: 'test' });
    builder.extend(buildGoodChain(2));
    const mapping: FrameworkMapping = {
      obligation_id: 'eu_ai_act.art12.1.automatic_recording',
      evidence_event_indexes: [99],
      implementation_status_at_bundle_time: 'designed_toward',
    };
    expect(() => builder.addFrameworkMapping(mapping)).toThrow(/references event index/);
  });

  it('accepts a valid framework mapping', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'fm', producer_runtime: 'test' });
    builder.extend(buildGoodChain(2));
    builder.addFrameworkMapping({
      obligation_id: 'eu_ai_act.art12.3c.matched_input_data',
      evidence_event_indexes: [0],
      implementation_status_at_bundle_time: 'field_supported',
    });
    const bundle = builder.build();
    expect(bundle.framework_mappings.length).toBe(1);
    expect(bundle.framework_mappings[0]!.obligation_id).toBe('eu_ai_act.art12.3c.matched_input_data');
  });

  it('serializes timestamps with 6-digit microsecond precision', () => {
    const builder = new ProofBundleBuilder({ chain_id: 't', producer_runtime: 'test' });
    builder.extend(buildGoodChain(1));
    const bundle = builder.build();
    expect(bundle.events[0]!.event.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/);
  });
});

describe('verifyProofBundle', () => {
  it('accepts a good bundle', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'v', producer_runtime: 'test' });
    builder.extend(buildGoodChain(3));
    const bundle = builder.build();
    const result = verifyProofBundle(bundle);
    expect(result.ok).toBe(true);
    expect(result.event_count).toBe(3);
    expect(result.agreement).toBe(true);
    expect(result.chain_result.ok).toBe(true);
  });

  it('rejects a bad bundle_version', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'v', producer_runtime: 'test' });
    const bundle = builder.build() as unknown as Record<string, unknown>;
    bundle['bundle_version'] = 99;
    expect(() => verifyProofBundle(bundle)).toThrow(BundleSchemaError);
  });

  it('rejects a bundle missing required fields', () => {
    expect(() => verifyProofBundle({ bundle_version: 1 })).toThrow(/missing required fields/);
  });

  it('rejects a non-object input', () => {
    expect(() => verifyProofBundle('not an object')).toThrow(BundleSchemaError);
    expect(() => verifyProofBundle(null)).toThrow(BundleSchemaError);
    expect(() => verifyProofBundle(42)).toThrow(BundleSchemaError);
  });

  it('detects a tampered chain (event_hash mismatch)', () => {
    const builder = new ProofBundleBuilder({ chain_id: 't', producer_runtime: 'test' });
    builder.extend(buildGoodChain(3));
    const bundle = JSON.parse(JSON.stringify(builder.build())) as Record<string, unknown>;
    const events = bundle['events'] as Array<Record<string, unknown>>;
    const ev1 = events[1]!;
    const event = ev1['event'] as Record<string, unknown>;
    event['payload'] = { index: 999 };
    const result = verifyProofBundle(bundle);
    expect(result.ok).toBe(false);
    expect(result.chain_result.ok).toBe(false);
    expect(result.chain_result.first_bad_index).toBe(1);
  });

  it('flags bundle/walk disagreement', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'd', producer_runtime: 'test' });
    builder.extend(buildGoodChain(3));
    const bundle = JSON.parse(JSON.stringify(builder.build())) as Record<string, unknown>;
    const events = bundle['events'] as Array<Record<string, unknown>>;
    const ev1 = events[1]!;
    (ev1['event'] as Record<string, unknown>)['payload'] = { tampered: true };
    // Leave verification_report.ok at true (simulating post-build tampering).
    const result = verifyProofBundle(bundle);
    expect(result.ok).toBe(false);
    expect(result.bundle_reported_ok).toBe(true);
    expect(result.chain_result.ok).toBe(false);
    expect(result.agreement).toBe(false);
  });

  it('shortSummary formats ok and fail differently', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'my-id', producer_runtime: 'test' });
    builder.extend(buildGoodChain(2));
    const okResult = verifyProofBundle(builder.build());
    expect(shortSummary(okResult)).toMatch(/^OK/);
    expect(shortSummary(okResult)).toContain("'my-id'");

    const bundle = JSON.parse(JSON.stringify(builder.build())) as Record<string, unknown>;
    ((bundle['events'] as Array<Record<string, unknown>>)[1]!['event'] as Record<string, unknown>)[
      'payload'
    ] = { changed: true };
    const failResult = verifyProofBundle(bundle);
    expect(shortSummary(failResult)).toMatch(/^FAIL/);
  });
});

describe('verifyProofBundleFile', () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'attestplane-test-'));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it('round-trips a written bundle', async () => {
    const builder = new ProofBundleBuilder({ chain_id: 'f', producer_runtime: 'test' });
    builder.extend(buildGoodChain(2));
    const bundle = builder.build();
    const filePath = path.join(tmpDir, 'bundle.json');
    await fs.writeFile(filePath, JSON.stringify(bundle), 'utf-8');

    const result = await verifyProofBundleFile(filePath);
    expect(result.ok).toBe(true);
    expect(result.event_count).toBe(2);
  });

  it('rejects a missing file with BundleVerificationError', async () => {
    await expect(verifyProofBundleFile(path.join(tmpDir, 'nope.json'))).rejects.toThrow(
      BundleVerificationError,
    );
  });

  it('rejects malformed JSON with BundleSchemaError', async () => {
    const filePath = path.join(tmpDir, 'bad.json');
    await fs.writeFile(filePath, 'not valid json', 'utf-8');
    await expect(verifyProofBundleFile(filePath)).rejects.toThrow(BundleSchemaError);
  });
});

describe('buildAuditorExport', () => {
  it('produces a minimal export', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'ax', producer_runtime: 'test' });
    builder.extend(buildGoodChain(3));
    const bundle = builder.build();
    const exp = buildAuditorExport(bundle);
    expect(exp.export_version).toBe(1);
    expect(exp.chain_summary.event_count).toBe(3);
    expect(exp.verification_status.ok).toBe(true);
    expect(exp.redaction_policy.redaction_status).toBe('enforced_by_producer');
  });

  it('emits event_type_histogram', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'hist', producer_runtime: 'test' });
    builder.extend(buildGoodChain(4));
    const bundle = builder.build();
    const exp = buildAuditorExport(bundle);
    expect(exp.chain_summary.event_type_histogram['eval_event']).toBe(2);
    expect(exp.chain_summary.event_type_histogram['policy_check_event']).toBe(2);
  });

  it('reports anchor_status=unanchored in v1', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'a', producer_runtime: 'test' });
    const exp = buildAuditorExport(builder.build());
    expect(exp.chain_summary.anchor_status).toBe('unanchored');
  });

  it('includes the default legal disclaimer', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'd', producer_runtime: 'test' });
    const exp = buildAuditorExport(builder.build());
    expect(exp.legal_disclaimer).toContain('compliance opinion');
  });

  it('respects redaction_status override', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'r', producer_runtime: 'test' });
    const exp = buildAuditorExport(builder.build(), { redaction_status: 'enforced_by_adapter' });
    expect(exp.redaction_policy.redaction_status).toBe('enforced_by_adapter');
  });

  it('uses the bundle verified_at as time-range sentinel for empty chains', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'e', producer_runtime: 'test' });
    const bundle = builder.build();
    const exp = buildAuditorExport(bundle);
    expect(exp.chain_summary.time_range.earliest).toBe(bundle.verification_report.verified_at);
    expect(exp.chain_summary.time_range.latest).toBe(bundle.verification_report.verified_at);
  });
});
