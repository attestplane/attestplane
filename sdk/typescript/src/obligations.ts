// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Static obligation registry mappings.
 *
 * These mappings are informational evidence-schema mappings only. They are
 * not legal advice, not compliance certification, and not a runtime policy
 * engine. They mirror the Python static registries for EU AI Act Article 12
 * and DORA Article 8.
 */

export type ImplementationStatus =
  | 'mapping_target'
  | 'designed_toward'
  | 'field_supported'
  | 'verified_in_test';

export interface ObligationEntry {
  readonly framework: string;
  readonly article: string;
  readonly paragraph: string;
  readonly obligation_id: string;
  readonly regulatory_text: string;
  readonly required_evidence_fields: readonly string[];
  readonly optional_evidence_fields: readonly string[];
  readonly event_type_mapping: readonly string[];
  readonly verifier_expectation: string;
  readonly implementation_status: ImplementationStatus;
  readonly legal_disclaimer: string;
  readonly source_citation: string;
  readonly notes?: string;
}

export interface Registry {
  readonly framework: string;
  readonly framework_source: string;
  readonly registry_version: number;
  readonly last_reviewed: string;
  readonly entries: readonly ObligationEntry[];
}

export class ObligationRegistryError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ObligationRegistryError';
  }
}

const REGISTRIES: readonly Registry[] = [
  {
    framework: 'EU AI Act',
    framework_source:
      'Regulation (EU) 2024/1689 of the European Parliament and of the Council of 13 June 2024 laying down harmonised rules on artificial intelligence (Artificial Intelligence Act), OJ L, 2024/1689, 12.7.2024',
    registry_version: 1,
    last_reviewed: '2026-05-17',
    entries: [
      {
        framework: 'EU AI Act',
        article: '12',
        paragraph: '1',
        obligation_id: 'eu_ai_act.art12.1.automatic_recording',
        regulatory_text:
          "High-risk AI systems shall technically allow for the automatic recording of events ('logs') over the lifetime of the system.",
        required_evidence_fields: [],
        optional_evidence_fields: [],
        event_type_mapping: [
          'tool_call_event',
          'policy_check_event',
          'human_approval_event',
          'lease_lifecycle_event',
          'budget_event',
          'settlement_event',
          'worker_assignment_event',
          'runtime_lifecycle_event',
          'gateway_decision_event',
          'state_transition_event',
          'eval_event',
          'routing_event',
        ],
        verifier_expectation:
          "The chain contains at least one event of any v1 type; the substrate's append-only invariant is documented in ADR-0002 and enforced by canonical-JSON byte determinism plus the hash chain.",
        implementation_status: 'designed_toward',
        legal_disclaimer:
          "Mapping target only. Attestplane's append-only hash chain provides one technical component supporting an Article 12(1) implementation; it does not on its own discharge the obligation, which also requires runtime emission of events, retention against the system's lifetime, and the system being a 'high-risk AI system' as defined in Article 6.",
        source_citation: 'Regulation (EU) 2024/1689, Article 12(1).',
        notes:
          "Implementation_status remains 'designed_toward' until M6 retention-policy ADR ships.",
      },
      {
        framework: 'EU AI Act',
        article: '12',
        paragraph: '2(a)',
        obligation_id: 'eu_ai_act.art12.2a.identifying_risk_situations',
        regulatory_text:
          '[Logging capabilities shall enable the recording of events relevant for] identifying situations that may result in the AI system presenting a risk within the meaning of Article 79(1) or in a substantial modification.',
        required_evidence_fields: ['event_type', 'timestamp'],
        optional_evidence_fields: ['session_id', 'reference_db_ref', 'matched_input_ref'],
        event_type_mapping: [
          'policy_check_event',
          'state_transition_event',
          'eval_event',
          'runtime_lifecycle_event',
        ],
        verifier_expectation:
          'Events that record adverse policy decisions, abnormal state transitions, failed evaluations, or runtime crashes carry a timestamp and an event_type drawn from the v1 taxonomy.',
        implementation_status: 'field_supported',
        legal_disclaimer:
          "Mapping target only. Attestplane records risk-relevant events when adapters emit them; what counts as 'a situation that may result in a risk within the meaning of Article 79(1)' is a runtime / deployer determination outside the substrate's scope.",
        source_citation: 'Regulation (EU) 2024/1689, Article 12(2)(a).',
      },
      {
        framework: 'EU AI Act',
        article: '12',
        paragraph: '2(b)',
        obligation_id: 'eu_ai_act.art12.2b.post_market_monitoring',
        regulatory_text:
          '[Logging capabilities shall enable the recording of events relevant for] facilitating the post-market monitoring referred to in Article 72.',
        required_evidence_fields: ['event_type', 'timestamp'],
        optional_evidence_fields: ['session_id'],
        event_type_mapping: [
          'tool_call_event',
          'policy_check_event',
          'eval_event',
          'state_transition_event',
        ],
        verifier_expectation:
          'Recorded events span the operational lifetime of the system and are retrievable as a verifiable chain, supporting Article 72 post-market obligations.',
        implementation_status: 'designed_toward',
        legal_disclaimer:
          'Mapping target only. The substrate provides the recording layer; Article 72 also requires a post-market monitoring system / plan and provider procedures, which are deployer responsibilities.',
        source_citation: 'Regulation (EU) 2024/1689, Article 12(2)(b).',
      },
      {
        framework: 'EU AI Act',
        article: '12',
        paragraph: '2(c)',
        obligation_id: 'eu_ai_act.art12.2c.monitoring_operation',
        regulatory_text:
          '[Logging capabilities shall enable the recording of events relevant for] monitoring the operation of high-risk AI systems referred to in Article 26(5).',
        required_evidence_fields: ['event_type', 'timestamp'],
        optional_evidence_fields: ['session_id'],
        event_type_mapping: [
          'runtime_lifecycle_event',
          'gateway_decision_event',
          'state_transition_event',
          'tool_call_event',
        ],
        verifier_expectation:
          "Recorded events include runtime start/stop, gateway admit/deny decisions, and state transitions sufficient for an operator to reconstruct the system's operational timeline.",
        implementation_status: 'designed_toward',
        legal_disclaimer:
          'Mapping target only. The substrate captures operational events when adapters emit them; the deployer (acting per Article 26(5)) is responsible for ensuring those events are emitted and reviewed.',
        source_citation: 'Regulation (EU) 2024/1689, Article 12(2)(c).',
      },
      {
        framework: 'EU AI Act',
        article: '12',
        paragraph: '3(a)',
        obligation_id: 'eu_ai_act.art12.3a.period_of_each_use',
        regulatory_text:
          '[For high-risk AI systems referred to in point 1(a) of Annex III, the logging capabilities shall provide, at a minimum] recording of the period of each use of the system (start date and time and end date and time of each use).',
        required_evidence_fields: ['session_id', 'timestamp'],
        optional_evidence_fields: [],
        event_type_mapping: ['runtime_lifecycle_event', 'state_transition_event'],
        verifier_expectation:
          'For each session_id present in the chain there exists at least one event marking the start of use and at least one event marking the end of use; both carry timestamps. (Implementation deferred to M6; v0.1 verifier surfaces this as a warning, not an error.)',
        implementation_status: 'field_supported',
        legal_disclaimer:
          "Mapping target only. The session_id field on EventDraft is the substrate's mechanism for recording per-use periods. Whether the runtime emits start/end events for each use of the system is a runtime/adapter responsibility outside the substrate's scope.",
        source_citation:
          'Regulation (EU) 2024/1689, Article 12(3)(a). Applies specifically to Annex III point 1(a) (biometric identification systems for natural persons).',
      },
      {
        framework: 'EU AI Act',
        article: '12',
        paragraph: '3(b)',
        obligation_id: 'eu_ai_act.art12.3b.reference_database',
        regulatory_text:
          '[For high-risk AI systems referred to in point 1(a) of Annex III, the logging capabilities shall provide, at a minimum] the reference database against which input data has been checked by the system.',
        required_evidence_fields: ['reference_db_ref'],
        optional_evidence_fields: ['session_id'],
        event_type_mapping: ['eval_event', 'policy_check_event'],
        verifier_expectation:
          'Every eval_event (and policy_check_event when applicable to biometric matching) has reference_db_ref populated with a stable identifier of the reference database used.',
        implementation_status: 'field_supported',
        legal_disclaimer:
          "Mapping target only. The reference_db_ref field on EventDraft is the substrate's mechanism for recording reference-database identity; the adapter is responsible for populating it with a meaningful and stable identifier.",
        source_citation:
          'Regulation (EU) 2024/1689, Article 12(3)(b). Applies specifically to Annex III point 1(a) (biometric identification systems for natural persons).',
      },
      {
        framework: 'EU AI Act',
        article: '12',
        paragraph: '3(c)',
        obligation_id: 'eu_ai_act.art12.3c.matched_input_data',
        regulatory_text:
          '[For high-risk AI systems referred to in point 1(a) of Annex III, the logging capabilities shall provide, at a minimum] the input data for which the search has led to a match.',
        required_evidence_fields: ['matched_input_ref'],
        optional_evidence_fields: ['session_id', 'reference_db_ref'],
        event_type_mapping: ['eval_event'],
        verifier_expectation:
          "Every eval_event whose decision is 'PASS' (i.e., a match) has matched_input_ref populated with a SHA-256 content reference to the input data, never the raw input.",
        implementation_status: 'field_supported',
        legal_disclaimer:
          'Mapping target only. The matched_input_ref field on EventDraft records a SHA-256 content reference to the input data, not the raw data, in keeping with GDPR Article 5(1)(c) data minimisation. The substrate does not retain the underlying input.',
        source_citation:
          'Regulation (EU) 2024/1689, Article 12(3)(c). Applies specifically to Annex III point 1(a) (biometric identification systems for natural persons).',
      },
      {
        framework: 'EU AI Act',
        article: '12',
        paragraph: '3(d)',
        obligation_id: 'eu_ai_act.art12.3d.human_verifier',
        regulatory_text:
          '[For high-risk AI systems referred to in point 1(a) of Annex III, the logging capabilities shall provide, at a minimum] the identification of the natural persons involved in the verification of the results, as referred to in Article 14(5).',
        required_evidence_fields: ['human_verifier'],
        optional_evidence_fields: ['session_id'],
        event_type_mapping: ['human_approval_event', 'eval_event'],
        verifier_expectation:
          "Every human_approval_event has human_verifier populated; every eval_event with evaluator_kind in {'HUMAN','ENSEMBLE'} has human_verifier populated. The human_verifier field is a SubjectRef so direct identifiers cannot be silently written.",
        implementation_status: 'field_supported',
        legal_disclaimer:
          "Mapping target only. The human_verifier field is typed as SubjectRef, which forces pseudonymisation per GDPR Article 4(5). Whether the pseudonymisation scheme is recoverable (and to whom) is a deployer policy decision outside the substrate's scope.",
        source_citation:
          'Regulation (EU) 2024/1689, Article 12(3)(d). Cross-references Article 14(5) on human oversight. Applies specifically to Annex III point 1(a) (biometric identification systems for natural persons).',
      },
    ],
  },
  {
    framework: 'DORA',
    framework_source:
      'Regulation (EU) 2022/2554 of the European Parliament and of the Council of 14 December 2022 on digital operational resilience for the financial sector (Digital Operational Resilience Act), OJ L 333, 27.12.2022',
    registry_version: 1,
    last_reviewed: '2026-05-17',
    entries: [
      {
        framework: 'DORA',
        article: '8',
        paragraph: '1',
        obligation_id: 'dora.art8.1.identification_and_documentation',
        regulatory_text:
          'As part of the ICT risk management framework, financial entities shall identify, classify and adequately document all ICT supported business functions, roles and responsibilities, the information assets and ICT assets supporting those functions, and their roles and dependencies in relation to ICT risk.',
        required_evidence_fields: ['event_type', 'timestamp'],
        optional_evidence_fields: ['actor', 'session_id', 'reference_db_ref'],
        event_type_mapping: [
          'runtime_lifecycle_event',
          'worker_assignment_event',
          'gateway_decision_event',
          'policy_check_event',
        ],
        verifier_expectation:
          'Recorded events sufficient to reconstruct which ICT assets supported which business functions over the audit window — runtime starts/stops, worker assignments, gateway-level admission decisions, and policy gates applied — are present.',
        implementation_status: 'designed_toward',
        legal_disclaimer:
          "Mapping target only. Attestplane records ICT-asset-level events when adapters emit them; identification, classification, and documentation of business functions, asset criticality, and dependencies are deployer responsibilities outside the substrate's scope. The substrate is one component supporting a DORA Article 8(1) implementation, not the implementation itself.",
        source_citation: 'Regulation (EU) 2022/2554, Article 8(1).',
        notes:
          'regulatory_text is a paraphrase pending final verification against OJ L 333, 27.12.2022; the substantive obligation is correctly summarised. Public-facing material citing this entry must include the legal_disclaimer per claims_policy.md.',
      },
      {
        framework: 'DORA',
        article: '8',
        paragraph: '3',
        obligation_id: 'dora.art8.3.classification_and_yearly_review',
        regulatory_text:
          'Information assets and ICT assets shall be classified by financial entities, with the classification reviewed as necessary and at least on a yearly basis.',
        required_evidence_fields: ['event_type', 'timestamp'],
        optional_evidence_fields: ['actor', 'reference_db_ref', 'human_verifier'],
        event_type_mapping: [
          'policy_check_event',
          'human_approval_event',
          'state_transition_event',
        ],
        verifier_expectation:
          'At least one event per calendar year exists per classified asset; events recording the yearly review carry a human_verifier when the review is human-led.',
        implementation_status: 'designed_toward',
        legal_disclaimer:
          "Mapping target only. The substrate can record classification-review events when they occur; whether the yearly cadence has been met is a deployer-side schedule discipline outside the substrate's enforcement scope.",
        source_citation: 'Regulation (EU) 2022/2554, Article 8(3).',
        notes:
          'regulatory_text is a paraphrase pending final verification against OJ L 333, 27.12.2022.',
      },
      {
        framework: 'DORA',
        article: '8',
        paragraph: '5',
        obligation_id: 'dora.art8.5.privileged_access_inventory',
        regulatory_text:
          'Financial entities shall identify and document the user accounts, including those used by ICT third-party service providers, with privileged or administrative access.',
        required_evidence_fields: ['event_type', 'timestamp', 'actor'],
        optional_evidence_fields: ['subject_ref', 'human_verifier', 'session_id'],
        event_type_mapping: [
          'policy_check_event',
          'gateway_decision_event',
          'state_transition_event',
        ],
        verifier_expectation:
          'Events with administrative or privileged-access semantics carry the acting actor and, where applicable, a SubjectRef wrapper for the operator identity per GDPR Article 4(5) pseudonymisation.',
        implementation_status: 'field_supported',
        legal_disclaimer:
          'Mapping target only. The actor field and SubjectRef type enable recording privileged-access events without storing raw identifiers; building and maintaining the inventory itself is a deployer responsibility.',
        source_citation: 'Regulation (EU) 2022/2554, Article 8(5).',
        notes:
          'regulatory_text is a paraphrase pending final verification against OJ L 333, 27.12.2022.',
      },
      {
        framework: 'DORA',
        article: '8',
        paragraph: '7',
        obligation_id: 'dora.art8.7.third_party_dependency_mapping',
        regulatory_text:
          'Financial entities shall identify, on a continuous basis, all processes that are dependent on ICT third-party service providers and identify interconnections with ICT third-party service providers that provide services supporting critical or important functions.',
        required_evidence_fields: ['event_type', 'timestamp'],
        optional_evidence_fields: ['reference_db_ref', 'actor'],
        event_type_mapping: [
          'tool_call_event',
          'gateway_decision_event',
          'runtime_lifecycle_event',
        ],
        verifier_expectation:
          'Tool calls and gateway decisions involving external ICT third-party services are recorded as events with sufficient identifying refs to map the dependency.',
        implementation_status: 'designed_toward',
        legal_disclaimer:
          'Mapping target only. The substrate records dependency-triggering events when adapters emit them; producing the mapping itself, identifying critical-or-important functions, and continuous maintenance of that mapping are deployer responsibilities.',
        source_citation: 'Regulation (EU) 2022/2554, Article 8(7).',
        notes:
          'regulatory_text is a paraphrase pending final verification against OJ L 333, 27.12.2022.',
      },
      {
        framework: 'DORA',
        article: '8',
        paragraph: '8',
        obligation_id: 'dora.art8.8.records_of_third_party_arrangements',
        regulatory_text:
          'Financial entities shall maintain and update relevant records on the use of services provided by ICT third-party service providers, distinguishing between those supporting critical or important functions and other arrangements.',
        required_evidence_fields: ['event_type', 'timestamp'],
        optional_evidence_fields: ['reference_db_ref', 'actor', 'session_id'],
        event_type_mapping: [
          'gateway_decision_event',
          'settlement_event',
          'tool_call_event',
          'lease_lifecycle_event',
        ],
        verifier_expectation:
          'Events recording the use of an ICT third-party service carry a stable reference (reference_db_ref or actor) to the third-party arrangement; the append-only chain provides the maintenance-and-update audit trail.',
        implementation_status: 'designed_toward',
        legal_disclaimer:
          "Mapping target only. The substrate's append-only hash chain provides the record-keeping integrity layer; classifying arrangements as supporting critical-or-important functions and maintaining the canonical record under DORA Article 28 register-of-information are deployer responsibilities.",
        source_citation:
          'Regulation (EU) 2022/2554, Article 8(8). See also Article 28 (register of information on contractual arrangements).',
        notes:
          'regulatory_text is a paraphrase pending final verification against OJ L 333, 27.12.2022.',
      },
    ],
  },
] as const satisfies readonly Registry[];

function cloneEntry(entry: ObligationEntry): ObligationEntry {
  return Object.freeze({
    ...entry,
    required_evidence_fields: Object.freeze([...entry.required_evidence_fields]),
    optional_evidence_fields: Object.freeze([...entry.optional_evidence_fields]),
    event_type_mapping: Object.freeze([...entry.event_type_mapping]),
  });
}

function cloneRegistry(registry: Registry): Registry {
  return Object.freeze({
    ...registry,
    entries: Object.freeze(registry.entries.map((entry) => cloneEntry(entry))),
  });
}

function registryByFramework(framework: string): Registry {
  const registry = REGISTRIES.find((item) => item.framework === framework);
  if (registry === undefined) {
    throw new ObligationRegistryError(`no registry for framework ${framework}`);
  }
  return cloneRegistry(registry);
}

export function loadEuAiActArticle12(): Registry {
  return registryByFramework('EU AI Act');
}

export function loadDoraArticle8(): Registry {
  return registryByFramework('DORA');
}

export function loadAllRegistries(): readonly Registry[] {
  return Object.freeze([loadEuAiActArticle12(), loadDoraArticle8()]);
}

export function obligationById(
  registry: Registry,
  obligationId: string,
): ObligationEntry | undefined {
  return registry.entries.find((entry) => entry.obligation_id === obligationId);
}

export function obligationsByEventType(
  registry: Registry,
  eventType: string,
): readonly ObligationEntry[] {
  return Object.freeze(
    registry.entries.filter((entry) => entry.event_type_mapping.includes(eventType)),
  );
}

export function obligationsByImplementationStatus(
  registry: Registry,
  status: ImplementationStatus,
): readonly ObligationEntry[] {
  return Object.freeze(registry.entries.filter((entry) => entry.implementation_status === status));
}
