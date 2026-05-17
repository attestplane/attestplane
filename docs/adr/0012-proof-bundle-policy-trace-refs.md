# 0012. ProofBundle.policy_trace_refs — surface policy_check_event hashes for auditor consumption

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer; self-signed acceptance per GOVERNANCE.md § 6.2)
- **Related**: [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0005](0005-event-signing-scheme.md), [ADR-0008](0008-evidence-event-taxonomy-v1.md), [ADR-0009](0009-aios-absorption-boundary.md) (A.8 + D.2), [`docs/validation/aios_to_attestplane_absorption_audit_20260517.md`](../validation/aios_to_attestplane_absorption_audit_20260517.md)

## Context

[P0.2](0009-aios-absorption-boundary.md) landed the
`policy_check_event` payload (ADR-0009 A.8). An auditor or regulator
walking a `ProofBundle` for a long chain needs to answer the question
"which seqs in this chain carried a policy decision?" without
having to scan every event payload's `event_type` field.

ADR-0009 § D.2 identified this as a **blocking** gap for M5 (the
August 2026 EU AI Act release). The fix is to surface a
**flat list of SHA-256 references** to `policy_check_event` rows at
the top level of `ProofBundle`. The references are 32-byte
`event_hash` values that already exist on each `ChainedEvent`; the
bundle simply exposes them in an additive top-level array so
verifiers can index into the events list without re-walking.

The same pattern works for any future "give me a quick index of
events of type X" use case. This ADR ships the policy-trace case
and notes the pattern is the discipline for future ADRs (e.g.,
`lease_trace_refs`, `replay_trace_refs`) without committing to
landing them now.

## Decision

### 1. New optional field `ProofBundle.policy_trace_refs`

The `proof_bundle.schema.json` gains a new optional top-level array
field:

```json
{
  "policy_trace_refs": {
    "type": "array",
    "items": {
      "type": "string",
      "pattern": "^[0-9a-f]{64}$"
    },
    "uniqueItems": true,
    "maxItems": 65536
  }
}
```

Semantics:

- Each entry is the **`event_hash_hex`** (lowercase, 64-char) of a
  `ChainedEvent` whose `event_type == "policy_check_event"`.
- The list is **ordered by chain seq ascending** (deterministic
  iteration order for byte-stable serialisation).
- The list contains **no duplicates** (per-seq uniqueness; an event
  hash uniquely identifies its event).
- The list is **absent** (not empty array) when no
  `policy_check_event` appears in the chain. This preserves byte
  identity with v0.0.1-alpha bundles that don't yet contain
  policy_check_event rows.

### 2. Builder API

`ProofBundleBuilder.build()` computes the list automatically by
walking `self.events` once and filtering by `event_type`. No new
public method on the builder; callers do not need to manage the
list explicitly. This avoids the failure mode where a caller adds
the events but forgets to populate `policy_trace_refs`.

Pseudocode (Python):

```python
def build(self, *, now=None) -> dict[str, Any]:
    ...
    policy_refs = [
        ev.event_hash.hex()
        for ev in self.events
        if ev.event.event_type == POLICY_CHECK_EVENT
    ]
    return {
        ...existing fields...,
        **({"policy_trace_refs": policy_refs} if policy_refs else {}),
    }
```

TypeScript builder mirrors this.

### 3. Backward compatibility — strictly additive

- Bundles built before this ADR (no policy_check_event rows) emit
  bundles that **do not contain** the `policy_trace_refs` key.
  Existing consumers see no diff.
- Bundles built **after** this ADR with no policy_check_event rows
  also do not contain the key.
- Bundles built after this ADR **with** policy_check_event rows
  contain the new key with non-empty ordered hash list.

This is identical to the discipline used by ADR-0005 T5 (additive
`signatures` field).

### 4. Why a flat list, not nested structure

Alternatives considered:

| Option | Decision |
|---|---|
| Flat `list[hex-string]` (chosen) | Simplest. O(1) verifier indexing. No new schema for nested keys. |
| List of `{seq, event_hash_hex, policy_id, decision}` rich rows | Duplicates payload data; risks drift if payload changes. Rejected. |
| Map `{policy_id: [event_hashes]}` | Forces verifiers to walk all keys to count total decisions. Rejected. |
| New `policy_index` top-level schema | Over-engineered for v1. Rejected. |

The flat list lets the verifier do `bundle["policy_trace_refs"].length`
to count policy decisions, or iterate hashes and use them to lookup
into `bundle["events"]` via a precomputed `{event_hash_hex: index}`
map.

### 5. Not in scope (future ADRs)

- `lease_trace_refs` — same pattern for `lease_lifecycle_event`. Not
  shipped here because no concrete consumer has asked. Will follow
  this ADR's pattern if added.
- `replay_trace_refs` — same pattern for `replay_event`. Same posture.
- `policy_decision_trace` (nested rich form) — explicitly rejected
  (alternative 2 above).
- Threading `policy_trace_refs` consumption into the v1 verifier's
  return shape — separate concern; verifier already reads `events[]`
  and can re-derive the list if needed.

## Consequences

### Positive

- Auditor tooling (EU AI Act Article 13 transparency reports;
  regulator dashboards) gains a top-level index of policy decisions
  in O(1) rather than O(n) chain walk.
- The discipline of "surface event-type-X refs as an additive
  top-level array" becomes the official pattern for future ADRs.
- Builder-side automatic population eliminates a class of
  caller-error bugs (forgetting to maintain the list).

### Negative

- A second representation of policy_check_event existence (the
  events list + this index). Verifiers comparing the two should
  pass; if they diverge, the producer has a builder bug. Mitigated
  by the builder-side automatic population.
- ProofBundle wire shape grows by ~10–100 bytes per
  `policy_check_event` (each hex SHA-256 + separator). Negligible
  for realistic chain sizes; the `maxItems: 65536` cap is the
  practical safety limit.

### Risks accepted

- The byte ordering of `policy_trace_refs` is "chain seq ascending".
  If a future builder bug emits them out of order, the bundle's
  canonical bytes drift. Mitigated by the conformance fixture
  pinning the expected order.

### Reversibility

- Removing the field in a future version is **breaking** for
  consumers that read it. v1 commits to keeping it.
- Adding sibling fields (`lease_trace_refs`, `replay_trace_refs`)
  is additive and does not require ADR amendment of this one — a
  new ADR can simply cite this one's pattern.

## Compatibility with existing conformance vectors

This ADR is **fully additive**:

- `vectors.json` (v0.0.1-alpha 10 chain vectors) — unchanged.
- `text_vectors.json` (12 vectors) — unchanged.
- `signature_vectors.json` (5 vectors) — unchanged.
- `lease_lifecycle_event_vectors.json` (P0.1) — unchanged.
- `policy_check_event_vectors.json` (P0.2) — unchanged.
- `replay_event_vectors.json` (P1.1) — unchanged.
- `reason_codes_vectors.json` (P0.3) — unchanged.

New fixture introduced under this ADR:
- `proof_bundle_policy_trace_vectors.json` — 3 positive vectors
  (no policy events → field absent; one policy event → 1-element
  list; multiple policy events → ordered N-element list) + 1
  byte-equality vector pinning the Py/TS shared output.

## Alternatives considered

(See § 4 of Decision.)

## Implementation status

Accepted 2026-05-17. Companion artefacts in this commit:

- `schemas/v1/proof_bundle.schema.json` — `policy_trace_refs`
  optional field added with regex + uniqueItems + maxItems.
- `sdk/python/src/attestplane/proof_bundle.py` —
  `ProofBundleBuilder.build()` auto-populates the list.
- `sdk/typescript/src/proof_bundle.ts` — TS mirror.
- `sdk/python/tests/conformance/proof_bundle_policy_trace_vectors.json` —
  new conformance fixture.
- Unit tests in both languages.

This ADR does NOT touch:
- `canonicalize()` / `hashchain` / `ChainedEvent` (frozen).
- `vectors.json` / `text_vectors.json` / `signature_vectors.json` /
  `lease_lifecycle_event_vectors.json` / `policy_check_event_vectors.json`
  / `replay_event_vectors.json` / `reason_codes_vectors.json`.

## Follow-up

If a customer engagement requires it, a future ADR-0016 can ship
`lease_trace_refs` + `replay_trace_refs` using the same flat-list
pattern. The pattern of "builder auto-populates from events list +
additive optional top-level array + maxItems safety cap" is
recommended as the default for any future top-level event-type
index.
