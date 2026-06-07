// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Public package import smoke tests. These exercise the root export surface
 * used by README examples without implying production or compliance readiness.
 */

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import {
  AttestSubstrate,
  ProofBundleBuilder,
  SUPPORTED_SCHEMA_VERSIONS,
  VERSION,
  canonicalize,
  makeEventDraft,
  makeSubjectRef,
  verifyProofBundle,
} from '../src/index.js';

describe('version single source of truth', () => {
  it('VERSION equals package.json version (no hand-maintained literal)', () => {
    // VERSION must derive from the package manifest so it cannot drift from the
    // published tarball. A previously hardcoded literal silently shipped a stale
    // "1.8.4" inside the 1.9.x/1.10.0 releases; this asserts the invariant.
    const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')) as {
      version: string;
    };
    expect(VERSION).toBe(pkg.version);
    expect(VERSION).not.toBe('0.0.0+unknown');
  });
});

describe('root package export surface', () => {
  it('exports README quickstart symbols', () => {
    const sub = new AttestSubstrate();
    const chained = sub.append(
      makeEventDraft({
        event_type: 'ai_decision',
        actor: 'agent://smoke/v1',
        payload: { outcome: 'approved', confidence_bp: 9120 },
        subject_ref: makeSubjectRef('sha256_salted', '2c1b'),
      }),
      { now: new Date('2026-05-17T12:00:00.000Z') },
    );

    expect(chained.event_hash).toHaveLength(32);
    expect(sub.verify().ok).toBe(true);
  });

  it('exports proof bundle predicates without upgrading CLI verification claims', () => {
    const sub = new AttestSubstrate();
    sub.append(makeEventDraft({ event_type: 'eval_event', actor: 'agent://smoke/v1' }), {
      now: new Date('2026-05-17T12:00:00.000Z'),
      event_id: '00000000-0000-7000-8000-000000000001',
    });
    const builder = new ProofBundleBuilder({
      chain_id: 'smoke',
      producer_runtime: `typescript-sdk-${VERSION}`,
    });
    builder.extend(sub.snapshot());

    const result = verifyProofBundle(builder.build());
    expect(result.ok).toBe(true);
    expect(typeof canonicalize).toBe('function');
    expect(SUPPORTED_SCHEMA_VERSIONS).toEqual([1]);
  });
});
