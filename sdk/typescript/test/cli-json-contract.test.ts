// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Cross-SDK contract snapshot for `verify --json`.
 *
 * The Python CLI owns the runtime behavior in this checkout; this test keeps
 * the shared versioned fixture pinned from the TypeScript workspace so
 * `npm test -- cli-json-contract` fails if the contract snapshot drifts.
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CONTRACT_PATH = resolve(
  __dirname,
  '..',
  '..',
  'python',
  'tests',
  'conformance',
  'verify_json_contract_vectors.json',
);

interface VerifyJsonContractOutput {
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
  schema_version: 1;
  taxonomy_version: 1;
}

interface VerifyJsonContractCase {
  bundle_fixture: string;
  expected_exit_code: number;
  name: string;
  output: VerifyJsonContractOutput;
}

interface VerifyJsonContractFixture {
  comment: string;
  cases: VerifyJsonContractCase[];
  schema_version: 1;
}

const CONTRACT = JSON.parse(
  readFileSync(CONTRACT_PATH, 'utf-8'),
) as VerifyJsonContractFixture;

describe('verify --json contract snapshot', () => {
  it('pins the versioned fixture schema', () => {
    expect(CONTRACT.schema_version).toBe(1);
    expect(CONTRACT.comment).toContain('Issue #294');
    expect(CONTRACT.cases).toHaveLength(2);
  });

  it('pins the pass payload snapshot', () => {
    const passCase = CONTRACT.cases.find((entry) => entry.name === 'pass_minimal_fixture');
    expect(passCase).toBeDefined();
    expect(passCase?.bundle_fixture).toBe('../../../fixtures/positive/minimal.json');
    expect(passCase?.expected_exit_code).toBe(0);
    expect(passCase?.output).toEqual({
      bundle: {
        digest: 'd4d37025f7452ad2525d6b37c898bf08cd335db3e7983ce04e242e898b77b2cb',
        schema_version: 1,
      },
      exit_code: 0,
      reason_code: null,
      reasons: [],
      result: 'pass',
      schema_version: 1,
      taxonomy_version: 1,
    });
  });

  it('pins the failure payload snapshot', () => {
    const failCase = CONTRACT.cases.find(
      (entry) => entry.name === 'fail_canonicalization_edge_fixture',
    );
    expect(failCase).toBeDefined();
    expect(failCase?.bundle_fixture).toBe('../../../fixtures/reject/canonicalization-edge.json');
    expect(failCase?.expected_exit_code).toBe(1);
    expect(failCase?.output).toEqual({
      bundle: {
        digest: '914bdd3745f9566e4cf0c3c2dd2747b701f50ad4cb3dc0eeede5f16207748ffd',
        schema_version: 1,
      },
      exit_code: 1,
      reason_code: 'att.verify.canonical_mismatch',
      reasons: [
        {
          code: 'att.verify.canonical_mismatch',
          message: 'canonicalization failed',
          path: '/events/0/event/payload/artifact_ref',
        },
      ],
      result: 'fail',
      schema_version: 1,
      taxonomy_version: 1,
    });
  });
});
