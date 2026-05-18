# CLI ProofBundle Verifier Alpha

`attestplane verify-proofbundle` is an alpha local verifier for P3.1
ProofBundle verification envelopes. It is separate from `attestplane verify`,
which remains `chain_report_only`.

## Usage

```bash
attestplane verify-proofbundle tests/fixtures/proofbundle/valid_minimal.json
```

The command always emits a machine-readable JSON report and uses these exit
codes:

| Exit code | Meaning |
|---|---|
| 0 | Valid local alpha verification envelope. |
| 1 | Verification failed, for example a recomputed hash or chain link mismatch. |
| 2 | Invalid input, malformed JSON, missing required metadata, or unsupported version. |

## Checks

The alpha verifier checks:

- JSON parse succeeds.
- Required P3.1 envelope fields are present.
- `proofbundle_verifier_schema_version` is supported.
- Embedded ProofBundle metadata closure and hash chain recomputation pass.
- Artifact hash is lowercase SHA-256 hex and matches the canonical ProofBundle bytes.
- Hash-chain metadata agrees with the embedded ProofBundle metadata.
- Obligation references are known and match `framework_mappings`.
- in-toto Statement and DSSE envelope shape are present and internally consistent.
- Storage compatibility metadata identifies the alpha JSONL compatibility policy.
- Provenance metadata does not claim SLSA level, certified provenance, or production supply-chain security.

## Boundary

This command is local, read-only, and alpha-grade. It does not perform network
access, signature verification, anchor verification, release asset publishing,
or compliance certification. It is not production-ready and not compliance-ready.

The DSSE/in-toto checks are shape checks only. They do not verify cryptographic
signatures, transparency-log entries, or release provenance.

## Report Fields

The JSON report includes:

- `verification_scope: "proofbundle_alpha_local"`
- `ok`
- `exit_code`
- `checks`
- `summary`
- `network_access_performed: false`
- `signature_verification_performed: false`
- `anchor_verification_performed: false`
- `compliance_certification: false`
- `production_ready: false`
- `certified_provenance: false`
- `slsa_level_claimed: null`

