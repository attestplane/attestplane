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
| 2 | Invalid signature or anchor material, or a fail-closed signature/anchor request with unsupported or missing verification input. |
| 3 | Schema or output-contract error, including malformed JSON, missing required metadata, or unsupported version. |
| 4 | Quarantined or anchor-unverifiable material. The JSON report stays deterministic, but the anchor cannot be trusted for gating. |

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
access or compliance certification. Signature and anchor verification are
opt-in fail-closed extensions behind `--verify-signature` and `--verify-anchor`.
It is not production-ready and not compliance-ready.

The default DSSE/in-toto checks are shape checks only. The optional signature
and anchor flags perform fail-closed verification of the declared material, but
they still do not verify transparency-log entries or release provenance.

## Report Fields

The JSON report includes:

- `verification_scope: "proofbundle_alpha_local"`
- `status`
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

The top-level `status` field is the canonical machine-readable gate state:

- `ok` maps to exit code `0`.
- `invalid_signature_or_anchor` maps to exit code `2`.
- `output_contract_error` maps to exit code `3`.
- `quarantined` maps to exit code `4`.

---

## P3.2 alpha signature / anchor extension flags

Two optional flags request fail-closed alpha verification material
inspection. Cryptographic verification is NOT performed.

```bash
# request alpha DSSE signature material inspection (fail-closed)
python -m attestplane.cli.main verify-proofbundle <path> --verify-signature

# request alpha RFC-3161 anchor material inspection (fail-closed)
python -m attestplane.cli.main verify-proofbundle <path> --verify-anchor

# both
python -m attestplane.cli.main verify-proofbundle <path> --verify-signature --verify-anchor
```

Status semantics for `signature_verification_status` /
`anchor_verification_status`:

| Status            | Meaning                                                            | Exit |
|-------------------|--------------------------------------------------------------------|------|
| `skipped`         | flag not set; extension not exercised                              | same as enclosing report |
| `invalid_input`   | flag set but verification material missing or shape invalid       | 2    |
| `unsupported`    | flag set but declared algorithm / anchor type outside allowlist   | 2    |
| `not_implemented`| flag set, material present, alpha verifier does not perform crypto | 2    |
| `failed`          | signature verification failed after the cryptographic path ran     | 2    |
| `quarantined`     | anchor material was present but unverifiable for gating            | 4    |
| `passed`          | successful verification path                                       | 0    |

Alpha allowlists (subject to change in follow-up branches):

- signature algorithm allowlist: `{ed25519}`
- anchor type allowlist: `{rfc3161}`

The verifier never attempts network access under any flag combination.
See `docs/validation/p3_2_signed_anchored_verification_report.md` for
the full scope statement and remaining limitations.
