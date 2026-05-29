# P3.2 Signed / Anchored Verification Path — Alpha Report

- **Date**: 2026-05-18
- **Verdict**: `P3.2SignedAnchoredVerificationReadyWithLimitations`
- **Branch**: `feat/p3-2-signed-anchored-verification-20260518`
- **Base commit**: `7a89d54d0b8ec956bdba00d588a4f56297bfefc2` (`main`, P3.1 merged)
- **v0.0.3-alpha tag**: untouched, still pins `9bde6338df008afe58d561b0ba66eaaf75e298ad`

## Scope

P3.2 adds an alpha-grade signed / anchored verification *interface* on top of
the P3.1 ProofBundle verifier. **Cryptographic signature verification and
RFC-3161 anchor verification are not implemented in this branch**; the
interface is wired and fail-closed paths are exhaustively exercised, but the
positive cryptographic path is deferred. This is the honest verdict — the
verifier does not pretend to verify what it does not verify.

## P3.2a — Extension Interface

Two new CLI flags on `attestplane verify-proofbundle`:

- `--verify-signature` — request alpha DSSE signature material inspection
- `--verify-anchor` — request alpha RFC-3161 anchor material inspection

Default behaviour is byte-equivalent to P3.1 (both `*_status: "skipped"`).
Report shape extended:

```json
{
  "signature_verification_requested": <bool>,
  "signature_verification_performed": false,
  "signature_verification_status": "skipped|invalid_input|unsupported|not_implemented",
  "signature_verification_summary": {...},
  "signature_verification_claims": {
    "cryptographic_verification_performed": false,
    "certified_provenance": false,
    "production_supply_chain_security": false,
    "slsa_level_claimed": null
  },
  "anchor_verification_requested": <bool>,
  "anchor_verification_performed": false,
  "anchor_verification_status": "skipped|invalid_input|unsupported|quarantined|not_implemented",
  "anchor_verification_summary": {...},
  "anchor_verification_claims": {
    "anchor_verification_performed": false,
    "long_term_archival_trust": false,
    "legal_timestamp_attestation": false,
    "network_access_attempted": false
  },
  "safe_claims": [...],
  "no_go_claims": [...]
}
```

## P3.2b — DSSE Signature Verification (alpha, fail-closed only)

Implemented as inspection of `proof_bundle_envelope.signature_material` and
`dsse_envelope.signatures[]`:

- `missing material` → exit 2, `status: "invalid_input"`,
  `summary.reason: "missing_material"`
- `algorithm not in {ed25519}` → exit 2, `status: "unsupported"`,
  `summary.reason: "unsupported_algorithm"`
- `material present, allowlisted algorithm` → exit 2,
  `status: "not_implemented"`,
  `summary.reason: "alpha_cryptographic_verification_not_implemented"`

The verifier deliberately does NOT call into `signing/verifier_ext.py`
`_verify_single_signature` for this alpha branch. That code is sound, but
wiring it up here would require a positive-fixture test key, ed25519 PAE
binding, and PKI lifecycle handling that is out of P3.2 scope.

## P3.2c — RFC-3161 Anchor Verification (alpha, fail-closed only)

Implemented as inspection of `proof_bundle_envelope.anchor_records[]`:

- `missing` → exit 2, `status: "invalid_input"`,
  `summary.reason: "missing_material"`
- `anchor_type not in {rfc3161}` → exit 2, `status: "unsupported"`,
  `summary.reason: "unsupported_anchor_type"`
- `records present, allowlisted type` → exit 1 on cryptographic
  verification failure, `status: "quarantined"`,
  `summary.reason: "rfc3161_verify_failed"`

No network access is attempted under any condition (asserted in the
extension `summary.network_access_attempted: false` field). The existing
`anchoring/verifier.py` `verify_chain_with_anchors` + `anchor_vectors.json`
test material would be the integration target for the follow-up positive
path.

## P3.2d — Negative Fixtures + Gates

10 new fixtures land in this branch (all under
`tests/fixtures/proofbundle/`):

- `signature_shape_valid_but_not_requested.json`
- `missing_signature_material.json`
- `tampered_dsse_signature.json`
- `unsupported_signature_algorithm.json`
- `anchor_shape_valid_but_not_requested.json`
- `missing_anchor_material.json`
- `expired_tsa_timestamp.json`
- `invalid_anchor_chain.json`
- `unsupported_anchor_type.json`
- `signature_and_anchor_requested_missing_material.json`

Total fixture count: 20 (10 P3.1 + 10 P3.2).

Tests in `sdk/python/tests/cli/test_proofbundle_alpha.py`: 25 parametrized
cases now, all green.

New gate: `scripts/check-signed-anchored-verification.sh` exercises a
15-row CLI smoke matrix + jq + claim scan + `git diff --check`.

## P3.2e — Publish-Readiness

- Source code ready for future package version bump.
- **No** PyPI publish in this branch.
- **No** npm publish in this branch.
- **No** GitHub Release modification in this branch.
- v0.0.3-alpha tag untouched (`9bde6338…`).
- npm `latest` dist-tag untouched (`0.0.1-alpha.1`).

## CLI Usage

```bash
# default — identical to P3.1
python -m attestplane.cli.main verify-proofbundle <path>

# request alpha signature material inspection (fail-closed)
python -m attestplane.cli.main verify-proofbundle <path> --verify-signature

# request alpha anchor material inspection (fail-closed)
python -m attestplane.cli.main verify-proofbundle <path> --verify-anchor

# both
python -m attestplane.cli.main verify-proofbundle <path> --verify-signature --verify-anchor
```

## Exit Code Contract (unchanged from P3.1)

- `0` — valid (default flags; all P3.1 structural checks pass)
- `1` — verification failed (e.g. hash mismatch, tampered artifact hash,
  broken hash chain)
- `2` — invalid input / malformed JSON / missing required field /
  unsupported version / **unsupported algorithm or anchor type** /
  **missing verification material when extension requested**

## Safe Claims

- Optional alpha signature verification request path implemented.
- Optional alpha anchor verification request path implemented.
- Deterministic JSON report shape extended without breaking P3.1 consumers.
- Fail-closed coverage: missing material, unsupported algorithm,
  unsupported anchor type, not-implemented positive path.
- Quarantine coverage: parseable anchor material that still fails
  RFC-3161 verification is surfaced as `anchor_verification_status:
  "quarantined"` rather than being accepted as anchored.
- Default `verify-proofbundle` behaviour is byte-equivalent to P3.1.
- No network access attempted under any flag combination.

## No-Go Claims (deliberately preserved)

- Verifier is NOT production-ready.
- Verifier is NOT compliance-ready.
- Verifier is NOT certification-ready.
- Verifier does NOT emit a certified provenance attestation.
- Verifier does NOT establish SLSA L3 or any other SLSA level.
- Verifier is NOT a production-grade supply-chain security control.
- Verifier does NOT provide legal timestamp attestation.
- Verifier does NOT guarantee long-term archival trust.
- Verifier does NOT perform cryptographic DSSE signature verification
  in this branch (only material inspection).
- Verifier does NOT perform RFC-3161 anchor token verification in this
  branch (only material inspection).
- Verifier does NOT perform certificate revocation checking.
- Verifier does NOT load eIDAS qualified TSA trusted lists.
- Verifier does NOT validate full PKI lifecycle.

## Remaining P3.2 Limitations

- Cryptographic DSSE signature verification (PAE binding +
  algorithm-specific verifier) is deferred to a follow-up branch using
  test-only ed25519 fixture key material.
- RFC-3161 token verification (message-imprint match + cert chain to
  test root + OCSP) is deferred. The existing `anchor_vectors.json`
  has all the cryptographic material needed; the integration is purely
  wiring work.
- Algorithm allowlist is currently `{ed25519}`. Adding RSA/ECDSA support
  is a follow-up, not a blocker.
- Anchor type allowlist is currently `{rfc3161}`. Sigstore Rekor entry
  verification is a separate code path (see `anchoring/sigstore.py`)
  and is deferred.
- Test-only crypto material is in fixtures; production key/cert
  lifecycle is out of scope.

## Readiness Recommendation

`P3.2SignedAnchoredVerificationReadyWithLimitations` — the extension
interface, CLI flags, report shape, and fail-closed paths are
production-quality for the alpha boundary they sit at. The positive
cryptographic path is intentionally deferred to keep the alpha claim
honest: this verifier does not pretend to do what it does not do.
