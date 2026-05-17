// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Cross-language conformance tests for the replayer (ADR-0014 / P2.2).
 * Replays the substrate-shipped LangSmith + LangFuse fixtures against
 * the TS-side adapters and asserts byte equality.
 */

import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { AdapterConformanceError, replayFixture } from '../src/adapter_conformance.js';
import { LangFuseAdapter } from '../src/adapters/langfuse.js';
import { LangSmithAdapter } from '../src/adapters/langsmith.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = resolve(
  __dirname,
  '..',
  '..',
  'python',
  'tests',
  'fixtures',
  'adapter_conformance',
);

describe('replayFixture — ADR-0014 P2.2 reference fixtures', () => {
  it('langsmith_v1 fixture passes against TS LangSmithAdapter', () => {
    const adapter = new LangSmithAdapter();
    const report = replayFixture(resolve(FIXTURES_DIR, 'langsmith_v1.json'), {
      translate: (raw: unknown) =>
        adapter.translate(LangSmithAdapter.fromDict(raw as Record<string, unknown>)),
    });
    expect(report.ok).toBe(true);
    expect(report.runtime_kind).toBe('langsmith');
    expect(report.cases_total).toBe(2);
    expect(report.cases_passed).toBe(2);
    expect(report.cases_failed).toBe(0);
  });

  it('langfuse_v1 fixture passes against TS LangFuseAdapter', () => {
    const adapter = new LangFuseAdapter();
    const report = replayFixture(resolve(FIXTURES_DIR, 'langfuse_v1.json'), {
      translate: (raw: unknown) =>
        adapter.translate(LangFuseAdapter.fromDict(raw as Record<string, unknown>)),
    });
    expect(report.ok).toBe(true);
    expect(report.runtime_kind).toBe('langfuse');
    expect(report.cases_total).toBe(2);
  });
});

describe('replayFixture — error reporting', () => {
  let tmp: string;
  beforeAll(() => {
    tmp = mkdtempSync(join(tmpdir(), 'attestplane-replay-test-'));
  });
  afterAll(() => {
    rmSync(tmp, { recursive: true, force: true });
  });

  it('reports byte mismatch when expected_event_draft is wrong', () => {
    const badFixture = {
      $schema_version: 1,
      fixture_kind: 'adapter_conformance',
      runtime_kind: 'langsmith',
      fixture_version: 1,
      cases: [
        {
          name: 'intentional_mismatch',
          runtime_event_input: {
            id: '33333333-3333-7000-8000-000000000003',
            name: 'x',
            run_type: 'tool',
            start_time: '2026-05-17T12:00:00.000000+00:00',
          },
          expected_event_draft: {
            event_type: 'WRONG_TYPE',
            actor: 'WRONG',
            payload: {},
            subject_ref: null,
            session_id: null,
            reference_db_ref: null,
            matched_input_ref: null,
            human_verifier: null,
          },
        },
      ],
    };
    const p = join(tmp, 'bad.json');
    writeFileSync(p, JSON.stringify(badFixture));
    const adapter = new LangSmithAdapter();
    const report = replayFixture(p, {
      translate: (raw: unknown) =>
        adapter.translate(LangSmithAdapter.fromDict(raw as Record<string, unknown>)),
    });
    expect(report.ok).toBe(false);
    expect(report.cases_failed).toBe(1);
    expect(report.results[0]?.reason).toMatch(/canonical-bytes mismatch/);
  });

  it('reports adapter raise as case failure (not throwing)', () => {
    const fixture = {
      $schema_version: 1,
      fixture_kind: 'adapter_conformance',
      runtime_kind: 'langsmith',
      fixture_version: 1,
      cases: [
        {
          name: 'malformed_input',
          runtime_event_input: {},
          expected_event_draft: {
            event_type: 'tool_call_event',
            actor: 'x',
            payload: {},
            subject_ref: null,
            session_id: null,
            reference_db_ref: null,
            matched_input_ref: null,
            human_verifier: null,
          },
        },
      ],
    };
    const p = join(tmp, 'raise.json');
    writeFileSync(p, JSON.stringify(fixture));
    const adapter = new LangSmithAdapter();
    const report = replayFixture(p, {
      translate: (raw: unknown) =>
        adapter.translate(LangSmithAdapter.fromDict(raw as Record<string, unknown>)),
    });
    expect(report.ok).toBe(false);
    expect(report.results[0]?.reason).toMatch(/adapter raised/);
  });

  it('rejects malformed fixture shape immediately', () => {
    const p = join(tmp, 'malformed.json');
    writeFileSync(p, '{"not_a_fixture": true}');
    const adapter = new LangSmithAdapter();
    expect(() =>
      replayFixture(p, {
        translate: (raw: unknown) =>
          adapter.translate(LangSmithAdapter.fromDict(raw as Record<string, unknown>)),
      }),
    ).toThrow(AdapterConformanceError);
  });

  it('rejects duplicate case names', () => {
    const fixture = {
      $schema_version: 1,
      fixture_kind: 'adapter_conformance',
      runtime_kind: 'langsmith',
      fixture_version: 1,
      cases: [
        { name: 'dup', runtime_event_input: {}, expected_event_draft: {} },
        { name: 'dup', runtime_event_input: {}, expected_event_draft: {} },
      ],
    };
    const p = join(tmp, 'dup.json');
    writeFileSync(p, JSON.stringify(fixture));
    expect(() =>
      replayFixture(p, {
        translate: (raw: unknown) =>
          new LangSmithAdapter().translate(
            LangSmithAdapter.fromDict(raw as Record<string, unknown>),
          ),
      }),
    ).toThrow(/duplicate/);
  });

  it('replayer is pure (same fixture+adapter → same report)', () => {
    const path = resolve(FIXTURES_DIR, 'langsmith_v1.json');
    const r1 = replayFixture(path, {
      translate: (raw: unknown) =>
        new LangSmithAdapter().translate(LangSmithAdapter.fromDict(raw as Record<string, unknown>)),
    });
    const r2 = replayFixture(path, {
      translate: (raw: unknown) =>
        new LangSmithAdapter().translate(LangSmithAdapter.fromDict(raw as Record<string, unknown>)),
    });
    expect(r1).toEqual(r2);
  });
});
