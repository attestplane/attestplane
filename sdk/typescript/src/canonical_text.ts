// SPDX-FileCopyrightText: 2026 The Attestplane Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Canonical text normalizer (TypeScript port of
 * `sdk/python/src/attestplane/canonical_text.py`).
 *
 * Cross-language byte stable with the Python reference implementation
 * across the conformance vectors in
 * `sdk/python/tests/conformance/text_vectors.json`.
 *
 * Four-stage algorithm locked by `docs/spec/canonical-text-v1.md`:
 *   1. NFC normalize
 *   2. Unicode default lowercase
 *   3. Zero-width strip (U+200B, U+200C, U+200D, U+FEFF)
 *   4. Whitespace fold (split on \s+, rejoin with single space, trim)
 */

import { createHash } from 'node:crypto';

const ZERO_WIDTH_CODE_POINTS = new Set([0x200b, 0x200c, 0x200d, 0xfeff]);

export class CanonicalTextError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CanonicalTextError';
  }
}

function rejectForbiddenCodePoints(text: string): void {
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    if (code === 0) {
      throw new CanonicalTextError('input contains U+0000 (null) — forbidden');
    }
    // Detect unpaired surrogates: a high surrogate not followed by a low,
    // or a low surrogate not preceded by a high.
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = i + 1 < text.length ? text.charCodeAt(i + 1) : 0;
      if (next < 0xdc00 || next > 0xdfff) {
        throw new CanonicalTextError(
          `input contains unpaired surrogate U+${code.toString(16).toUpperCase().padStart(4, '0')} — forbidden`,
        );
      }
      i++; // skip the paired low surrogate
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      throw new CanonicalTextError(
        `input contains unpaired surrogate U+${code.toString(16).toUpperCase().padStart(4, '0')} — forbidden`,
      );
    }
  }
}

function stripZeroWidth(text: string): string {
  // Iterate by code point to be robust under astral planes.
  let out = '';
  for (const ch of text) {
    const cp = ch.codePointAt(0);
    if (cp != null && !ZERO_WIDTH_CODE_POINTS.has(cp)) {
      out += ch;
    }
  }
  return out;
}

function foldWhitespace(text: string): string {
  // `/\s+/u` matches any run of Unicode whitespace (with the `u` flag);
  // splitting then rejoining with single ASCII space is the analogue of
  // Python's `" ".join(text.split())`. Edge empty strings filter out.
  const parts = text.split(/\s+/u).filter((s) => s.length > 0);
  return parts.join(' ');
}

/**
 * Return the canonical UTF-8 bytes of `text`.
 *
 * Pure, deterministic, cross-language byte stable across the
 * conformance-vector set. Identical inputs in Python and TypeScript
 * implementations produce identical output bytes.
 */
export function canonicalizeText(text: string): Uint8Array {
  if (typeof text !== 'string') {
    throw new CanonicalTextError(`canonicalizeText expects string, got ${typeof text}`);
  }

  rejectForbiddenCodePoints(text);

  // Stage 1: NFC normalization.
  const nfc = text.normalize('NFC');

  // Stage 2: Unicode default lowercase. JavaScript's toLowerCase() applies
  // the Default Case Conversion (no locale), matching Python's str.lower()
  // for the ASCII / common-Latin subset documented in the spec.
  const lowered = nfc.toLowerCase();

  // Stage 3: zero-width strip.
  const stripped = stripZeroWidth(lowered);

  // Stage 4: whitespace fold.
  const folded = foldWhitespace(stripped);

  return new TextEncoder().encode(folded);
}

/** SHA-256 of `canonicalizeText(text)`. Returns 32 raw bytes. */
export function textHash(text: string): Uint8Array {
  return new Uint8Array(createHash('sha256').update(canonicalizeText(text)).digest());
}

/** Lowercase hex form of `textHash`. */
export function textHashHex(text: string): string {
  const bytes = textHash(text);
  let out = '';
  for (let i = 0; i < bytes.length; i++) {
    out += (bytes[i] as number).toString(16).padStart(2, '0');
  }
  return out;
}
