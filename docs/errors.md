<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Stable Verifier Error Taxonomy

`v0.0.5-alpha` adds a machine-readable verifier error-code layer for CLI and
SDK consumers. This taxonomy is separate from ADR-0010 `ReasonCodeV1`: reason
codes describe chain/event verification semantics, while `VERIFY_*` codes
classify verifier and CLI outcomes.

This is an alpha API surface. The v1 code names are intended to be stable for
the alpha line, but Attestplane has not made a GA compatibility promise yet.
Future alpha releases may add optional fields or tighten descriptions without
renaming existing v1 codes.

## Schema

- `verify_error_schema_version`: `1`
- Python: `attestplane.verify_errors`
- TypeScript: `src/verify_errors.ts`

## Codes

| Code | Meaning |
|---|---|
| `VERIFY_OK` | Verification completed without a verifier-detected failure. |
| `VERIFY_IO_ERROR` | The verifier could not read the requested input. |
| `VERIFY_SCHEMA_ERROR` | The input shape is unsupported or malformed. |
| `VERIFY_CHAIN_RECOMPUTE_FAILED` | Recomputed hash-chain verification failed. |
| `VERIFY_METADATA_CLOSURE_FAILED` | Bundle metadata disagrees with recomputed chain state. |
| `VERIFY_POLICY_TRACE_REFS_FAILED` | Policy trace refs are missing, dangling, duplicated, or out of order. |
| `VERIFY_RETENTION_PROOF_FAILED` | Retention/deletion proof refs are malformed or dangling. |
| `VERIFY_ARTIFACT_HASH_FAILED` | The envelope artifact hash does not match the embedded proof bundle. |
| `VERIFY_REQUIRED_FIELDS_MISSING` | A required verifier-envelope field is missing. |
| `VERIFY_EXTENSION_INVALID_INPUT` | Requested signature or anchor extension input is malformed. |
| `VERIFY_EXTENSION_UNSUPPORTED` | Requested signature or anchor extension input uses an unsupported mode. |
| `VERIFY_EXTENSION_FAILED` | Requested signature or anchor extension verification failed. |

## Claim Boundary

These codes are engineering outcomes. They do not mean:

- EU AI Act compliance,
- GDPR compliance,
- legal certification,
- production readiness, or
- complete external sidecar deletion.

They are intended to make offline verifier output deterministic and easier to
consume in CI, audit exports, and cross-language conformance tests.

## Verifier Rejection Reasons

Issue #172 adds a second, SDK-public taxonomy for rejection reasons returned
by `verify` paths. Issue #236 threads that same taxonomy through both
`verify --json` and `verify --explain`:

- `verify_reason_code_schema_version`: `1`
- Python: `attestplane.verify_reason_codes`
- TypeScript: `src/verify_reason_codes.ts`
- Result shape: `primary_reason` is exactly one code for rejected verifier
  results, and `secondary_reasons` is an ordered list of additional failed
  checks. Successful verifier results use `primary_reason: null` and
  `secondary_reasons: []`.
- CLI JSON surfaces the same taxonomy with `reason_code` and
  `taxonomy_version`, while `--explain` renders the same code set in human
  form and adds a top-level `explanation[]` array with
  `{primary_reason, pointer, message}` entries.

These codes are namespaced under `att.verify.*`. The taxonomy is pinned by
`taxonomy_version = 1` and is additive-only: adding a new code is allowed with
documentation and tests, but removing, renaming, or reusing an existing code
is a breaking change and must be called out in `CHANGELOG.md`.

The v1.7.x release-note delta names the same stability knob
`reason_code_version`; in the canonical docs, the stable version is surfaced as
`verify_reason_code_schema_version: 1` / `taxonomy_version = 1`.

| Code | Meaning |
|---|---|
| `att.verify.anchor_invalid` | Anchor material is missing, malformed, unsupported, or failed verification. |
| `att.verify.canonical_mismatch` | Recomputed canonical bytes, event hashes, chain links, or embedded verification reports disagree. |
| `att.verify.required_field_missing` | A required top-level, nested, signature, or verifier-envelope field is absent. |
| `att.verify.schema_invalid` | The input shape is malformed for a known verifier schema. |
| `att.verify.schema_unknown` | The input declares an unknown schema family, verification method namespace, or fail-closed critical/required field. |
| `att.verify.schema_version_missing` | A known bundle, payload, signature, or verifier schema version is missing. |
| `att.verify.schema_version_unsupported` | A known bundle, payload, signature, or verifier schema version is unsupported. |
| `att.verify.signature_invalid` | Signature material is present but malformed or fails verifier checks. |
| `att.verify.signature_missing` | Strict verification requires signature material but none is present. |
| `att.verify.structure_invalid` | Known bundle relationships are malformed, duplicated, dangling, or out of order. |

The existing human-readable fields such as `chain_result.reason`,
`metadata_reason`, `policy_trace_refs_reason`, `retention_proofs_reason`, and
`signed_attestation_schema_reason` remain for one minor release as deprecated
migration aids. SDK and CLI consumers should branch on `primary_reason` and
`secondary_reasons` instead of matching these strings.

Forward-compatible additive bundle fields are ignored by the verifier and do
not change `ok` when the rest of the bundle is valid. Use `verify --explain`
when you need the human-oriented summary of the rejected result; the CLI
keeps the structured `reasons[]` contract and adds the operator-facing
`explanation[]` array without changing exit codes.
