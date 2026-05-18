# P3.1 CLI ProofBundle Verifier Report

## Scope

P3.1 adds an alpha local CLI verifier for P3.1 ProofBundle verification
envelopes:

```bash
attestplane verify-proofbundle <bundle.json>
```

The existing `attestplane verify` command remains `chain_report_only`.

## Contract

The new verifier emits JSON and uses these exit codes:

| Exit code | Meaning |
|---|---|
| 0 | Valid alpha verification envelope. |
| 1 | Verification failed. |
| 2 | Invalid input, malformed file, or unsupported version. |

The verifier is fail-closed. Malformed JSON, unsupported versions, missing
required sections, invalid hash formats, tampered artifact hashes, broken chain
links, missing DSSE/in-toto shape, and missing storage compatibility metadata
all fail.

## Implemented Checks

- JSON parse and root object checks.
- Required field and `proofbundle_verifier_schema_version` checks.
- Existing ProofBundle metadata closure and chain recomputation predicates.
- Artifact SHA-256 format and recomputation over canonical ProofBundle bytes.
- Hash-chain metadata consistency with the embedded ProofBundle.
- Obligation references against the shipped obligation registries.
- in-toto Statement v1 shape and subject digest consistency.
- DSSE envelope shape and payload round-trip to the provided statement.
- Storage compatibility metadata for the alpha JSONL compatibility policy.
- Provenance metadata no-go checks: no SLSA level, no certified provenance, no production supply-chain security.

## Fixtures

Added fixtures under `tests/fixtures/proofbundle/`:

- `valid_minimal.json`
- `missing_required_field.json`
- `malformed.json`
- `invalid_hash_format.json`
- `tampered_artifact_hash.json`
- `broken_hash_chain.json`
- `unsupported_version.json`
- `missing_dsse_shape.json`
- `missing_storage_compat.json`

## Gate

Added `scripts/check-proofbundle-verifier.sh`, which runs:

- `sdk/python/.venv/bin/pytest sdk/python/tests/cli/test_proofbundle_alpha.py -q`
- CLI fixture exit-code checks for all P3.1 fixtures.
- `jq empty` on generated JSON reports.
- Validation JSON parsing.
- Claim scan for the new verifier surfaces.

## Safe Claims

- Alpha local ProofBundle verification envelope checks.
- Local JSON shape, hash, chain, obligation, storage compatibility, and provenance-shape checks.
- DSSE/in-toto shape checking only.
- Machine-readable JSON report with exit codes 0, 1, and 2.

## No-Go Claims

- Not production-ready.
- Not compliance-ready.
- No certification claim.
- No full CLI ProofBundle verification claim for the existing `attestplane verify` command.
- No default signed verification.
- No default anchored verification.
- No runtime governance or AIOS runtime integration claim.
- No ACID, database-grade durability, or multi-writer correctness claim.
- No formal verification or exhaustive mutation-testing claim.
- No SLSA L3 or certified provenance claim.
- No automatic destructive storage repair claim.

## Remaining P3.1 Limitations

- Cryptographic signature verification remains out of scope for this command.
- Anchor verification remains out of scope for this command.
- The verifier accepts the P3.1 local envelope shape, not arbitrary third-party provenance documents.
- Release asset checksums and upload flow remain governed by the P2.5 provenance artifact gate.

## Validation Result

Status: PASS after running the commands listed in the companion JSON report.

