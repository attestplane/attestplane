// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { verifyProofBundleFile } from '../../src/verifier.js';

const REPO_ROOT = join(process.cwd(), '..', '..');
const BUNDLE_FIXTURE = join(
  REPO_ROOT,
  'tests',
  'fixtures',
  'bundles',
  'valid_signed_attestation.json',
);
const VERIFY_RESULT_SCHEMA = JSON.parse(
  readFileSync(join(REPO_ROOT, 'schemas', 'cli', 'verify-result-v1.json'), 'utf-8'),
) as {
  readonly properties: {
    readonly taxonomy_version: {
      readonly const: number;
    };
  };
};

describe('sdk/verify', () => {
  it('exposes taxonomy_version on verify results and matches the CLI contract', async () => {
    const result = await verifyProofBundleFile(BUNDLE_FIXTURE);
    const cliTaxonomyVersion = VERIFY_RESULT_SCHEMA.properties.taxonomy_version.const;

    expect(Object.prototype.hasOwnProperty.call(result, 'taxonomy_version')).toBe(true);
    expect(result.ok).toBe(true);
    expect(result.taxonomy_version).toBe(cliTaxonomyVersion);
    expect(cliTaxonomyVersion).toBe(1);
  });
});
