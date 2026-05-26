// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Local selector for `npm test -- cli-json-contract`.
 *
 * This pins the checked-in `verify --json` snapshot fixtures so the package
 * test selector has a stable target even though the CLI runtime itself lives in
 * the Python implementation.
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

interface VerifyJsonPayload {
  bundle: {
    digest: string;
    schema_version: number;
  };
  exit_code: number;
  reason_code: string | null;
  reasons: Array<{
    code: string;
    message: string;
    path: string;
  }>;
  result: 'pass' | 'fail';
  schema_version: number;
  taxonomy_version: number;
}

const __dirname = dirname(fileURLToPath(import.meta.url));
const SNAPSHOT_DIR = resolve(
  __dirname,
  '..',
  '..',
  '..',
  'tests',
  'conformance',
  'vectors',
  'verify_json',
  'v1',
);

function loadSnapshot(filename: string): VerifyJsonPayload {
  const payload = JSON.parse(readFileSync(resolve(SNAPSHOT_DIR, filename), 'utf-8')) as VerifyJsonPayload;
  expect(payload.schema_version).toBe(1);
  expect(payload.taxonomy_version).toBe(1);
  expect(payload.bundle.schema_version).toBe(1);
  return payload;
}

describe('cli-json-contract', () => {
  it('pins the pass snapshot and 0 exit code', () => {
    const payload = loadSnapshot('pass.json');

    expect(payload.exit_code).toBe(0);
    expect(payload.result).toBe('pass');
    expect(payload.reason_code).toBeNull();
    expect(payload.reasons).toEqual([]);
  });

  it('pins the fail snapshot and the stable verification failure exit code', () => {
    const payload = loadSnapshot('fail.json');

    expect(payload.exit_code).toBe(1);
    expect(payload.result).toBe('fail');
    expect(payload.reason_code).toBe('att.verify.canonical_mismatch');
    expect(payload.reasons).toEqual([
      {
        code: 'att.verify.canonical_mismatch',
        message: 'canonicalization failed',
        path: '/events/0/event/payload/artifact_ref',
      },
    ]);
  });
});
