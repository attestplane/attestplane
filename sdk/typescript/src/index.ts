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
export {
  AdapterConformanceError,
  replayFixture,
  type AdapterCaseResult,
  type AdapterConformanceReport,
  type ReplayOptions,
  type TranslateAdapter,
} from './adapter_conformance.js';
export {
  LangSmithAdapter,
  type LangSmithRun,
} from './adapters/langsmith.js';
export {
  LangFuseAdapter,
  type LangFuseObservation,
} from './adapters/langfuse.js';
export {
  ANCHOR_SCHEMA_VERSION,
  AnchorError,
  AnchorVerificationError,
  DEFAULT_ANCHOR_POLICY,
  MockTSAProvider,
  MultiTSAProvider,
  TSAProvider,
  TSAUnavailableError,
  makeAnchorPolicy,
  makeTimestampRequest,
  validateAnchorRecord,
  verifyChainWithAnchors,
  type AnchorPolicy,
  type AnchorRecord,
  type AnchorStatus,
  type AnchorVerificationResult,
  type CertStatus,
  type MockTSAProviderInput,
  type MultiTSAProviderInput,
  type SingleAnchorResult,
  type TimestampRequest,
  type VerifyChainWithAnchorsOptions,
} from './anchoring.js';
export {
  parseTimestampResponse,
  verifyTimestampToken,
  type ParsedTimestampTs,
  type VerifyTimestampOptions,
} from './rfc3161.js';
export { CanonicalizationError, canonicalize } from './canonical.js';
export {
  CanonicalTextError,
  canonicalizeText,
  textHash,
  textHashHex,
} from './canonical_text.js';
export {
  FORBIDDEN_PAYLOAD_FIELDS,
  PayloadValidationError,
  validateLeaseLifecycleEventPayload,
  validatePolicyCheckEventPayload,
  validateReplayEventPayload,
  type LeaseLifecycle,
  type LeaseLifecycleEventPayload,
  type PolicyCheckEventPayload,
  type PolicyDecision,
  type PolicyEffect,
  type ReplayEventPayload,
} from './event_payloads.js';
export {
  verifyReplayManifest,
  type ChainEventForReplay,
  type ReplayCoverage,
  type ReplayManifest,
  type ReplayVerificationResult,
} from './replay_verifier.js';
export {
  checkSettlementPrecondition,
  type ChainEventForSettlement,
  type SettlementPreconditionClaim,
  type SettlementVerificationResult,
} from './settlement_verifier.js';
export {
  ALL_REASON_CODES_V1,
  REASON_CODE_DESCRIPTIONS,
  REASON_CODE_SCHEMA_VERSION,
  isKnownReasonCode,
  reasonCodeMatchesFormat,
  type ReasonCodeV1,
} from './reason_codes.js';
export {
  ALL_VERIFY_ERROR_CODES_V1,
  VERIFY_ERROR_DESCRIPTIONS,
  VERIFY_ERROR_SCHEMA_VERSION,
  isKnownVerifyErrorCode,
  type VerifyErrorCode,
} from './verify_errors.js';
export {
  ALL_VERIFY_REASON_CODES_V1,
  VERIFY_REASON_ANCHOR_INVALID,
  VERIFY_REASON_CANONICAL_MISMATCH,
  VERIFY_REASON_CODE_DESCRIPTIONS,
  VERIFY_REASON_CODE_SCHEMA_VERSION,
  VERIFY_REASON_TAXONOMY,
  VERIFY_REASON_REQUIRED_FIELD_MISSING,
  VERIFY_REASON_SCHEMA_INVALID,
  VERIFY_REASON_SCHEMA_UNKNOWN,
  VERIFY_REASON_SCHEMA_VERSION_MISSING,
  VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
  VERIFY_REASON_SIGNATURE_INVALID,
  VERIFY_REASON_SIGNATURE_MISSING,
  VERIFY_REASON_STRUCTURE_INVALID,
  VERIFY_REASON_TAXONOMY_VERSION,
  isKnownVerifyReasonCode,
  verifyReasonCodeExplanation,
  verifyReasonCodeMatchesFormat,
  type VerifyReasonCodeV1,
} from './verify_reason_codes.js';
export {
  RETENTION_PROOF_SCHEMA_VERSION,
  buildDeletionProof,
  buildRetentionMarker,
  validateRetentionProof,
  verifyRetentionProofs,
  type RetentionAction,
  type RetentionProof,
  type RetentionProofVerificationResult,
} from './retention.js';
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
  SUPPORTED_SCHEMA_VERSIONS,
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
  deserializeSignatureRecord,
  serializeChainedEvent,
  serializeSignatureRecord,
  type AuditorExport,
  type AuditorExportOptions,
  type FrameworkMapping,
  type ImplementationStatus,
  type ProofBundle,
  type ProofBundleBuilderInput,
  type SerializedAuditEvent,
  type SerializedChainedEvent,
  type SerializedSignatureRecord,
  type SerializedSubjectRef,
} from './proof_bundle.js';
export {
  DSSE_PAYLOAD_TYPE,
  IntotoError,
  PREDICATE_TYPE_V1,
  STATEMENT_TYPE,
  canonicalJsonBytes,
  dsseEnvelopeToStatement,
  proofBundleToInTotoStatement,
  statementToDsseEnvelope,
  type DsseEnvelope,
  type DsseSignature,
  type IntotoStatement,
  type IntotoSubject,
} from './intoto.js';
export {
  ObligationRegistryError,
  loadAllRegistries,
  loadDoraArticle8,
  loadEuAiActArticle12,
  obligationById,
  obligationsByEventType,
  obligationsByImplementationStatus,
  type ImplementationStatus as ObligationImplementationStatus,
  type ObligationEntry,
  type Registry,
} from './obligations.js';
export {
  type AnchoringResult,
  BundleSchemaError,
  BundleVerificationError,
  shortSummary,
  verifyProofBundle,
  verifyProofBundleFile,
  type BundleVerificationResult,
} from './verifier.js';

// ADR-0005 event-signing surface (T6).
export {
  KeyBoundaryError,
  KeyProvider,
  KeyProviderError,
  SIGNATURE_SCHEMA_VERSION,
  SignatureVerificationError,
  SigningError,
  DEFAULT_SIGNATURE_POLICY,
  deriveKeyId,
  makeSignaturePolicy,
  validateSignatureRecord,
  type SignatureMode,
  type SignaturePolicy,
  type SignatureRecord,
  type SigningMaterial,
} from './signing/base.js';
export {
  EnvKeyProvider,
  FileKeyProvider,
  InMemoryKeyProvider,
  MultiSignerProvider,
  exportPublicKeyDer,
  seedToPrivateKey,
  type EnvKeyProviderOptions,
  type FileKeyProviderOptions,
  type InMemoryKeyProviderOptions,
} from './signing/providers.js';
export {
  Signer,
  buildPerEventPayload,
  buildSegmentHeadPayload,
  type SignerOptions,
} from './signing/signer.js';
export {
  TrustRoots,
  TrustRootsError,
  loadTrustRoots,
  parseTrustRoots,
  type TrustRootEntry,
} from './signing/trust_roots.js';
export {
  STATUS_RANK,
  verifyChainFull,
  verifyChainWithSignatures,
  type BundleVerificationResult as ChainBundleVerificationResult,
  type SignatureStatus,
  type SingleSignatureResult,
  type VerifyChainFullOptions,
  type VerifyChainWithSignaturesOptions,
  type VerifyChainWithSignaturesResult,
} from './signing/verifier_ext.js';

export { VERSION } from './index_version.js';
