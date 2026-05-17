<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Canonical Text v1 — Cross-Language Text Hash

> **Status**: Specification of the canonical-text primitive shipped on
> `main` (not yet in a published artifact).
> Conformance vectors frozen at
> [`sdk/python/tests/conformance/text_vectors.json`](../../sdk/python/tests/conformance/text_vectors.json).
> **Schema version**: `text_schema_version = 1`.
> **Authors**: @merchloubna70-dot

## Purpose

A second, independent canonicalization primitive alongside
[canonical-json-v1](canonical-json-v1.md). The text canonicalizer
normalizes a single free-form string so that two semantically-equivalent
inputs hash identically. It is the substrate's answer to common
typographic ambiguity: case differences, accent decomposition,
invisible characters, and inconsistent whitespace.

Use cases:

- **Actor-string deduplication** — `"agent_alpha"` ≡ `"Agent_Alpha"` ≡
  `"agent​_alpha"` (with a ZWSP) all hash to the same value.
- **SubjectRef value normalization** — when an adapter's pseudonymization
  scheme takes a raw identifier as input, normalizing it through this
  primitive before hashing avoids accidental drift across deployments.
- **Free-text reason hashing** — short human-authored reason strings
  embedded in `policy_check_event.payload.decision_reason_hash` survive
  trivial editorial whitespace changes without re-hashing.

The primitive is **not** a fuzzy matcher: it does not remove
punctuation, does not transliterate, does not remove diacritics
(beyond NFC composition). Those operations are lossy in ways that
obscure compliance evidence. NFC normalization is the only
diacritic-level operation, and it preserves all visual information.

## Algorithm

```
canonicalize_text(text: str) -> bytes
    1. Reject forbidden inputs.
    2. NFC normalize.
    3. Unicode default lowercase.
    4. Strip zero-width characters.
    5. Fold whitespace.
    6. Encode as UTF-8.
```

### Stage 0 — Reject forbidden inputs

The following inputs are rejected with `CanonicalTextError`:

| Input | Reason |
|---|---|
| Non-string types | The primitive is text-only; binary normalization needs `bytes`. |
| Strings containing U+0000 (null) | Null bytes terminate strings in many languages and are a smuggling vector. |
| Strings containing unpaired surrogates (U+D800–U+DFFF, not part of a valid surrogate pair) | Not representable in valid UTF-8; would corrupt downstream hashes. |

Paired surrogates (correctly encoding astral-plane characters like
emoji) are accepted.

### Stage 1 — NFC normalize

Apply Unicode Normalization Form C: canonical decomposition followed by
canonical composition. This collapses decomposed sequences like
`"e" + U+0301` (combining acute) into the single code point `U+00E9`.

Reference implementations:

- Python: `unicodedata.normalize("NFC", text)`
- TypeScript: `text.normalize("NFC")`
- Both use the Unicode Consortium's standard NFC algorithm.

### Stage 2 — Unicode default lowercase

Apply the Unicode Default Case Conversion algorithm (`toLowerCase`
without locale).

Reference implementations:

- Python: `str.lower()`
- TypeScript: `String.prototype.toLowerCase()` (no `locale` argument)

Both consume the Unicode Default Case Folding table. They produce
byte-identical output for the conformance-vector subset (see § Cross-language
stability below).

### Stage 3 — Strip zero-width characters

Remove all occurrences of the following four code points:

| Code point | Name |
|---|---|
| U+200B | ZERO WIDTH SPACE |
| U+200C | ZERO WIDTH NON-JOINER |
| U+200D | ZERO WIDTH JOINER |
| U+FEFF | ZERO WIDTH NO-BREAK SPACE (BOM) |

These four are commonly used to defeat string comparison without
visible change.

### Stage 4 — Fold whitespace

- Split the string on any run of Unicode whitespace (i.e., characters
  in the Unicode `\s` class, which includes ASCII space/tab/newline,
  ideographic space U+3000, no-break space U+00A0, etc.).
- Discard empty parts (handles leading/trailing whitespace).
- Rejoin parts with a single ASCII space (U+0020).

Reference implementations:

- Python: `" ".join(text.split())`
- TypeScript: `text.split(/\s+/u).filter(s => s.length > 0).join(" ")`

### Stage 5 — UTF-8 encode

The output of canonicalize_text is the UTF-8 byte sequence of the
normalized string.

## Hash

`text_hash(text) = SHA-256(canonicalize_text(text))` — 32 raw bytes.
`text_hash_hex(text)` is the lowercase hex form (64 chars).

SHA-256 is locked by alignment with the canonical-JSON primitive (which
itself locks SHA-256 per [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md)).
Changing this hash function is a v2 schema bump.

## Cross-language stability

The conformance vector set
([`sdk/python/tests/conformance/text_vectors.json`](../../sdk/python/tests/conformance/text_vectors.json),
12 vectors at v1) exercises the byte-stable subset of inputs:

- ASCII letters (lowercase, uppercase, mixed)
- Common Latin-1 supplement characters with NFC decomposition
- CJK characters (passthrough through lowercase)
- All four zero-width characters
- ASCII whitespace + ideographic space U+3000

Edge cases NOT covered by v1 vectors (use at your own risk; behavior may
differ between Python and TypeScript reference implementations):

| Input | Concern |
|---|---|
| German sharp s (`ß`) | Python `str.lower()` leaves it as `ß`; some lowercase implementations produce `"ss"`. Both Python and TS reference implementations leave it as `ß`, but the v1 spec does not freeze this behaviour. |
| Turkish dotted-i (`İ`, `I`, `ı`, `i`) | Locale-sensitive in some implementations. Default (non-locale) `toLowerCase` matches; do not pass locale arguments. |
| Certain Greek case mappings (e.g., final sigma `ς` vs medial `σ`) | Default case conversion preserves these; do not use casefold for v1. |

A future v2 may freeze a wider stability set with explicit per-character
disposition. Until then, callers depending on byte stability for
European-language inputs should run their inputs through both
reference implementations once as a smoke test.

## Conformance

A conforming implementation MUST:

1. Reproduce every `canonical_utf8_hex` and `text_hash_hex` value in
   `text_vectors.json` byte-for-byte.
2. Reject every forbidden input listed in § Stage 0 with an error
   named `CanonicalTextError` (Python: class; TypeScript: class).
3. Apply the four stages in the order listed.
4. Use SHA-256 for the hash function.

The Python implementation lives at
[`sdk/python/src/attestplane/canonical_text.py`](../../sdk/python/src/attestplane/canonical_text.py).
The TypeScript implementation lives at
[`sdk/typescript/src/canonical_text.ts`](../../sdk/typescript/src/canonical_text.ts).
Both replay the same `text_vectors.json` on every CI run; cross-language
drift fails CI.

## Independence from canonical-JSON v1

The text canonicalizer is independent of the JSON canonicalizer:

- Different input type (string, not arbitrary JSON value).
- Different output: text returns the canonical UTF-8 bytes of one
  string; JSON returns the canonical UTF-8 bytes of a structured value.
- Different version number: `text_schema_version = 1` evolves
  separately from the JSON `schema_version = 1` locked in ADR-0002.

The text primitive does NOT appear inside the canonicalize() call used
by `event_hash` computation. Adapters and callers can use it
voluntarily, but it does not affect the substrate's chain-hash
contract; the chain hash continues to use only canonical-JSON.

## Cross-references

- [`sdk/python/src/attestplane/canonical_text.py`](../../sdk/python/src/attestplane/canonical_text.py)
- [`sdk/typescript/src/canonical_text.ts`](../../sdk/typescript/src/canonical_text.ts)
- [`sdk/python/tests/conformance/text_vectors.json`](../../sdk/python/tests/conformance/text_vectors.json) — frozen vectors
- [`canonical-json-v1.md`](canonical-json-v1.md) — sibling JSON primitive
- [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md) — substrate hash-chain hash function (SHA-256, shared with text primitive)
- Unicode Standard Annex #15 — Unicode Normalization Forms (NFC)
- Unicode Standard § 3.13 — Default Case Algorithms
