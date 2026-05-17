// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Abstract runtime-adapter base — the only adapter surface in the substrate.
 *
 * Per ADR-0004 § 1 ("Universal rule"):
 *
 *   Any AIOS surface whose primary semantic is authority or execution stays
 *   in AIOS. Attestplane only ever records the event of a decision having
 *   been made, never owns the decision.
 *
 * A `GenericRuntimeAdapter` translates one runtime-specific event into one
 * `EventDraft`. That is the only verb it owns. The abstract class
 * deliberately exposes no `execute()`, `grant()`, or `decide()` method.
 *
 * Concrete adapters (AIOS, LangGraph, Claude Code SDK, …) live in their
 * respective execution-plane repositories or in `attestplane-contrib`, not
 * in the substrate OSS tree.
 *
 * Spec-Only Phase 0 deliverable (migration plan ticket #3).
 */

import type { EventDraft } from './types.js';

/** Base class for any adapter-raised error. */
export class AdapterError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AdapterError';
  }
}

/**
 * A runtime event could not be translated into an `EventDraft`.
 *
 * Adapters MUST throw this (or a subclass) rather than returning a
 * partially-populated draft or silently dropping the event. Silent drops
 * would defeat the point of a substrate.
 */
export class AdapterTranslationError extends AdapterError {
  constructor(message: string) {
    super(message);
    this.name = 'AdapterTranslationError';
  }
}

const FORBIDDEN_METHOD_NAMES: ReadonlySet<string> = new Set([
  'execute',
  'run',
  'dispatch',
  'grant',
  'revoke',
  'issue',
  'decide',
  'approve',
  'reject',
  'settle',
  'charge',
  'credit',
  'schedule',
  'allocate',
]);

/**
 * Abstract base for any execution-plane → Attestplane adapter.
 *
 * The contract is intentionally narrow:
 *
 * 1. `translate()` is the only required method.
 * 2. `translate()` is a **pure function**: given the same input it returns
 *    the same output. No I/O, no side effects, no clock reads, no random
 *    number generation, no calls back into the runtime.
 * 3. The returned `EventDraft` is the caller-provided portion of the audit
 *    event. The substrate assigns `event_id`, `timestamp`, `seq`,
 *    `prev_hash`, and `event_hash`. Adapters do not produce those fields.
 * 4. Adapters do not execute, grant, decide, or otherwise affect runtime
 *    state. The base class enforces this via a runtime check in the
 *    constructor that rejects forbidden method names at instantiation
 *    time. (TypeScript does not have a Python-style `__init_subclass__`
 *    hook, so the check runs at `new` time rather than class-creation
 *    time.)
 *
 * Reserved method names that any subclass MUST NOT define at the public
 * level (any leading underscore exempts the name):
 *
 * - `execute`, `run`, `dispatch`
 * - `grant`, `revoke`, `issue`
 * - `decide`, `approve`, `reject`
 * - `settle`, `charge`, `credit`
 * - `schedule`, `allocate`
 *
 * Defining any of these is an ADR-0004 boundary violation and the
 * constructor throws on first instantiation.
 */
export abstract class GenericRuntimeAdapter<RuntimeEvent> {
  abstract readonly runtime_name: string;
  abstract readonly schema_version: number;

  constructor() {
    const proto = Object.getPrototypeOf(this) as object;
    const offenders: string[] = [];
    for (const name of Object.getOwnPropertyNames(proto)) {
      if (name === 'constructor') continue;
      if (name.startsWith('_')) continue;
      if (FORBIDDEN_METHOD_NAMES.has(name)) {
        offenders.push(name);
      }
    }
    if (offenders.length > 0) {
      offenders.sort();
      throw new TypeError(
        `${this.constructor.name} defines forbidden authority/execution method(s) ` +
          `[${offenders.join(', ')}]; adapters may only translate events. See ADR-0004 § 1.`,
      );
    }
  }

  /**
   * Translate one runtime-specific event into one `EventDraft`.
   *
   * Implementations MUST:
   *
   * - Throw `AdapterTranslationError` on any input the adapter cannot map.
   *   Never return `null` or a partially-populated draft.
   * - Be pure: same input → same output, no I/O, no clock reads.
   * - Apply pseudonymization at the boundary: any direct identifier in
   *   `runtime_event` that maps to a data subject MUST be wrapped in a
   *   `SubjectRef` with an appropriate `scheme` before being placed in the
   *   returned draft. Raw PII in `payload` is a GDPR Art. 4(5) violation.
   * - Not call into the runtime to fetch additional context. If the
   *   runtime event lacks information the adapter needs, the runtime must
   *   emit a richer event — not the adapter.
   */
  abstract translate(runtime_event: RuntimeEvent): EventDraft;
}
