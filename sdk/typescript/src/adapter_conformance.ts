// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Adapter-conformance fixture replayer (ADR-0014 P2.2).
 *
 * TypeScript mirror of `attestplane.adapter_conformance` (Python).
 * Loads a fixture file, calls `adapter.translate()` per case, asserts
 * canonical-bytes equality against `expected_event_draft`. Pure — no
 * I/O beyond the fixture file read.
 */

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

import { canonicalize } from './canonical.js';
import type { EventDraft, SubjectRef } from './types.js';

export interface AdapterCaseResult {
  readonly case_name: string;
  readonly ok: boolean;
  readonly reason: string | null;
  readonly expected_canonical_hash: string | null;
  readonly actual_canonical_hash: string | null;
}

export interface AdapterConformanceReport {
  readonly fixture_path: string;
  readonly runtime_kind: string;
  readonly fixture_version: number;
  readonly cases_total: number;
  readonly cases_passed: number;
  readonly cases_failed: number;
  readonly results: readonly AdapterCaseResult[];
  readonly ok: boolean;
}

export class AdapterConformanceError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AdapterConformanceError';
  }
}

function subjectRefToDict(ref: SubjectRef | null | undefined): {
  scheme: string;
  value: string;
} | null {
  if (ref === null || ref === undefined) return null;
  return { scheme: ref.scheme, value: ref.value };
}

function eventDraftToDict(draft: EventDraft): Record<string, unknown> {
  return {
    event_type: draft.event_type,
    actor: draft.actor,
    payload: draft.payload,
    subject_ref: subjectRefToDict(draft.subject_ref),
    session_id: draft.session_id,
    reference_db_ref: draft.reference_db_ref,
    matched_input_ref: draft.matched_input_ref,
    human_verifier: subjectRefToDict(draft.human_verifier),
  };
}

function canonicalBytesHash(d: unknown): string {
  return createHash('sha256').update(canonicalize(d)).digest('hex');
}

interface FixtureCase {
  name: string;
  runtime_event_input: Record<string, unknown>;
  expected_event_draft: Record<string, unknown>;
}

interface FixtureFile {
  $schema_version: number;
  fixture_kind: string;
  runtime_kind: string;
  fixture_version: number;
  description?: string;
  cases: FixtureCase[];
}

function loadAndValidateFixture(fixturePath: string): FixtureFile {
  let raw: unknown;
  try {
    raw = JSON.parse(readFileSync(fixturePath, 'utf-8'));
  } catch (exc) {
    throw new AdapterConformanceError(
      `cannot load fixture ${fixturePath}: ${(exc as Error).message}`,
    );
  }
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new AdapterConformanceError(
      `fixture ${fixturePath}: top level must be object, got ${
        Array.isArray(raw) ? 'array' : raw === null ? 'null' : typeof raw
      }`,
    );
  }
  const obj = raw as Record<string, unknown>;
  if (obj.$schema_version !== 1) {
    throw new AdapterConformanceError(
      `fixture ${fixturePath}: $schema_version must be 1, got ${JSON.stringify(obj.$schema_version)}`,
    );
  }
  if (obj.fixture_kind !== 'adapter_conformance') {
    throw new AdapterConformanceError(
      `fixture ${fixturePath}: fixture_kind must be 'adapter_conformance', got ${JSON.stringify(obj.fixture_kind)}`,
    );
  }
  if (typeof obj.runtime_kind !== 'string' || obj.runtime_kind.length === 0) {
    throw new AdapterConformanceError(
      `fixture ${fixturePath}: runtime_kind must be non-empty string`,
    );
  }
  if (
    typeof obj.fixture_version !== 'number' ||
    !Number.isInteger(obj.fixture_version) ||
    obj.fixture_version < 1
  ) {
    throw new AdapterConformanceError(
      `fixture ${fixturePath}: fixture_version must be integer >= 1`,
    );
  }
  if (!Array.isArray(obj.cases) || obj.cases.length === 0) {
    throw new AdapterConformanceError(`fixture ${fixturePath}: cases must be non-empty array`);
  }
  const seenNames = new Set<string>();
  for (let i = 0; i < obj.cases.length; i++) {
    const c = obj.cases[i];
    if (c === null || typeof c !== 'object' || Array.isArray(c)) {
      throw new AdapterConformanceError(`fixture ${fixturePath}: cases[${i}] must be object`);
    }
    const co = c as Record<string, unknown>;
    if (typeof co.name !== 'string' || co.name.length === 0) {
      throw new AdapterConformanceError(
        `fixture ${fixturePath}: cases[${i}].name must be non-empty string`,
      );
    }
    if (seenNames.has(co.name)) {
      throw new AdapterConformanceError(
        `fixture ${fixturePath}: duplicate case name ${JSON.stringify(co.name)}`,
      );
    }
    seenNames.add(co.name);
    if (!('runtime_event_input' in co)) {
      throw new AdapterConformanceError(
        `fixture ${fixturePath}: cases[${i}] missing runtime_event_input`,
      );
    }
    if (!('expected_event_draft' in co)) {
      throw new AdapterConformanceError(
        `fixture ${fixturePath}: cases[${i}] missing expected_event_draft`,
      );
    }
    if (
      co.expected_event_draft === null ||
      typeof co.expected_event_draft !== 'object' ||
      Array.isArray(co.expected_event_draft)
    ) {
      throw new AdapterConformanceError(
        `fixture ${fixturePath}: cases[${i}].expected_event_draft must be object`,
      );
    }
  }
  return obj as unknown as FixtureFile;
}

export interface ReplayOptions {
  /** Optional callback to convert raw `runtime_event_input` into the
   *  runtime-event type the adapter's `translate()` expects. */
  readonly pre_translate?: (raw: Record<string, unknown>) => unknown;
}

/** An adapter-shaped object: has a `translate()` method returning an `EventDraft`. */
export interface TranslateAdapter<RE = unknown> {
  translate(runtimeEvent: RE): EventDraft;
}

/**
 * Replay every case in `fixturePath` against `adapter.translate()`.
 *
 * `report.ok` is true iff every case's adapter output matches its
 * `expected_event_draft` byte-equal under canonical-JSON.
 */
export function replayFixture(
  fixturePath: string,
  adapter: TranslateAdapter,
  options: ReplayOptions = {},
): AdapterConformanceReport {
  const fixture = loadAndValidateFixture(fixturePath);
  const results: AdapterCaseResult[] = [];
  let passed = 0;
  let failed = 0;

  for (const c of fixture.cases) {
    const expectedHash = canonicalBytesHash(c.expected_event_draft);
    try {
      const runtimeEvent =
        options.pre_translate !== undefined
          ? options.pre_translate(c.runtime_event_input)
          : c.runtime_event_input;
      const actualDraft = adapter.translate(runtimeEvent);
      const actual = eventDraftToDict(actualDraft);
      const actualHash = canonicalBytesHash(actual);
      if (actualHash === expectedHash) {
        results.push({
          case_name: c.name,
          ok: true,
          reason: null,
          expected_canonical_hash: expectedHash,
          actual_canonical_hash: actualHash,
        });
        passed++;
      } else {
        results.push({
          case_name: c.name,
          ok: false,
          reason: `canonical-bytes mismatch (expected hash ${expectedHash}, got ${actualHash})`,
          expected_canonical_hash: expectedHash,
          actual_canonical_hash: actualHash,
        });
        failed++;
      }
    } catch (exc) {
      results.push({
        case_name: c.name,
        ok: false,
        reason: `adapter raised: ${(exc as Error).name}: ${(exc as Error).message}`,
        expected_canonical_hash: expectedHash,
        actual_canonical_hash: null,
      });
      failed++;
    }
  }

  return {
    fixture_path: fixturePath,
    runtime_kind: fixture.runtime_kind,
    fixture_version: fixture.fixture_version,
    cases_total: fixture.cases.length,
    cases_passed: passed,
    cases_failed: failed,
    results,
    ok: failed === 0,
  };
}
