// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Attestplane — verifiable audit substrate for AI agents.
 *
 * Designed toward EU AI Act Article 12 auditability. Apache-2.0 licensed.
 * See https://github.com/attestplane/attestplane and
 * docs/adr/0002-substrate-data-model-and-hash-chain-v0.md for the design.
 */

export { CanonicalizationError, canonicalize } from './canonical.js';
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

export const VERSION = '0.0.1';
