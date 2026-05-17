// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Replay-manifest verifier — read-only walker, NEVER re-executes.
 *
 * ADR-0009 A.9 + P1.1. Given a `ReplayManifest` describing which
 * original chain segment was replayed and what observed booleans the
 * external replay runner reported, this function checks the manifest
 * is internally consistent against the chain provided by the caller.
 *
 * **Hard constraint** (per ADR-0009 § B.6 + invariant 7): this module
 * NEVER re-executes the workload. Replay execution lives in REDLINE
 * C.13 `aios-replay-runner`. We only walk the provided chain.
 */

import { validateReplayEventPayload } from './event_payloads.js';

export type ReplayCoverage = 'deterministic' | 'non_deterministic' | 'no_replay_event';

export interface ReplayManifest {
  readonly replay_run_id: string;
  readonly original_run_id: string;
  /** The runner's claimed outcome; the verifier checks the chain agrees. */
  readonly expected_deterministic: boolean;
  readonly snapshot_id_ref?: string;
}

export interface ReplayVerificationResult {
  readonly ok: boolean;
  readonly coverage: ReplayCoverage;
  /** The chain seq of the matching `replay_event`, or null. */
  readonly matching_seq: number | null;
  readonly reason: string | null;
}

/** Minimal chain-event shape this verifier needs. Matches the JSONL
 *  backend's serialised form and the ProofBundle wire format. */
export interface ChainEventForReplay {
  readonly seq: number;
  readonly event_type: string;
  readonly payload: Record<string, unknown>;
}

/**
 * Check that `chainEvents` contains a `replay_event` matching `manifest`.
 *
 * Read-only. Pure function. Never re-executes. Never modifies anything.
 */
export function verifyReplayManifest(
  chainEvents: readonly ChainEventForReplay[],
  manifest: ReplayManifest,
  options: { readonly verification_time?: Date } = {},
): ReplayVerificationResult {
  if (!Array.isArray(chainEvents)) {
    return {
      ok: false,
      coverage: 'no_replay_event',
      matching_seq: null,
      reason: `chainEvents must be array, got ${typeof chainEvents}`,
    };
  }
  if (
    options.verification_time !== undefined &&
    Number.isNaN(options.verification_time.getTime())
  ) {
    return {
      ok: false,
      coverage: 'no_replay_event',
      matching_seq: null,
      reason: 'verification_time must be a valid Date',
    };
  }

  const candidates: { seq: number; payload: Record<string, unknown> }[] = [];
  for (const ev of chainEvents) {
    if (ev === null || typeof ev !== 'object') continue;
    if (ev.event_type !== 'replay_event') continue;
    if (ev.payload === null || typeof ev.payload !== 'object') continue;
    const payload = ev.payload;
    if (payload.replay_run_id !== manifest.replay_run_id) continue;
    if (payload.original_run_id !== manifest.original_run_id) continue;
    if (
      manifest.snapshot_id_ref !== undefined &&
      payload.snapshot_id_ref !== manifest.snapshot_id_ref
    ) {
      continue;
    }
    if (typeof ev.seq !== 'number' || !Number.isInteger(ev.seq)) continue;
    candidates.push({ seq: ev.seq, payload });
  }

  if (candidates.length === 0) {
    return {
      ok: false,
      coverage: 'no_replay_event',
      matching_seq: null,
      reason: `no replay_event payload found with replay_run_id=${JSON.stringify(manifest.replay_run_id)}`,
    };
  }

  candidates.sort((a, b) => a.seq - b.seq);
  const latest = candidates[candidates.length - 1] as {
    seq: number;
    payload: Record<string, unknown>;
  };
  const { seq, payload } = latest;

  try {
    validateReplayEventPayload(payload);
  } catch (exc) {
    return {
      ok: false,
      coverage: 'no_replay_event',
      matching_seq: seq,
      reason: `matching replay_event payload failed validation: ${(exc as Error).message}`,
    };
  }

  const actualDet = Boolean(payload.deterministic_result);
  if (manifest.expected_deterministic !== actualDet) {
    return {
      ok: false,
      coverage: actualDet ? 'deterministic' : 'non_deterministic',
      matching_seq: seq,
      reason: `manifest expected deterministic_result=${manifest.expected_deterministic}, chain payload reports ${actualDet}`,
    };
  }

  return {
    ok: true,
    coverage: actualDet ? 'deterministic' : 'non_deterministic',
    matching_seq: seq,
    reason: null,
  };
}
