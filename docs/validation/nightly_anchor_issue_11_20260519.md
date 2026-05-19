<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Nightly Anchor Issue #11 Diagnosis — 2026-05-19

## Scope

This report records the P0 diagnosis for
[`#11`](https://github.com/attestplane/attestplane/issues/11), the
nightly A5 FreeTSA live verification failure from
[run 26076696174](https://github.com/attestplane/attestplane/actions/runs/26076696174).

This report does not change release status and does not expand public
claims. The default `attestplane verify` path remains `chain_report_only`.

## Finding

The failure was not a FreeTSA reachability outage. The workflow fetched
the FreeTSA root and received a TimeStampResp, then failed during local
CMS signature verification:

```text
TSA ECDSA signature does not verify against leaf cert
```

Local inspection of a fresh FreeTSA response showed:

| Field | Observed value |
|---|---|
| TSTInfo `message_imprint.hash_algorithm` | `sha256` |
| CMS `SignerInfo.digest_algorithm` | `sha512` |
| CMS `SignerInfo.signature_algorithm` | `sha512_ecdsa` |

Attestplane was correct to require SHA-256 for the anchored chain-head
digest. The bug was that `verify_timestamp_token()` also hard-coded
SHA-256 for the CMS `signed_attrs` signature verification. Live TSAs may
sign the CMS wrapper with SHA-512 ECDSA while timestamping a SHA-256
message imprint.

## Fix

The verifier now keeps these two checks separate:

- `messageImprint` must remain SHA-256 and match the expected
  Attestplane chain-head digest.
- CMS `signed_attrs` verification uses an explicit allowlist derived
  from `SignerInfo.digest_algorithm` and `SignerInfo.signature_algorithm`
  (`sha256`, `sha384`, `sha512` for RSA PKCS#1 v1.5 or ECDSA).
- Python and TypeScript now use the same verification semantics.
- The signer certificate is selected by `SignerInfo.sid`, not by
  certificate array order.
- `signed_attrs` must include valid `content-type=tst_info` and a
  `message-digest` computed with the CMS signer digest.
- The TSA signer certificate must carry critical `timeStamping`
  ExtendedKeyUsage.

A deterministic offline regression was added:

```text
sdk/python/tests/anchoring/test_rfc3161.py::test_ec_leaf_with_sha512_cms_signer_digest_round_trips
sdk/typescript/test/rfc3161.test.ts::RFC-3161 CMS signer digest parity
```

Claude Opus advisory was requested because this is a cryptographic
verification boundary. The advisory completed and confirmed the
algorithm split while requiring the additional fail-closed checks above.

## Local Live Probe

After the fix, a local FreeTSA probe returned:

```json
{"status": "ok", "cert_status": "VALID", "reason": null}
```

## Claim Safety

No claim was expanded:

- `attestplane verify` remains chain/report-oriented.
- No full ProofBundle verification claim was added.
- No default signed verification claim was added.
- No default anchored verification claim was added.
- No compliance certification claim was added.

## Explicit Non-Actions

- tag: not performed
- release: not performed
- publish: not performed
- deploy: not performed
- workflow_dispatch: not performed
- secrets printed: false

## Final Status

`nightly_anchor_issue_11_diagnosed_with_local_fix`
