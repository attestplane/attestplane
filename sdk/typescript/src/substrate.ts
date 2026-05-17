// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * `AttestSubstrate` — append-only audit-event container.
 *
 * Mirrors `sdk/python/src/attestplane/substrate.py`. Single-threaded by
 * Node's event-loop model; no explicit locking is needed for in-process
 * use. Durable storage and multi-process coordination are out of scope at
 * v0.0.1 (anticipated ADR-0004).
 */

import {
  type VerificationResult,
  chainExtend,
  genesisHead,
  headOf,
  verifyChain,
} from './hashchain.js';
import type { ChainHead, ChainedEvent, EventDraft } from './types.js';

export interface AppendOptions {
  readonly now?: Date;
}

export class AttestSubstrate {
  #events: ChainedEvent[] = [];
  #tip: ChainHead = genesisHead();

  append(draft: EventDraft, options: AppendOptions = {}): ChainedEvent {
    const now = options.now ?? new Date();
    const chained = chainExtend(this.#tip, draft, { now });
    this.#events.push(chained);
    this.#tip = { seq: chained.seq, event_hash: chained.event_hash };
    return chained;
  }

  tip(): ChainHead {
    return this.#tip;
  }

  verify(): VerificationResult {
    return verifyChain(this.#events);
  }

  get length(): number {
    return this.#events.length;
  }

  snapshot(): ChainedEvent[] {
    return [...this.#events];
  }

  *[Symbol.iterator](): IterableIterator<ChainedEvent> {
    yield* this.#events;
  }

  static fromEvents(events: readonly ChainedEvent[]): AttestSubstrate {
    const result = verifyChain(events);
    if (!result.ok) {
      throw new Error(`cannot rehydrate substrate: ${result.reason ?? 'unknown'}`);
    }
    const instance = new AttestSubstrate();
    instance.#events = [...events];
    instance.#tip = headOf(events);
    return instance;
  }
}
