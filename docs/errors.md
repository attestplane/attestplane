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
