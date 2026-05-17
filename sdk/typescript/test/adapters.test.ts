// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Tests for `src/adapters.ts`. Mirror of
 * `sdk/python/tests/adapters/test_base.py` so the contract behaves
 * identically across languages.
 */

import { describe, expect, it } from 'vitest';

import { AdapterError, AdapterTranslationError, GenericRuntimeAdapter } from '../src/adapters.js';
import { type EventDraft, makeEventDraft, makeSubjectRef } from '../src/types.js';

interface MockRuntimeEvent {
  readonly kind: string;
  readonly actor_id: string;
  readonly user_id_hashed: string;
}

class MockAdapter extends GenericRuntimeAdapter<MockRuntimeEvent> {
  readonly runtime_name = 'mock';
  readonly schema_version = 1;

  translate(runtime_event: MockRuntimeEvent): EventDraft {
    if (typeof runtime_event !== 'object' || runtime_event === null) {
      throw new AdapterTranslationError(
        `expected MockRuntimeEvent object, got ${typeof runtime_event}`,
      );
    }
    return makeEventDraft({
      event_type: `mock.${runtime_event.kind}`,
      actor: runtime_event.actor_id,
      subject_ref: makeSubjectRef('sha256_salted', runtime_event.user_id_hashed),
      payload: { kind: runtime_event.kind },
    });
  }
}

describe('GenericRuntimeAdapter', () => {
  it('translates a runtime event into an EventDraft', () => {
    const adapter = new MockAdapter();
    const draft = adapter.translate({
      kind: 'foo',
      actor_id: 'agent_1',
      user_id_hashed: 'abc123',
    });

    expect(draft.event_type).toBe('mock.foo');
    expect(draft.actor).toBe('agent_1');
    expect(draft.subject_ref).toEqual({ scheme: 'sha256_salted', value: 'abc123' });
    expect(draft.payload).toEqual({ kind: 'foo' });
  });

  it('is pure: same input → same output', () => {
    const adapter = new MockAdapter();
    const event: MockRuntimeEvent = {
      kind: 'foo',
      actor_id: 'agent_1',
      user_id_hashed: 'abc123',
    };

    const first = adapter.translate(event);
    const second = adapter.translate(event);

    expect(first).toEqual(second);
  });

  it('throws AdapterTranslationError on bad input', () => {
    const adapter = new MockAdapter();
    expect(() => adapter.translate('not a runtime event' as never)).toThrow(
      AdapterTranslationError,
    );
  });

  it('AdapterTranslationError is an AdapterError', () => {
    const err = new AdapterTranslationError('test');
    expect(err).toBeInstanceOf(AdapterError);
  });

  const FORBIDDEN_METHODS = [
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
  ] as const;

  for (const forbidden of FORBIDDEN_METHODS) {
    it(`rejects forbidden method "${forbidden}" at instantiation`, () => {
      class BadAdapter extends GenericRuntimeAdapter<MockRuntimeEvent> {
        readonly runtime_name = 'bad';
        readonly schema_version = 1;

        translate(): EventDraft {
          return makeEventDraft({ event_type: 'x', actor: 'y' });
        }
      }
      // Inject the forbidden method on the prototype so __init_subclass__-
      // equivalent constructor check fires.
      Object.defineProperty(BadAdapter.prototype, forbidden, {
        value: () => undefined,
        enumerable: false,
        configurable: true,
        writable: true,
      });

      expect(() => new BadAdapter()).toThrow(/forbidden authority\/execution method/);
    });
  }

  it('allows private helper methods with forbidden-name stems', () => {
    class AdapterWithPrivateHelper extends GenericRuntimeAdapter<MockRuntimeEvent> {
      readonly runtime_name = 'ok';
      readonly schema_version = 1;

      translate(runtime_event: MockRuntimeEvent): EventDraft {
        this._execute_internal_check();
        return makeEventDraft({ event_type: 'x', actor: 'y' });
      }

      private _execute_internal_check(): void {
        /* no-op */
      }
    }

    const adapter = new AdapterWithPrivateHelper();
    expect(adapter.translate({ kind: 'x', actor_id: 'y', user_id_hashed: 'z' }).event_type).toBe(
      'x',
    );
  });
});
