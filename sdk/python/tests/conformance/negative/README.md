<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Negative conformance vectors

Five frozen test fixtures that exercise the verifier on chains that MUST
fail validation. Each file pairs a deliberately-broken chain with the
expected failure mode (`ok=False`, `first_bad_index`, and a substring of
the human-readable reason).

| File | Failure mode | Detection point |
|------|--------------|-----------------|
| `broken_chain.json` | `prev_hash` mismatch (event seq=1's `prev_hash` is bogus) | index 1 |
| `missing_event.json` | seq gap (event seq=1 deleted) | index 1 |
| `reordered_event.json` | events at positions 1/2 swapped (seq fields preserved) | index 1 |
| `duplicate_event.json` | event seq=1 repeated at position 2 | index 2 |
| `malformed_payload.json` | event seq=1's `payload` mutated, `event_hash_hex` left stale | index 1 |

Together they pin gates **A2** (single-event hash integrity) and **A3**
(reorder / delete / insert detection) from
[`docs/architecture/ATTESTATION_GATES.md`](../../../../../docs/architecture/ATTESTATION_GATES.md).

## Generation

These fixtures were generated once by an inline script using the live SDK
to compute byte-exact hash values for the underlying good chain. They are
now **frozen artifacts**: do not regenerate. Any change in canonicalization
or hash semantics that would alter the byte content is a substrate-level
change requiring `SCHEMA_VERSION` bump per ADR-0002.

The underlying good chain is the first three events of the frozen
`vectors.json` happy-path set, so any drift in those base vectors would
also break these negative fixtures — by design.

## Relationship to `vectors.json`

`vectors.json` (parent directory) is the **happy-path** conformance set
and is the long-term external contract referenced by ADR-0002. This
`negative/` directory is the **failure-mode** set. Both are frozen; both
are read by Python and TypeScript test suites.

The TypeScript port of these negative vectors will ship at M6 alongside
the verifier CLI; for v0.1 only the Python side reads them. The fixtures
themselves are language-neutral JSON.
