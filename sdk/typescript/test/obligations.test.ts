// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';

import {
  loadAllRegistries,
  loadDoraArticle8,
  loadEuAiActArticle12,
  obligationById,
  obligationsByEventType,
  obligationsByImplementationStatus,
} from '../src/obligations.js';

describe('obligation registry parity', () => {
  it('loads EU AI Act Article 12 registry', () => {
    const registry = loadEuAiActArticle12();
    expect(registry.framework).toBe('EU AI Act');
    expect(registry.registry_version).toBe(1);
    expect(registry.entries).toHaveLength(8);
    expect(obligationById(registry, 'eu_ai_act.art12.3d.human_verifier')?.paragraph).toBe('3(d)');
  });

  it('loads DORA Article 8 registry', () => {
    const registry = loadDoraArticle8();
    expect(registry.framework).toBe('DORA');
    expect(registry.registry_version).toBe(1);
    expect(registry.entries).toHaveLength(5);
    expect(
      obligationById(registry, 'dora.art8.5.privileged_access_inventory')?.implementation_status,
    ).toBe('field_supported');
  });

  it('keeps stable ids and canonical order', () => {
    const registries = loadAllRegistries();
    expect(registries.map((registry) => registry.framework)).toEqual(['EU AI Act', 'DORA']);
    const ids = registries.flatMap((registry) =>
      registry.entries.map((entry) => entry.obligation_id),
    );
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toContain('eu_ai_act.art12.1.automatic_recording');
    expect(ids).toContain('dora.art8.8.records_of_third_party_arrangements');
  });

  it('returns undefined for unknown obligation id', () => {
    expect(obligationById(loadEuAiActArticle12(), 'does.not.exist')).toBeUndefined();
  });

  it('filters by event type and implementation status', () => {
    const registry = loadEuAiActArticle12();
    expect(obligationsByEventType(registry, 'eval_event').length).toBeGreaterThan(0);
    const fieldSupported = obligationsByImplementationStatus(registry, 'field_supported');
    expect(fieldSupported.map((entry) => entry.obligation_id)).toContain(
      'eu_ai_act.art12.3c.matched_input_data',
    );
  });

  it('returns frozen defensive copies', () => {
    const registry = loadEuAiActArticle12();
    expect(Object.isFrozen(registry)).toBe(true);
    expect(Object.isFrozen(registry.entries)).toBe(true);
    expect(Object.isFrozen(registry.entries[0])).toBe(true);
    expect(Object.isFrozen(registry.entries[0]?.event_type_mapping)).toBe(true);
  });

  it('keeps legal-disclaimer wording on every entry', () => {
    for (const registry of loadAllRegistries()) {
      for (const entry of registry.entries) {
        expect(entry.legal_disclaimer.toLowerCase()).toContain('mapping target');
      }
    }
  });
});
