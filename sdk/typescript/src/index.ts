// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Attestplane — verifiable audit substrate for AI agents.
 *
 * Designed toward EU AI Act Article 12 auditability. Apache-2.0 licensed.
 * See https://github.com/attestplane/attestplane and
 * docs/adr/0002-substrate-data-model-and-hash-chain-v0.md for the design.
 */

export {
  AdapterError,
  AdapterTranslationError,
  GenericRuntimeAdapter,
} from './adapters.js';
export { CanonicalizationError, canonicalize } from './canonical.js';
export {
  ALL_EVENT_TYPES_V1,
  BUDGET_EVENT,
  EVAL_EVENT,
  EVIDENCE_TAXONOMY_VERSION,
  GATEWAY_DECISION_EVENT,
  HUMAN_APPROVAL_EVENT,
  LEASE_LIFECYCLE_EVENT,
  POLICY_CHECK_EVENT,
  ROUTING_EVENT,
  RUNTIME_LIFECYCLE_EVENT,
  SETTLEMENT_EVENT,
  STATE_TRANSITION_EVENT,
  TOOL_CALL_EVENT,
  WORKER_ASSIGNMENT_EVENT,
  isKnownV1EventType,
  type EventTypeV1,
} from './event_types.js';
export {
  GENESIS_HASH,
  SCHEMA_VERSION,
  chainExtend,
  genesisHead,
  hashEvent,
  headOf,
  verifyChain,
  type ChainExtendOptions,
  type VerificationResult,
} from './hashchain.js';
export { AttestSubstrate, type AppendOptions } from './substrate.js';
export {
  makeEventDraft,
  makeSubjectRef,
  type AuditEvent,
  type ChainHead,
  type ChainedEvent,
  type EventDraft,
  type EventDraftInput,
  type SubjectRef,
  type SubjectScheme,
} from './types.js';

export {
  DEFAULT_FORBIDDEN_FIELDS,
  ProofBundleBuilder,
  buildAuditorExport,
  serializeChainedEvent,
  type AuditorExport,
  type AuditorExportOptions,
  type FrameworkMapping,
  type ImplementationStatus,
  type ProofBundle,
  type ProofBundleBuilderInput,
  type SerializedAuditEvent,
  type SerializedChainedEvent,
  type SerializedSubjectRef,
} from './proof_bundle.js';
export {
  BundleSchemaError,
  BundleVerificationError,
  shortSummary,
  verifyProofBundle,
  verifyProofBundleFile,
  type BundleVerificationResult,
} from './verifier.js';
export { VERSION } from './index_version.js';
