<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Canonical JSON v1 — Restricted-JCS Profile

> **Status**: Specification of the v0.0.1-alpha shipped canonicalizer.
> Locked by [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md)
> and the frozen conformance vectors in
> [`sdk/python/tests/conformance/vectors.json`](../../sdk/python/tests/conformance/vectors.json).
> **Schema version**: `schema_version = 1`.
> **Authors**: @merchloubna70-dot

## Purpose

This document specifies the canonicalization profile that the Attestplane
substrate uses before computing event hashes. The spec is sufficient to
reimplement a verifier in any language without reading
`sdk/python/src/attestplane/canonical.py` or
`sdk/typescript/src/canonical.ts`. Cross-language byte-conformance is
enforced in CI against the frozen ten-vector test set; any
implementation that satisfies this spec will reproduce the published
hexadecimal hashes byte-for-byte.

The profile is intentionally narrower than RFC 8785 JSON Canonicalization
Scheme (JCS). It rejects representational ambiguity that JCS leaves open
(floats, mixed-case escapes, non-NFC strings) because those ambiguities
make audit-chain hashes drift across SDKs.

## Scope

The canonicalizer is applied to one `AuditEvent` value at a time. The
output bytes are then SHA-256-hashed to produce the event's
`event_hash`. The canonicalizer is **not** applied to the
`ChainedEvent` envelope (`seq` / `prev_hash` / `event_hash` are not
canonicalized; they live outside the hashed bytes).

## Output

The output of `canonicalize(value)` is a UTF-8 byte sequence with **no
trailing newline** and **no leading byte-order mark**. Implementations
MUST produce these bytes; emitting them through any other Unicode
encoding (e.g. UTF-16) is a profile violation.

## Type system

The profile accepts these JSON-like value kinds and forbids everything else.

| Kind | Profile rule | Encoded form |
|---|---|---|
| `null` | Allowed | `null` |
| Boolean | Allowed | `true` / `false` |
| Integer (signed 64-bit) | Allowed in `[-2^63, 2^63 - 1]` | Decimal digits; leading `-` for negatives; no leading zeros except for the literal `0` |
| Float / `NaN` / `Infinity` | **Forbidden** | n/a — raise an error |
| String (UTF-8 NFC) | Allowed; non-NFC strings rejected | See § Strings |
| Bytes | Allowed | Base64url **without** trailing `=` padding, wrapped in a JSON string |
| Datetime | Allowed if UTC-aware | RFC 3339 with **6-digit microsecond** precision and a literal `Z`, e.g. `"2026-05-17T12:00:00.000000Z"` |
| Array | Allowed | See § Arrays |
| Object (`dict` / `Map` with string keys) | Allowed | See § Objects |
| Dataclass / record | Allowed by reflection in the Python SDK; serialised as an object with field names as keys | See § Dataclasses |
| Anything else | **Forbidden** | n/a — raise an error |

Forbidden inputs MUST raise an error of name `CanonicalizationError`
(Python) or `CanonicalizationError` (TypeScript), surfacing the
JSON-pointer-like `$.path.to.offender` location of the violation.
Verifiers MUST NOT coerce or silently drop forbidden inputs.

## Integers

- Range: `[-9223372036854775808, 9223372036854775807]` (signed 64-bit).
- Encoded as the standard decimal representation produced by
  `str(int)`-equivalent in any language: no `+` sign, single leading
  `-` for negatives, no leading zeros except for the literal `0`, no
  thousands separators, no exponent notation.
- Out-of-range integers are forbidden, even if they fit in the source
  language's native arbitrary-precision integer type.

## Floats and NaN / Infinity

Forbidden. Implementations MUST reject these at canonicalization time.

Rationale: cross-platform float representation is not byte-stable
across language runtimes (e.g., 0.1 + 0.2 prints differently in Python
than in some JavaScript versions, and ECMAScript JSON.stringify rounds
differently from Python's `repr`). Forbidding floats removes the entire
class of drift bugs.

If an event needs to carry a numeric measurement, choose one of:

1. A **scaled integer** (e.g., basis points `bp` for percentages,
   smallest-currency-unit for money, microseconds for durations).
2. A **string** representation chosen by the producer
   (`"0.7853981633974483"`).
3. A SHA-256 hex of the byte representation of the raw measurement,
   carried in a separate field.

## Strings

- Must be Unicode **NFC** normalized. Non-NFC inputs are rejected.
- Encoded as a JSON string with the following escape rules:
  - Always escape `\b` (U+0008), `\t` (U+0009), `\n` (U+000A),
    `\f` (U+000C), `\r` (U+000D), `\"` (U+0022), and `\\` (U+005C)
    using the two-character escape forms listed.
  - All other code points in `[U+0000, U+001F]` (control characters)
    MUST be escaped as `\u00XX` using **lowercase hex** digits
    (``, not ``).
  - Code points U+0020 and above are emitted directly as UTF-8 bytes.
    Implementations MUST NOT additionally escape non-ASCII characters
    such as quotation marks, dashes, or fullwidth forms; the canonical
    bytes contain the literal UTF-8 encoding of the character.
  - Solidus (`/`, U+002F) is emitted unescaped.
- No surrogate code points or unpaired surrogates may appear.

### Subject-reference type

A `SubjectRef` value (Python dataclass / TypeScript object) serialises
as an object with two keys, `scheme` and `value`. The `scheme` field
takes one of three literal strings (`"sha256_salted"`, `"opaque"`,
`"none"`). When `scheme == "none"`, `value` MUST equal the empty
string.

## Bytes

- Encoded as Base64url (RFC 4648 § 5) **without** trailing `=` padding,
  wrapped in a JSON string. Example: the byte sequence `[0xAA, 0xBB]`
  serialises as `"qrs"`.
- Implementations MUST strip trailing `=` characters before emitting.

## Datetimes

- Must be timezone-aware **and** equal to UTC. Non-UTC timezone offsets
  are forbidden; the substrate forces an explicit conversion before
  recording.
- Naive datetimes (no tzinfo) are forbidden.
- Microsecond precision is **mandatory**. Sub-microsecond precision is
  not preserved. Higher-precision inputs (e.g., nanoseconds from a
  monotonic clock) MUST be truncated to microseconds before
  canonicalization, and the canonicalizer MUST NOT silently truncate.
- Encoded form: `"YYYY-MM-DDThh:mm:ss.uuuuuuZ"` where `uuuuuu` is the
  6-digit microsecond value (zero-padded). The literal `Z` is
  mandatory; `+00:00` is **not** an accepted alternative even though it
  is semantically equivalent.

Examples:

| Input | Output bytes |
|---|---|
| `datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)` | `"2026-05-17T12:00:00.000000Z"` |
| `datetime(2026, 5, 17, 12, 0, 0, 123456, tzinfo=UTC)` | `"2026-05-17T12:00:00.123456Z"` |

## Arrays

- Encoded as `[item0,item1,…,itemN-1]` with no whitespace between
  elements or around brackets.
- Element order is preserved exactly as input. Arrays of objects retain
  their input order; canonical ordering is **not** applied across array
  positions.
- Empty array: `[]`.

## Objects

- Object keys MUST be strings. Non-string keys (integers, booleans,
  `None`, etc.) are forbidden.
- Keys are sorted in **Unicode code-point ascending order** before
  emission. This is byte-comparison order over the UTF-8 encoded form
  for ASCII keys; for non-ASCII keys, implementations MUST sort by the
  sequence of code points (i.e., by the string's logical content, not
  by UTF-8 byte sequence). Note: for keys that are ASCII, code-point
  order coincides with UTF-8 byte order, so most implementations'
  default string sort works. Verifiers MUST cross-check non-ASCII key
  orderings against the conformance vector that exercises them.
- Duplicate keys are forbidden; if the input has duplicate keys after
  normalization the canonicalizer raises.
- Encoded as `{"key0":value0,"key1":value1,…}` with no whitespace
  inside.
- Empty object: `{}`.

## Dataclasses

The Python SDK accepts frozen dataclasses for events. When passed a
dataclass, the canonicalizer enumerates fields in declaration order
and constructs an equivalent dict (field name → field value), then
applies the object rules above. This means dataclass field order does
**not** affect canonical output — keys are sorted alphabetically by
field name like any other object.

The TypeScript SDK accepts plain objects with the same field names.
Both languages produce identical bytes for the same logical event.

## Object key ordering example

Input:

```python
{"z": 1, "a": 2, "m": [3, 2, 1]}
```

Canonical bytes:

```
{"a":2,"m":[3,2,1],"z":1}
```

Note that the `[3, 2, 1]` array preserves its input order; only the
top-level object's keys are sorted.

## End-of-string and trailing whitespace

There is no trailing newline, trailing whitespace, or trailing
separator in the output bytes. The output ends precisely with the
final closing bracket / brace / digit / quote of the encoded value.

## Implementation-defined extensions are forbidden

The profile is closed: no implementation may add a JSON-comments,
trailing-comma, or BSON-style binary extension. Any such extension
breaks cross-language byte conformance and is rejected on the
canonicalization layer.

## Hashing

After canonicalization, the SHA-256 digest of the output bytes is the
event's `event_hash`. SHA-256 is locked by ADR-0002 § hash algorithm;
the digest is 32 bytes (256 bits). Lowercase hexadecimal is the
recommended human-readable form; the canonical wire form is bytes,
and any encoding (hex / base64 / base64url) is acceptable provided
it round-trips losslessly.

## Versioning

The profile is `schema_version = 1`. Any byte-level change to the
profile — additional escape characters, different microsecond
precision, alternative key-ordering rules, additional type support —
is a **breaking change** that requires a new `schema_version` value
and a new frozen vector set under a new filename.

ADR-0002 § immutability invariant prevents in-place mutation of
`vectors.json` for any reason. The `schema_version` bump is the only
permitted path to evolve the profile.

## Conformance

A conforming implementation MUST:

1. Reproduce the `event_hash_hex` and `canonical_bytes_sha256_hex`
   value for each of the ten entries in `vectors.json` byte-for-byte.
2. Reject every type in the "Forbidden" rows above with a
   `CanonicalizationError`-named exception.
3. Reject non-NFC strings with the same error.
4. Reject non-UTC datetimes with the same error.
5. Reject duplicate object keys with the same error.

Tests in `sdk/python/tests/test_canonical.py` and
`sdk/typescript/test/canonical.test.ts` exercise items 2–5; the
cross-language conformance tests
(`sdk/python/tests/test_conformance.py`,
`sdk/typescript/test/conformance.test.ts`) exercise item 1.

## Cross-references

- [ADR-0002 — Substrate core data model and hash chain (v0.0.1)](../adr/0002-substrate-data-model-and-hash-chain-v0.md)
- [`sdk/python/src/attestplane/canonical.py`](../../sdk/python/src/attestplane/canonical.py) — Python reference implementation
- [`sdk/typescript/src/canonical.ts`](../../sdk/typescript/src/canonical.ts) — TypeScript reference implementation
- [`sdk/python/tests/conformance/vectors.json`](../../sdk/python/tests/conformance/vectors.json) — frozen happy-path vector set
- [`sdk/python/tests/conformance/negative/`](../../sdk/python/tests/conformance/negative/README.md) — frozen broken-chain vectors
- RFC 8785 — JSON Canonicalization Scheme (the broader profile this one restricts)
- RFC 3339 — Date and Time on the Internet (timestamp format)
- RFC 4648 § 5 — Base64url encoding (bytes encoding)
- Unicode Standard, Annex #15 — Unicode Normalization Forms (NFC)
