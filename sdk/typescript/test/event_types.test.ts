// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Mirror of sdk/python/tests/test_event_types.py — locks the v1 taxonomy
 * at the constant-string level. Any rename of a constant or change in set
 * cardinality is a wire-format change and requires a taxonomy v2 ADR.
 */

import { describe, expect, it } from 'vitest';

import * as eventTypes from '../src/event_types.js';
import * as pkg from '../src/index.js';

const EXPECTED_V1_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['BUDGET_EVENT', 'budget_event'],
  ['EVAL_EVENT', 'eval_event'],
  ['GATEWAY_DECISION_EVENT', 'gateway_decision_event'],
  ['HUMAN_APPROVAL_EVENT', 'human_approval_event'],
  ['LEASE_LIFECYCLE_EVENT', 'lease_lifecycle_event'],
  ['POLICY_CHECK_EVENT', 'policy_check_event'],
  ['ROUTING_EVENT', 'routing_event'],
  ['RUNTIME_LIFECYCLE_EVENT', 'runtime_lifecycle_event'],
  ['SETTLEMENT_EVENT', 'settlement_event'],
  ['STATE_TRANSITION_EVENT', 'state_transition_event'],
  ['TOOL_CALL_EVENT', 'tool_call_event'],
  ['WORKER_ASSIGNMENT_EVENT', 'worker_assignment_event'],
];

describe('event taxonomy v1', () => {
  it('taxonomy version is 1', () => {
    expect(eventTypes.EVIDENCE_TAXONOMY_VERSION).toBe(1);
  });

  for (const [name, value] of EXPECTED_V1_PAIRS) {
    it(`${name} equals "${value}"`, () => {
      expect((eventTypes as Record<string, unknown>)[name]).toBe(value);
    });
  }

  it('set cardinality is 12', () => {
    expect(eventTypes.ALL_EVENT_TYPES_V1.size).toBe(12);
  });

  it('set contains exactly the expected strings', () => {
    const expectedValues = new Set(EXPECTED_V1_PAIRS.map(([, v]) => v));
    expect(new Set(eventTypes.ALL_EVENT_TYPES_V1)).toEqual(expectedValues);
  });

  it('isKnownV1EventType returns true for each v1 string', () => {
    for (const [, value] of EXPECTED_V1_PAIRS) {
      expect(eventTypes.isKnownV1EventType(value)).toBe(true);
    }
  });

  it('isKnownV1EventType returns false for unknown / unrelated strings', () => {
    for (const unknown of [
      '',
      'unknown_event',
      'TOOL_CALL_EVENT',
      'tool_call',
      'future_taxonomy_event_v2',
      'evid',
    ]) {
      expect(eventTypes.isKnownV1EventType(unknown)).toBe(false);
    }
  });

  it('constants are re-exported from the package root', () => {
    for (const [name, value] of EXPECTED_V1_PAIRS) {
      expect((pkg as Record<string, unknown>)[name]).toBe(value);
    }
    expect((pkg as Record<string, unknown>).EVIDENCE_TAXONOMY_VERSION).toBe(1);
    expect(
      (pkg as Record<string, unknown>).isKnownV1EventType === eventTypes.isKnownV1EventType,
    ).toBe(true);
  });
});
