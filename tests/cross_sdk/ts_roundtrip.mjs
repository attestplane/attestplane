// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
//
// Cross-SDK round-trip: TypeScript reader + re-emitter (step 2 of 3).
//
// Reads `py_emit.json`, applies the TypeScript SDK canonicalizers to the
// original corpus inputs, then proves the TS output is byte-equal to the
// Python output (canonical bytes + SHA-256 hash). Emits `ts_reemit.json`
// with TS's view of the same data; step 3 (py_verify) does a final
// equivalence check.
//
// Failure modes that this catches:
// - Silent code-point divergence (e.g. Py strips zero-width but TS misses it)
// - JSON key-sort order divergence
// - Different number serialisation (1.0 vs 1)
// - Hash function or input encoding drift
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  canonicalize,
  canonicalizeText,
} from '../../sdk/typescript/dist/index.js';
import { createHash } from 'node:crypto';

const here = dirname(fileURLToPath(import.meta.url));

function toBase64(u8) {
  return Buffer.from(u8).toString('base64');
}

function sha256Hex(u8) {
  return createHash('sha256').update(u8).digest('hex');
}

const corpus = JSON.parse(readFileSync(join(here, 'corpus.json'), 'utf-8'));
const pyEmit = JSON.parse(readFileSync(join(here, 'py_emit.json'), 'utf-8'));

const result = { canonical_text: [], canonical_json: [] };
const failures = [];

function checkPair(kind, id, tsBytes, pyEntry) {
  const tsB64 = toBase64(tsBytes);
  const tsHash = sha256Hex(tsBytes);
  result[kind].push({ id, canonical_b64: tsB64, hash_hex: tsHash });
  if (tsB64 !== pyEntry.canonical_b64 || tsHash !== pyEntry.hash_hex) {
    failures.push({
      kind,
      id,
      py_b64: pyEntry.canonical_b64,
      ts_b64: tsB64,
      py_hash: pyEntry.hash_hex,
      ts_hash: tsHash,
    });
  }
}

const pyTextById = Object.fromEntries(pyEmit.canonical_text.map((e) => [e.id, e]));
const pyJsonById = Object.fromEntries(pyEmit.canonical_json.map((e) => [e.id, e]));

for (const c of corpus.canonical_text) {
  const tsBytes = canonicalizeText(c.text);
  checkPair('canonical_text', c.id, tsBytes, pyTextById[c.id]);
}

for (const c of corpus.canonical_json) {
  const tsBytes = canonicalize(c.value);
  checkPair('canonical_json', c.id, tsBytes, pyJsonById[c.id]);
}

writeFileSync(join(here, 'ts_reemit.json'), JSON.stringify(result, null, 2) + '\n', 'utf-8');

if (failures.length > 0) {
  console.error('::error::Cross-SDK round-trip DRIFT detected:');
  for (const f of failures) {
    console.error(JSON.stringify(f, null, 2));
  }
  process.exit(1);
}

const total = result.canonical_text.length + result.canonical_json.length;
console.log(
  `TypeScript SDK re-emitted ${result.canonical_text.length} text + ${result.canonical_json.length} JSON canonical outputs; all ${total} match Python byte-for-byte ✓`,
);
