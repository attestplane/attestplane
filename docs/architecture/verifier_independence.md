<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Verifier Independence Model

## Status

Accepted architecture guidance for the alpha substrate.

## Principle

Attestplane verification must not require trusting an Attestplane-hosted
production API. Hosted services may improve discovery, slicing, indexing, and
export ergonomics, but they are not the trust root.

The trust root is:

```text
open verifier + versioned schemas + exported evidence bytes + declared trust roots
```

## Why This Matters

Attestplane is a substrate. External auditors, regulated entities, and future
governance tools must be able to verify records independently. If truth depends
on a closed hosted API, the system becomes an unverifiable verifier.

For alpha, this means public docs should distinguish:

- **verification authority:** deterministic open-source verifier and schemas;
- **retrieval convenience:** API, index, dashboard, or hosted export service;
- **deployment responsibility:** caller-controlled retention, PII handling,
  and legal review.

## Required Offline Inputs

An independent verifier run should need only:

| Input | Purpose |
|---|---|
| Evidence bundle or export | The bytes being verified. |
| Schema version references | The validation contract for each event. |
| Verifier version or source revision | The deterministic algorithm used for the report. |
| Trust roots | Optional signature, TSA, Rekor, or eIDAS roots when sidecars are reviewed. |
| Profile identifier | Optional profile contract such as the AIA-12 aligned profile. |

If a hosted API supplied the export, the verifier should still verify the export
as bytes. The API's claim that the export is valid is not enough.

## API Boundary

Hosted or local APIs may provide:

- search over event metadata,
- export generation,
- bundle slicing by session or profile,
- schema discovery,
- verifier report storage, and
- convenience status pages.

APIs must not be documented as the sole source of truth. Public phrasing should
prefer:

```text
The API helps retrieve and inspect evidence. The open verifier checks the
exported bytes.
```

Avoid phrasing that implies:

```text
The hosted API decides whether a record is true.
```

## Failure Semantics

The independent verifier should fail closed when:

- required schema versions are missing,
- the evidence chain is broken,
- profile-critical fields are absent without explicit limitations,
- sidecar signatures or anchors are malformed when requested,
- trust roots are unavailable for requested sidecar checks, or
- the export cannot be parsed deterministically.

## Relationship to `attestplane verify`

The current CLI verifier remains chain/report-oriented. It does not perform
full ProofBundle, signed, anchored, or legal certification checks. This model
describes the direction for independent review surfaces without expanding the
current CLI claim.

## Relationship to Issue #7

This document resolves the verifier-independence part of issue #7: auditors
should be able to verify complete exports offline using OSS verifier code and
versioned schemas. APIs are helpful, but not authoritative.

## Related: OM World Execution Proof

The verifier-independence rule converged independently with the OM World
Execution Proof spec. OM World's [`docs/execution-proof.md` §On-chain
verification](https://github.com/omworldprotocol/om-world/blob/61979b1/docs/execution-proof.md#on-chain-verification)
now carries the same rule — the trust root MUST be the deterministic
open-source verifier + versioned schemas + exported evidence bytes, with
hosted indices/APIs as a convenience layer that verification correctness MUST
NOT depend on. The cross-adoption is tracked in
[issue #7](https://github.com/attestplane/attestplane/issues/7); attestplane is
listed as a Genesis Reviewer of that spec
([CONTRIBUTORS.md](https://github.com/omworldprotocol/om-world/blob/61979b1/CONTRIBUTORS.md#execution-proof)).
