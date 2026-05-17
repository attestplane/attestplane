# 0011. Canonical-text v1 — sibling primitive of canonical-JSON, Attestplane as source of truth

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer; self-signed acceptance per GOVERNANCE.md § 6.2)
- **Related**: [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0009](0009-aios-absorption-boundary.md) (A.2 independent convergence), [`docs/spec/canonical-text-v1.md`](../spec/canonical-text-v1.md), [`docs/spec/canonical-json-v1.md`](../spec/canonical-json-v1.md)

## Context

[ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md) locks the
canonical-JSON primitive in `attestplane.canonical` (Python) +
`canonical.ts` (TypeScript). The substrate ships a **second**
canonicalization primitive for *text*, intentionally separate from
JSON canonicalization:

- `attestplane.canonical_text` (Python)
- `canonical-text.ts` (TypeScript)
- 12 frozen conformance vectors in
  `sdk/python/tests/conformance/text_vectors.json` (shared by both
  SDKs)

The text canonicalizer is used by payload-side helpers — actor
identifiers, free-text reasons hashed before embedding in
`policy_check_event.expression_hash`, framework citations — where two
strings can be *semantically equal* while being *byte-different* due
to NFC vs. NFD form, lowercase vs. uppercase, embedded zero-width
characters, or runs of differently-spaced whitespace.

The technical specification has shipped at
[`docs/spec/canonical-text-v1.md`](../spec/canonical-text-v1.md) since
the v0.0.2-alpha release candidate. **No ADR has formally accepted
the primitive into the substrate's contract surface.** That ADR is
this one.

ADR-0009 also surfaces a second question this ADR answers: when AIOS
ships a parallel implementation at `~/aios/crates/aios-canonical/src/canonical.rs`,
which side is **the source of truth**? Per ADR-0009 § 1 Mode A.2
(independent convergence), the Attestplane spec is canonical — AIOS
must align to it, not the reverse, to prevent directional dependency
violation per ADR-0004 § 4.

## Decision

### 1. Locked algorithm — four stages

The text canonicalizer is the deterministic four-stage transformation
on a Unicode string, locked here and detailed in
[`docs/spec/canonical-text-v1.md`](../spec/canonical-text-v1.md):

| Stage | Operation | Library |
|---|---|---|
| 1 | **NFC normalize** — Unicode Canonical Decomposition followed by Canonical Composition | `unicodedata.normalize("NFC", s)` (Py) / `s.normalize('NFC')` (TS) |
| 2 | **Unicode default lowercase** | `str.lower()` (Py) / `s.toLowerCase()` (TS) |
| 3 | **Zero-width strip** — remove U+200B / U+200C / U+200D / U+FEFF | per-character filter |
| 4 | **Whitespace fold** — collapse any run of Unicode whitespace into single ASCII space (U+0020); trim leading + trailing | `" ".join(s.split())` (Py) / regex (TS) |

Output: UTF-8 bytes. `text_hash(s) := SHA-256(canonicalize_text(s))`,
32 raw bytes; `text_hash_hex(s)` is the lowercase 64-char hex form.

### 2. Reject inputs — three classes

The canonicalizer raises `CanonicalTextError` for:

- **Non-string input** (rejected at type boundary).
- **Strings containing U+0000 NULL** — null bytes are a smuggling
  vector and have no defensible canonical form.
- **Strings containing unpaired surrogates U+D800–U+DFFF** — not
  valid UTF-8; would fail at encode time anyway, so reject early.

### 3. Conformance vectors are frozen at 12 entries

`sdk/python/tests/conformance/text_vectors.json` ships 12 vectors
covering:

- ASCII pass-through (NFC + lowercase = no-op for ASCII letters)
- Combining-mark NFC normalisation (`"é"` → `"é"`)
- Case folding (`"Hello"` → `"hello"`)
- Zero-width character stripping
- Whitespace folding (tabs / newlines / NBSP / multiple-space runs)
- Combined transformations (all four stages firing)
- Error cases (null byte / unpaired surrogate)

The 12 vectors are **immutable** under v1 — same discipline as
`vectors.json` (ADR-0002), `text_vectors.json` itself locked here,
`signature_vectors.json` (ADR-0005), and the topic-segregated v1
payload vectors landed under P0.1 / P0.2.

Adding new conformance vectors does NOT require an ADR — a new
positive vector for a previously-untested input is additive. **Modifying
or removing an existing vector** requires a new ADR superseding this
one.

### 4. Attestplane is the source of truth (cross-language posture)

The text canonicalizer's algorithm and conformance vectors are
authored by Attestplane and frozen here. Other systems — including
AIOS's parallel `aios-canonical/src/canonical.rs` (~218 LOC) — are
either:

- **Independent convergence** (ADR-0009 Mode A.2): the other system
  implements the same four-stage algorithm independently; conformance
  is asserted by replaying Attestplane's `text_vectors.json` byte-for-byte.
- **Downstream consumer**: the other system imports Attestplane's
  Python SDK or TypeScript SDK and uses `canonicalize_text` /
  `canonicalizeText` directly. ADR-0004 § 4 single-direction
  dependency permits this.

In either case, Attestplane does NOT depend on the other system's
spec or implementation. Per ADR-0009 invariant 13 (`$id` discipline),
any future JSON Schema for canonical-text artefacts MUST be issued
under `https://attestplane.io/schemas/v1/`.

### 5. Independent schema version

Canonical-text has no top-level schema version field (the function
operates on raw strings); the implicit version is tied to this ADR's
acceptance. A future v2 — e.g. adding diacritic stripping, or
switching NFC → NFKC — requires a new ADR superseding this one and
introduces `canonical_text_v2` as a separate function. v1 callers
continue to work via the original function name.

This is the same versioning posture as canonical-JSON (ADR-0002).

## Consequences

### Positive

- Payload-side helpers can call `canonicalize_text(s)` /
  `canonicalizeText(s)` with the confidence that the result is
  cross-language byte-identical, EU AI Act audit-friendly, and won't
  silently drift as Python / Node minor versions advance.
- ADR-0009 Mode A.2 ("independent convergence") gains a concrete
  precedent: if AIOS ships a canonical-text implementation, this ADR
  is what Attestplane points to as the spec.
- Verifiers can cross-check that an externally-supplied
  `expression_hash` (in `policy_check_event` payload) matches
  `text_hash(<the supplied expression body>)` without depending on
  the producer's choice of whitespace / case / NFC form.

### Negative

- Two parallel canonicalizers (JSON + text) in the substrate. Reviewers
  must know which to use when. Mitigated by clear function naming
  (`canonicalize` for JSON, `canonicalize_text` for text) and by the
  spec documents enumerating use cases.
- Lowercase folding has Unicode edge cases (Turkish dotted/dotless I,
  German sharp S, some Greek mappings). Mitigated by the
  `text_vectors.json` conformance set — any cross-language drift
  surfaces immediately in CI.

### Risks accepted

- Some payloads will canonicalize identically when semantically
  different (e.g., `"García"` and `"GARCIA"` after fold both → `"garcia"`).
  Acceptable because the canonicalizer is for *hash comparison*, not
  *identity disambiguation*. Callers who need identity should not use
  text canonicalization; they should hash structured identifiers
  (`uuidv7`, `subject_ref`, etc.).
- ICU / Node `String.prototype.toLowerCase` mappings can in principle
  evolve across Unicode versions. The `text_vectors.json` set pins
  the v1 mapping; if a future Node release diverges, CI will fail
  before that release is adopted.

### Reversibility

- Removing the canonicalizer entirely is a breaking change for
  payload-side helpers; not anticipated. A future v2 ADR may add new
  functions (`canonicalize_text_v2`) but does not remove v1.

## Alternatives considered

### Alt-A. Reuse JSON canonicalizer for text by wrapping the string in `[s]` and canonicalizing the array

Rejected. JSON canonicalization is byte-stable but does not apply
NFC / case folding / zero-width strip / whitespace folding. The two
operations serve different purposes (byte stability for *structured*
input vs. semantic stability for *free-form* input).

### Alt-B. Use ICU directly via a native binding

Rejected. Adds a heavy native dependency (ICU is large; binding to
Python / Node both is significant maintenance). Python `unicodedata`
+ Node ICU defaults are sufficient for v1; if a customer requires
non-default Unicode behaviour, ADR-0011 v2 can re-evaluate.

### Alt-C. NFKC instead of NFC

Rejected. NFKC is **K**ompatibility decomposition — it folds
characters that look similar but are encoded differently (e.g.,
fullwidth Latin letters → halfwidth). That's lossy in ways that
matter for audit (a fullwidth-Latin-letter actor name is forensically
different from a halfwidth one). v1 stays at NFC.

### Alt-D. Defer the ADR and let `canonical-text-v1.md` spec doc be the contract

Rejected. ADR-0009 explicitly identifies this gap (P1.3 in the
audit's roadmap): the spec doc exists but no ADR formally accepts
the primitive. Future contributors / external auditors expect an ADR
trail for every load-bearing contract; deferring leaves a hole.

## Compatibility with existing conformance vectors

This ADR is **fully additive**:

- `vectors.json` (v0.0.1-alpha 10 chain vectors) — unchanged.
- `text_vectors.json` (12 vectors) — unchanged; this ADR formally
  freezes the existing set.
- `signature_vectors.json` (5 vectors) — unchanged.
- `lease_lifecycle_event_vectors.json` (P0.1) — unchanged.
- `policy_check_event_vectors.json` (P0.2) — unchanged.
- `reason_codes_vectors.json` (P0.3) — unchanged.

No code changes are required to accept this ADR. The Python +
TypeScript implementations and the spec doc all already match the
locked algorithm.

## Implementation status

**Accepted 2026-05-17.** The implementation has been live since
v0.0.2-alpha release-candidate stage:

- `sdk/python/src/attestplane/canonical_text.py` — 125 LOC
- `sdk/typescript/src/canonical_text.ts` — TypeScript mirror
- `sdk/python/tests/conformance/text_vectors.json` — 12 frozen vectors
- `docs/spec/canonical-text-v1.md` — full technical spec
- `sdk/python/tests/test_canonical_text.py` + TypeScript counterpart
  — replay tests passing for both SDKs

This ADR formally locks the algorithm + the 12-vector set + the
"Attestplane as source of truth" posture. No code or fixture changes
land under this ADR.

## Follow-up

If a future ADR adds new evidence-event payload schemas whose
fields require hashing (e.g., a hypothetical `audit_summary_hash`
field), the text canonicalizer is the recommended primitive. Schema
authors SHOULD cite this ADR in the field's `$comment` when they
require canonical-text inputs.
