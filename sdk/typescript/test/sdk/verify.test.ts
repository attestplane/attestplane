// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, delimiter, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { verifyProofBundle } from '../../src/verifier.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..', '..', '..', '..');
const FIXTURE = resolve(ROOT, 'tests', 'fixtures', 'bundles', 'valid_signed_attestation.json');
const PYTHON_SRC = resolve(ROOT, 'sdk', 'python', 'src');

function cliVerifyJson(bundlePath: string): { readonly taxonomy_version: number | null } {
  const env = {
    ...process.env,
    PYTHONPATH: process.env.PYTHONPATH
      ? `${PYTHON_SRC}${delimiter}${process.env.PYTHONPATH}`
      : PYTHON_SRC,
  };
  const stdout = execFileSync(
    'python',
    [
      '-c',
      'from attestplane.cli.main import main; import sys; sys.exit(main(["verify", "--json", sys.argv[1]]))',
      bundlePath,
    ],
    {
      cwd: ROOT,
      env,
      encoding: 'utf-8',
    },
  );
  return JSON.parse(stdout) as { readonly taxonomy_version: number | null };
}

function writeLegacyBundleFixture(): {
  readonly bundlePath: string;
  readonly bundle: Record<string, unknown>;
} {
  const bundle = JSON.parse(readFileSync(FIXTURE, 'utf-8')) as Record<string, unknown>;
  const chainMetadata = bundle.chain_metadata as Record<string, unknown>;
  delete chainMetadata.evidence_taxonomy_version;

  const tmpDir = mkdtempSync(resolve(tmpdir(), 'attestplane-taxonomy-'));
  const bundlePath = resolve(tmpDir, 'legacy-bundle.json');
  writeFileSync(bundlePath, `${JSON.stringify(bundle, null, 2)}\n`, 'utf-8');
  return { bundlePath, bundle };
}

describe('verifyProofBundle taxonomy version', () => {
  it('matches the CLI --json taxonomy_version for the same bundle', () => {
    const bundle = JSON.parse(readFileSync(FIXTURE, 'utf-8')) as Record<string, unknown>;

    const sdkResult = verifyProofBundle(bundle);
    const cliResult = cliVerifyJson(FIXTURE);

    expect(sdkResult.ok).toBe(true);
    expect(sdkResult.taxonomy_version).toBe(cliResult.taxonomy_version);
    expect(sdkResult.taxonomy_version).toBe(1);
  });

  it('surfaces null for legacy bundles that omit the declared taxonomy version', () => {
    const { bundle, bundlePath } = writeLegacyBundleFixture();

    const sdkResult = verifyProofBundle(bundle);
    const cliResult = cliVerifyJson(bundlePath);

    expect(sdkResult.ok).toBe(true);
    expect(sdkResult.taxonomy_version).toBeNull();
    expect(cliResult.taxonomy_version).toBeNull();
  });
});
