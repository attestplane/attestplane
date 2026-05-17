// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Evidence event type constants — v1 taxonomy.
 *
 * These twelve strings are the canonical `event_type` identifiers for the
 * v1 evidence taxonomy locked by ADR-0008 and specified in
 * `docs/spec/evidence-event-taxonomy-v1.md`.
 *
 * Adapters MUST import these constants rather than embedding string
 * literals. `ALL_EVENT_TYPES_V1` is a frozen Set exported for runtime
 * "is this a known v1 type?" checks performed by exporters, verifiers,
 * and the obligation registry — NOT by the substrate's canonicalization
 * or hash-chain layers, which deliberately stay taxonomy-agnostic per
 * ADR-0008 § Decision ("Substrate stays neutral").
 *
 * The taxonomy version is tracked separately from the chain schema
 * version and the anchor schema version:
 *
 *   EVIDENCE_TAXONOMY_VERSION   // this file, value 1 in v1
 *   SCHEMA_VERSION              // hashchain.ts, value 1 from ADR-0002
 *   anchor_schema_version       // ADR-0003, value 1 in v0.1
 */

export const EVIDENCE_TAXONOMY_VERSION = 1 as const;

export const TOOL_CALL_EVENT = 'tool_call_event' as const;
export const POLICY_CHECK_EVENT = 'policy_check_event' as const;
export const HUMAN_APPROVAL_EVENT = 'human_approval_event' as const;
export const LEASE_LIFECYCLE_EVENT = 'lease_lifecycle_event' as const;
export const BUDGET_EVENT = 'budget_event' as const;
export const SETTLEMENT_EVENT = 'settlement_event' as const;
export const WORKER_ASSIGNMENT_EVENT = 'worker_assignment_event' as const;
export const RUNTIME_LIFECYCLE_EVENT = 'runtime_lifecycle_event' as const;
export const GATEWAY_DECISION_EVENT = 'gateway_decision_event' as const;
export const STATE_TRANSITION_EVENT = 'state_transition_event' as const;
export const EVAL_EVENT = 'eval_event' as const;
export const ROUTING_EVENT = 'routing_event' as const;

export type EventTypeV1 =
  | typeof TOOL_CALL_EVENT
  | typeof POLICY_CHECK_EVENT
  | typeof HUMAN_APPROVAL_EVENT
  | typeof LEASE_LIFECYCLE_EVENT
  | typeof BUDGET_EVENT
  | typeof SETTLEMENT_EVENT
  | typeof WORKER_ASSIGNMENT_EVENT
  | typeof RUNTIME_LIFECYCLE_EVENT
  | typeof GATEWAY_DECISION_EVENT
  | typeof STATE_TRANSITION_EVENT
  | typeof EVAL_EVENT
  | typeof ROUTING_EVENT;

export const ALL_EVENT_TYPES_V1: ReadonlySet<EventTypeV1> = new Set<EventTypeV1>([
  TOOL_CALL_EVENT,
  POLICY_CHECK_EVENT,
  HUMAN_APPROVAL_EVENT,
  LEASE_LIFECYCLE_EVENT,
  BUDGET_EVENT,
  SETTLEMENT_EVENT,
  WORKER_ASSIGNMENT_EVENT,
  RUNTIME_LIFECYCLE_EVENT,
  GATEWAY_DECISION_EVENT,
  STATE_TRANSITION_EVENT,
  EVAL_EVENT,
  ROUTING_EVENT,
]);

/**
 * Return `true` if `event_type` is one of the twelve v1 strings.
 *
 * Verifiers and exporters use this to distinguish "known v1 event" from
 * "future-taxonomy / unknown event". The latter is not an error — v1
 * verifiers are required to tolerate unknown event types per ADR-0008
 * § Decision ("Substrate stays neutral") to remain forward-compatible
 * with future taxonomy versions.
 */
export function isKnownV1EventType(event_type: string): event_type is EventTypeV1 {
  return (ALL_EVENT_TYPES_V1 as ReadonlySet<string>).has(event_type);
}
