// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Clean-install smoke for a *published* @attestplane/attestplane release.
 *
 * Evidence for the Controlled Availability admission criteria (#3 clean-install
 * smoke and the verifier portion of #4), run against the package installed from
 * npm — not the local source tree. Run from a throwaway project that has
 * `npm install @attestplane/attestplane@<version>`.
 *
 * It imports only the public package entrypoint. Modes:
 *   * `smoke [EXPECTED_VERSION]` (default): assert VERSION matches the expected
 *     version (catches a stale-literal version drift) and is not the
 *     manifest-missing sentinel; build a bundle and verify -> ok; tamper and
 *     verify -> rejected (claim-safety invariant).
 *   * `emit <PATH>`: write a valid bundle JSON for the cross-SDK roundtrip.
 *   * `verify <PATH>`: verify a bundle JSON produced by the other SDK -> ok.
 *
 * Usage:
 *   node ca_registry_smoke.mjs [smoke [EXPECTED_VERSION] | emit PATH | verify PATH]
 */

import { readFileSync, writeFileSync } from 'node:fs';

import {
  AttestSubstrate,
  ProofBundleBuilder,
  VERSION,
  makeEventDraft,
  verifyProofBundle,
} from '@attestplane/attestplane';

function fail(msg) {
  console.error(`::error::${msg}`);
  process.exit(1);
}

function buildValidBundle() {
  const sub = new AttestSubstrate();
  sub.append(makeEventDraft({ event_type: 'eval_event', actor: 'agent' }), {
    now: new Date('2026-01-01T00:00:00.000Z'),
    event_id: '00000000-0000-7000-8000-000000000001',
  });
  const builder = new ProofBundleBuilder({ chain_id: 'ca-smoke', producer_runtime: 'ca-smoke' });
  builder.extend(sub.snapshot());
  return builder.build();
}

const mode = process.argv[2] ?? 'smoke';

if (mode === 'emit') {
  const path = process.argv[3];
  if (!path) fail('emit requires an output path');
  writeFileSync(path, JSON.stringify(buildValidBundle()), 'utf8');
  console.log(`CA emit OK: wrote bundle to ${path}`);
} else if (mode === 'verify') {
  const path = process.argv[3];
  if (!path) fail('verify requires an input path');
  const bundle = JSON.parse(readFileSync(path, 'utf8'));
  if (!verifyProofBundle(bundle).ok) fail(`cross-SDK bundle failed verification: ${path}`);
  console.log(`CA cross-verify OK: @attestplane/attestplane ${VERSION} verified ${path}`);
} else {
  // Default: self smoke. Accept "smoke [VERSION]" or a bare "[VERSION]".
  const expected = mode === 'smoke' ? process.argv[3] : mode;

  if (VERSION === '0.0.0+unknown') {
    fail('VERSION is the manifest-missing sentinel');
  }
  if (expected !== undefined && VERSION !== expected) {
    fail(`VERSION '${VERSION}' != expected '${expected}' (version drift)`);
  }

  const bundle = buildValidBundle();
  if (!verifyProofBundle(bundle).ok) {
    fail('valid bundle failed verification');
  }

  const tampered = JSON.parse(JSON.stringify(bundle));
  tampered.events[0].event.actor = 'agent://tampered';
  if (verifyProofBundle(tampered).ok) {
    fail('tampered bundle verified ok (claim-safety broken)');
  }

  console.log(`CA registry smoke OK: @attestplane/attestplane ${VERSION} (valid->ok, tampered->rejected)`);
}
