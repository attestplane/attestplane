// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Focused parity coverage for the stable verifier taxonomy version.
 */

import { describe, expect, it } from 'vitest';

import { ProofBundleBuilder } from '../src/proof_bundle.js';
import { verifyProofBundle } from '../src/verifier.js';

describe('taxonomy_version parity', () => {
  it('surfaces the stable taxonomy version on verifier results', () => {
    const builder = new ProofBundleBuilder({ chain_id: 'taxonomy', producer_runtime: 'test' });
    const result = verifyProofBundle(builder.build());

    expect(result.ok).toBe(true);
    expect(result.taxonomy_version).toBe(1);
  });
});
