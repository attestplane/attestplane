# 0010. Verification reason_code enum — machine-readable verification findings

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer; self-signed acceptance per GOVERNANCE.md § 6.2)
- **Related**: [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0003](0003-tsa-rfc-3161-anchoring.md), [ADR-0005](0005-event-signing-scheme.md), [ADR-0008](0008-evidence-event-taxonomy-v1.md), [ADR-0009](0009-aios-absorption-boundary.md), [`docs/validation/aios_to_attestplane_absorption_audit_20260517.md`](../validation/aios_to_attestplane_absorption_audit_20260517.md) § D.3

## Context

The current `VerificationResult` shape in `attestplane.hashchain`
(Python) and `hashchain.ts` (TypeScript) carries verification findings
as `reason: str | None` — a free-text human-readable string. Examples
of strings that actually appear in `verify_chain()`:

- `"seq mismatch at index 4: got 5, expected 4"`
- `"prev_hash mismatch at seq 3"`
- `"event_hash mismatch at seq 2"`

These are **operator-grade messages**, suitable for a human reading
the log. They are **not** suitable for:

1. Machine consumption by downstream auditor / compliance / regulator
   tooling that needs to branch on the *kind* of failure (e.g. "did
   the chain fail because of hash drift, or because an anchor cert
   expired?").
2. Cross-language byte-stable comparison (a free-text Python string
   and a free-text TypeScript string will diverge over time even when
   describing the same finding).
3. EU AI Act Article 12 "automatic recording of events" obligation
   evidence-pack consumers, who expect machine-readable failure
   classification when constructing audit reports.

ADR-0009 § D.3 identified this as a **blocking** gap for Phase 2.
This ADR lands the foundational primitive — a stable
machine-readable enum — without modifying the existing
`VerificationResult` shape. Threading the new enum into the existing
verifier return paths is sequenced into a follow-up ADR (likely
ADR-0015) so the current ADR can ship as additive-only.

## Decision

### 1. `ReasonCodeV1` — stable string enum

A new module `attestplane.reason_codes` (Python) and
`reason_codes.ts` (TypeScript) defines the v1 enum as a closed
literal set. Each enum value is:

- Uppercase ASCII with underscores. Regex: `^[A-Z][A-Z0-9_]{1,63}$`.
- Stable forever within v1 (frozen alongside `reason_code_schema_version = 1`).
- Documented with a single sentence of intent and the verifier path
  that emits it.

### 2. `reason_code_schema_version = 1`

This is the **fourth** independent schema-version counter in the
substrate:

| Counter | Source | Frozen in |
|---|---|---|
| `chain.schema_version` | ADR-0002 | v0.0.1-alpha vectors.json |
| `anchor_schema_version` | ADR-0003 | v0.0.2-alpha |
| `signature_schema_version` | ADR-0005 | v0.0.2-alpha signature_vectors.json |
| **`reason_code_schema_version`** | **this ADR** | **v0.0.2-alpha (Phase 2)** |

Independence is invariant 5 of ADR-0009. Bumping any counter requires
its own ADR amendment.

### 3. v1 enum value set

The v1 set is the smallest closure that covers the verifier paths
that exist in this repo today (`verify_chain`, signature verifier,
anchor verifier, payload validators). New values may be added in v2
(with a new `reason_code_schema_version = 2`); the v1 values listed
here are frozen.

#### Chain integrity (from `verify_chain`)

- `CHAIN_OK` — chain integrity verified end-to-end.
- `CHAIN_SEQ_MISMATCH` — `chained_event.seq` does not equal expected position.
- `CHAIN_PREV_HASH_MISMATCH` — `chained_event.prev_hash` does not equal previous event's `event_hash`.
- `CHAIN_EVENT_HASH_MISMATCH` — `chained_event.event_hash` does not equal `hash_event(audit_event)` (canonicalize bytes drift).

#### Signature verification (from `verify_chain_with_signatures`, ADR-0005)

- `SIGNATURE_OK` — signature verified.
- `SIGNATURE_INVALID` — Ed25519 verify failed (cryptographic mismatch).
- `SIGNATURE_UNKNOWN_KEY` — `key_id` not present in trust roots.
- `SIGNATURE_EXPIRED_KEY` — verification_time outside trust-root entry's validity window.
- `SIGNATURE_SCHEMA_MISMATCH` — `signature_schema_version` unsupported.
- `SIGNATURE_PAYLOAD_MISMATCH` — `signed_payload` bytes do not match re-canonicalised expected payload.

#### Anchor verification (from `verify_chain_with_anchors`, ADR-0003 + ADR-0006)

- `ANCHOR_OK` — anchor verified including LTV.
- `ANCHOR_INVALID` — anchor signature / hash / format check failed.
- `ANCHOR_CERT_EXPIRED` — TSA cert chain expired at verification_time.
- `ANCHOR_OCSP_FAILED` — OCSP response invalid / revoked / missing.
- `ANCHOR_MISSING_LTV_ARTIFACTS` — `tsa_cert_chain` or `ocsp_responses` empty (CAdES-A LTV unsupported).

#### Payload validators (from `event_payloads.py/ts`)

- `PAYLOAD_OK` — payload validates against its `<event>_schema`.
- `PAYLOAD_MISSING_REQUIRED_FIELD` — required field absent.
- `PAYLOAD_FIELD_TYPE_MISMATCH` — field present but wrong type.
- `PAYLOAD_FIELD_VALUE_OUT_OF_RANGE` — field within type but outside spec'd value set (enum / regex / numeric range).
- `PAYLOAD_FORBIDDEN_FIELD_PRESENT` — ADR-0004 § 2 redaction violation (e.g. `signature`, `expression` body).
- `PAYLOAD_SCHEMA_VERSION_MISMATCH` — payload's own `<event>_schema_version` unsupported.

#### Cross-cutting

- `UNSIGNED_SEGMENT` — bundle contains no signature records (per ADR-0005 plurality).
- `UNANCHORED_SEGMENT` — bundle contains no anchor records.
- `BUNDLE_MISSING_REQUIRED_FIELD` — top-level bundle field absent.
- `INTERNAL_ERROR` — verifier hit an unexpected condition (logged for debugging; should not occur in conformant input).

### 4. Backward-compatibility — `VerificationResult.reason: str` stays

The existing `VerificationResult.reason` free-text field stays as the
authoritative human-readable description. Callers that already log
`result.reason` continue to work without code changes.

Future threading of `reason_code` into the verifier return shape
(via a new optional field or wrapper type) is **out of scope for
this ADR** and is sequenced into a follow-up ADR. Reasons:

- This ADR ships the enum primitive alone, with zero changes to
  `hashchain.VerificationResult`. Risk surface is minimal.
- Threading touches multiple verifier paths (chain / signature /
  anchor / bundle / payload validators); each path has its own
  return-shape considerations.
- Splitting the work allows the enum to be reviewed independently of
  any return-shape API design choices.

### 5. Helper API surface (this ADR)

```python
# attestplane.reason_codes
REASON_CODE_SCHEMA_VERSION: Final[int] = 1

ReasonCodeV1 = Literal[
    "CHAIN_OK", "CHAIN_SEQ_MISMATCH", ...
]

ALL_REASON_CODES_V1: frozenset[str] = frozenset({...})

REASON_CODE_DESCRIPTIONS: Mapping[str, str] = {
    "CHAIN_OK": "Chain integrity verified end-to-end.",
    ...
}

def is_known_reason_code(code: str) -> bool: ...
```

The TypeScript mirror exposes the same constants with TS-native types.

## Consequences

### Positive

- Downstream tooling (audit reports, EU AI Act Article 12 evidence
  packs, regulator dashboards) can branch on `reason_code` instead
  of regex-matching free-text strings.
- Cross-language byte stability: the enum is byte-identical between
  Python and TypeScript SDKs.
- Independent `reason_code_schema_version = 1` decouples enum
  evolution from chain / anchor / signature schema evolution. Adding
  a new reason code in v2 does not invalidate v1 chains or bundles.
- ADR-0009 invariant 13 ("CI-enforced `$id` discipline") extends
  trivially: any future ReasonCodeV1 schema file (e.g. JSON Schema
  for evidence-pack `reason_code` fields) will be authored under
  `https://attestplane.io/schemas/v1/`.

### Negative

- Two parallel surfaces (free-text `reason` + machine-readable
  `reason_code`) until the threading ADR lands. Callers must
  understand which to use.
- The enum value set must be maintained by hand in two languages.
  Mitigated by the cross-language unit test that asserts Python and
  TypeScript enum sets are equal.

### Risks accepted

- The enum value set will need expansion as new verifier paths are
  added. v1 freeze means expansion requires a new ADR + new
  `reason_code_schema_version = 2`. This is intentional — the cost
  of "wait for v2 ADR" is the price of byte stability.
- Some verifier failures legitimately span multiple categories (e.g.
  a missing `signing_cert_chain` could be `SIGNATURE_INVALID`,
  `ANCHOR_MISSING_LTV_ARTIFACTS`, or `BUNDLE_MISSING_REQUIRED_FIELD`).
  Resolved by the path-specific naming (`SIGNATURE_*`, `ANCHOR_*`,
  `PAYLOAD_*`) — the verifier code path that emits the reason code
  determines the prefix.

### Reversibility

- Adding new enum values in v2 requires a new ADR but does not break
  v1 consumers (they will see an unknown code and SHOULD treat as
  `INTERNAL_ERROR` for forward compatibility).
- Removing an enum value in v2 is breaking and requires the same
  deprecation discipline as removing a v1 conformance vector — i.e.
  generally not done.

## Alternatives considered

### Alt-A. Modify `VerificationResult.reason` to be a structured object `{code, message}`

Rejected. Changes the shape of an already-published return type;
every existing caller that reads `result.reason` as a string would
break. The current decomposition (this ADR ships the enum; a
follow-up ADR adds the threading) preserves backward compatibility.

### Alt-B. Use HTTP-style numeric codes

Rejected. Numeric codes are opaque (a reader must consult a table
to interpret `42`). Stable string codes self-document in logs.

### Alt-C. Skip the enum; just normalise the free-text strings

Rejected. Free-text normalisation drifts over time; a closed enum
with CI-enforced membership is a stronger guarantee.

### Alt-D. Per-verifier-module enums (separate `chain_reason_code`, `anchor_reason_code`, ...)

Rejected. A single flat enum makes cross-verifier rollup (e.g. "what
% of failures were anchor-related?") trivial. The naming convention
(prefix per verifier path) preserves readability.

## Compatibility with existing conformance vectors

This ADR is **fully additive**:

- `vectors.json` (v0.0.1-alpha 10 chain vectors) — unchanged.
- `text_vectors.json` (12 vectors) — unchanged.
- `signature_vectors.json` (5 vectors) — unchanged.
- `lease_lifecycle_event_vectors.json` (P0.1) — unchanged.
- `policy_check_event_vectors.json` (P0.2) — unchanged.

No existing test changes its assertion shape. The new
`reason_codes_vectors.json` (this ADR) is a topic-segregated file
asserting only that the enum set is Py/TS byte-identical and that
each value matches the documented regex.

## Implementation status

Accepted 2026-05-17. Companion artefacts in this commit:

- `sdk/python/src/attestplane/reason_codes.py` — Python module
  defining `ReasonCodeV1` literal type, `ALL_REASON_CODES_V1`
  frozenset, `REASON_CODE_DESCRIPTIONS` mapping, `is_known_reason_code`
  predicate, `REASON_CODE_SCHEMA_VERSION = 1`.
- `sdk/typescript/src/reason_codes.ts` — TypeScript mirror.
- `sdk/python/tests/conformance/reason_codes_vectors.json` — frozen
  enum-set conformance vector (Py + TS replay byte-identical).
- Python + TypeScript unit + conformance tests.

Phase 2 follow-ups deferred to subsequent ADRs:

- **ADR-0015 (anticipated)** — threading `reason_code` into
  `VerificationResult` / `BundleVerificationResult` /
  `SingleSignatureResult` / `SingleAnchorResult` return shapes.
- **Optional `reason_code` field in payload schemas** — already
  defined in `lease_lifecycle_event.schema.json` (P0.1) and
  `policy_check_event.schema.json` (P0.2). Validators currently
  accept any matching-regex string; once ADR-0015 lands, the field
  may be tightened to `ReasonCodeV1`.
