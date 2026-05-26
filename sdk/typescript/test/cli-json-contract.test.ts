// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0

/**
 * Contract gate for `attestplane verify --json`.
 *
 * This test exercises the frozen Python CLI contract fixture from the
 * TypeScript package test runner so `npm test -- cli-json-contract` can
 * detect unannounced shape or exit-code drift.
 */

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

interface ContractCase {
  case_id: string;
  bundle_fixture: string;
  expected_exit_code: number;
  expected_stderr: string;
  expected_stdout: Record<string, unknown>;
}

interface ContractFixture {
  fixture_version: number;
  cases: ContractCase[];
}

const FIXTURE_PATH = resolve(
  process.cwd(),
  '..',
  'python',
  'tests',
  'conformance',
  'verify_json_contract_v1.json',
);
const PYTHON_CONFORMANCE_DIR = resolve(process.cwd(), '..', 'python', 'tests', 'conformance');
const PYTHON_PROJECT_DIR = resolve(process.cwd(), '..', 'python');

function loadFixture(): ContractFixture {
  return JSON.parse(readFileSync(FIXTURE_PATH, 'utf-8')) as ContractFixture;
}

function runVerify(bundleFixture: string): { rc: number; stdout: string; stderr: string } {
  const python = process.env.PYTHON ?? 'python3';
  try {
    const stdout = execFileSync(
      python,
      ['-m', 'attestplane.cli', 'verify', '--json', bundleFixture],
      {
        cwd: PYTHON_PROJECT_DIR,
        env: {
          ...process.env,
          PYTHONPATH: resolve(process.cwd(), '..', 'python', 'src'),
        },
        encoding: 'utf-8',
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    );
    return { rc: 0, stdout, stderr: '' };
  } catch (error) {
    const err = error as { status?: number; stdout?: string; stderr?: string };
    return {
      rc: err.status ?? 1,
      stdout: err.stdout ?? '',
      stderr: err.stderr ?? '',
    };
  }
}

describe('cli-json-contract', () => {
  it('pins the versioned verify --json fixture', () => {
    const fixture = loadFixture();
    expect(fixture.fixture_version).toBe(1);

    for (const testCase of fixture.cases) {
      const bundleFixture = resolve(PYTHON_CONFORMANCE_DIR, testCase.bundle_fixture);
      const result = runVerify(bundleFixture);

      expect(result.rc).toBe(testCase.expected_exit_code);
      expect(result.stderr).toBe(testCase.expected_stderr);
      expect(JSON.parse(result.stdout)).toEqual(testCase.expected_stdout);
    }
  });
});
