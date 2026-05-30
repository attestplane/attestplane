<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# User-facing roadmap

> **Audience.** This roadmap is written for outside readers — downstream
> users, third-party contributors, and auditors evaluating whether
> Attestplane is fit for their workflow. It complements the
> engineering-internal
> [`docs/roadmap/p3_release_roadmap.md`](p3_release_roadmap.md), which
> tracks per-gate implementation work in greater detail.
>
> **Pre-GA status.** The project is currently on the **v1.0.x pre-GA
> tag line**. Per [`SECURITY.md`](../../SECURITY.md), the v1.0 GA
> target is **2026-08-15**; the vulnerability response timelines
> published in `SECURITY.md` apply from v1.0 GA onwards. Pre-GA cadence
> is best-effort triage on the same target intervals.
>
> **No new date commitments.** The only schedule anchor in this
> document is the 2026-08-15 GA target already published in
> `SECURITY.md`. Nothing here promises a date for silver-tier
> criteria, third-party audit, ISO/IEC 42001 crosswalk submission,
> or EU AI Office submission.

---

## 1. Current capabilities (v1.0.x pre-GA)

What the project provides **today**, on the v1.0.x pre-GA tag line. Each
item links to its primary source-of-truth artifact in the repository.

### Wire format and SDKs

- **`AP-EVD/1.0` wire format** — Attestplane Evidence Protocol,
  frozen per [ADR-0011 (canonical text v1)](../adr/0011-canonical-text-v1.md)
  and [ADR-0016 (RC API freeze)](../adr/0016-rc-api-freeze.md). Backwards-
  compatible changes only inside the v1 line.
- **Python SDK** — published to PyPI; public surface enumerated in
  [`sdk/python/src/attestplane/__init__.py`](../../sdk/python/src/attestplane/__init__.py).
- **TypeScript SDK** — published to npm; same `AP-EVD/1.0` wire format,
  same canonicalization rules.
- **Cross-SDK byte equivalence** — enforced on every push by the
  `cross-sdk-roundtrip` workflow against the frozen conformance
  fixtures under [`tests/`](../../tests). Drift fails CI.

### Verifier (chain/report-oriented)

- **`attestplane verify` CLI** — chain/report-oriented path: replays
  bundle events, compares the embedded `verification_report` with the
  recomputed chain result, and fails closed on malformed ProofBundle
  metadata and `policy_trace_refs` closure.
- **Not yet stable**: a full **ProofBundle verifier** (predicate-based,
  not chain-based) is tracked under P3.1 of
  [`p3_release_roadmap.md`](p3_release_roadmap.md) and is **not** in
  the current CLI default path.

### Anchoring and signing

- **RFC 3161 TSA anchoring** — per [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md).
  FreeTSA, DigiCert, and Sigstore Rekor TSA providers are shipping;
  eIDAS qualified-TSA backends are pluggable via
  `load_qualified_tsa_trust_roots()`.
- **Ed25519 sidecar signing** — per
  [ADR-0005](../adr/0005-event-signing-scheme.md). KeyProvider
  abstraction with plurality verification.

### Release supply-chain evidence

- **Sigstore keyless cosign on releases** — applied **forward-only**
  per [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md);
  v1.0.9 is the first cut produced under that regime and is the
  worked example in
  [`docs/release/verifying-signatures.md`](../release/verifying-signatures.md).
- **SLSA Build L3 provenance on releases** — attached to releases
  from v1.0.9 forward via the upstream pinned
  `slsa-framework/slsa-github-generator` (per ADR-0018). The SLSA L3
  claim originates from the upstream generator, not from project
  self-attestation.
- **GitHub Actions release CD** — per
  [ADR-0017](../adr/0017-github-actions-release-cd.md).

### Open badge and cross-spec footprint

- **OpenSSF Best Practices badge — passing tier (100%)**, project
  [12924](https://www.bestpractices.dev/en/projects/12924/passing). Evidence
  mirrored at
  [`docs/security/openssf-best-practices.md`](../security/openssf-best-practices.md).
  Silver tier sits at **15%** as of 2026-05-20; the forward-looking
  view is at
  [`docs/security/openssf-silver-roadmap.md`](../security/openssf-silver-roadmap.md).
  Receiving the badge is not a compliance certification, a conformity
  assessment, or any other regulatory determination.
- **Cross-spec convergence (informational)** — the verifier-
  independence and commit-then-redact patterns implemented here are
  cited by the `omworldprotocol/om-world` execution-proof
  specification. The two specs evolve independently; convergence is
  informational, not a coupling.

### Honest framing — what the v1.0.x pre-GA line is **not**

- Not a legal compliance certification.
- Not a conformity assessment under any regulation.
- Not a full ProofBundle verifier (predicate-based) at the CLI default
  path — that is tracked under P3.1.
- Not a runtime-honesty attestation surface.
- Not on-chain settlement infrastructure.
- Not a production SLA — the response timelines in `SECURITY.md`
  apply from v1.0 GA onwards.

---

## 2. Next milestone — **v1.0 GA**, target 2026-08-15

The next user-visible milestone is **v1.0 GA**. The 2026-08-15 target
is the one already published in [`SECURITY.md`](../../SECURITY.md);
this section does **not** introduce any additional dated commitments.

What v1.0 GA adds on top of the v1.0.x pre-GA line:

- **Vulnerability response timeline becomes the SLA.** The table in
  [`SECURITY.md`](../../SECURITY.md) (acknowledgement within 7 days,
  triage within 14 days, Critical fix within 30 days, High within 60
  days, Medium/Low within 90 days) applies from v1.0 GA onwards.
  Pre-GA the same intervals are tracked best-effort.
- **GPG key publication for `security@attestplane.com`.** Per the GPG
  section of `SECURITY.md`, the project GPG key will be published at
  or before the v1.0 GA cut through three channels: this `SECURITY.md`
  file (fingerprint inlined), the project site, and `pgp.mit.edu`.
  Until that publication, the recommended pre-GA private channel is
  GitHub Security Advisories.
- **First marketed signed release.** Cosign keyless signing and SLSA
  Build L3 provenance are already proven on v1.0.9 per ADR-0018; v1.0
  GA is the first release line marketed as carrying that supply-chain
  evidence by default.
- **Default installer alignment.** Default PyPI and npm installs are
  intended to resolve to the v1.0 GA cut.
- **Patch line under SLA.** Subsequent v1.0.x patches after GA fall
  under the same response-timeline SLA.

What v1.0 GA does **not** promise:

- It does not promise OpenSSF silver-tier or gold-tier badge status.
  The silver roadmap is tracked at
  [`docs/security/openssf-silver-roadmap.md`](../security/openssf-silver-roadmap.md);
  no date beyond the 2026-08-15 anchor is committed.
- It does not promise third-party cryptanalysis review, ISO/IEC
  42001 crosswalk submission, or EU AI Office submission. Those are
  governance decisions for the maintainer.
- It does not retroactively re-tag or re-sign pre-ADR-0018 releases.
  Signing is **forward-only** per ADR-0018.

---

## 3. What counts as "stable usable"

This section defines the stability gates a downstream user or auditor
can check independently. The project considers a capability "stable
usable" only when **all** of the following gates hold for the release
under inspection.

| # | Gate | How to check |
|---|------|--------------|
| G1 | Chain/report verifier path passes the published conformance corpus | Run `attestplane verify` over the frozen fixtures under [`tests/`](../../tests); the `verifier-conformance` workflow on `main` records the green status. |
| G2 | `AP-EVD/1.0` cross-SDK byte equivalence holds | The `cross-sdk-roundtrip` workflow is green for the release tag. Python ↔ TypeScript produce byte-identical event hashes for every fixture. |
| G3 | Sigstore keyless cosign + SLSA Build L3 attached to the release | Follow [`docs/release/verifying-signatures.md`](../release/verifying-signatures.md). Apply forward-only per [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md); v1.0.9 is the first cut under this regime. |
| G4 | `SECURITY.md` Response Timeline in effect | Holds **from v1.0 GA onwards** (target 2026-08-15) per [`SECURITY.md`](../../SECURITY.md). Pre-GA cadence is best-effort triage on the same intervals. |
| G5 | OpenSSF Best Practices passing tier maintained | Public dashboard at [bestpractices.dev/projects/12924](https://www.bestpractices.dev/en/projects/12924/passing); on-disk mirror at [`docs/security/openssf-best-practices.md`](../security/openssf-best-practices.md). |

### Explicitly **not yet** stable usable

- **Full ProofBundle verifier (predicate-based, not chain-based).**
  Tracked under P3.1 of
  [`p3_release_roadmap.md`](p3_release_roadmap.md). Until that ships,
  the CLI default path remains chain/report-oriented and must not be
  treated as a full ProofBundle verifier.
- **Runtime-honesty attestation surface.** Out of scope for the
  v1.0.x line.
- **On-chain settlement.** Out of scope per the `om-world` cluster
  delineation; Attestplane provides the evidence substrate, not a
  settlement layer.

---

## See also

- [`SECURITY.md`](../../SECURITY.md) — supported versions, response
  timeline, GPG plan.
- [`docs/roadmap/p3_release_roadmap.md`](p3_release_roadmap.md) —
  engineering-internal roadmap (deeper, per-gate view).
- [`docs/adr/0011-canonical-text-v1.md`](../adr/0011-canonical-text-v1.md) —
  `AP-EVD/1.0` canonical text rules.
- [`docs/adr/0016-rc-api-freeze.md`](../adr/0016-rc-api-freeze.md) —
  RC API freeze.
- [`docs/adr/0017-github-actions-release-cd.md`](../adr/0017-github-actions-release-cd.md) —
  release-CD design.
- [`docs/adr/0018-keyless-signing-and-slsa-provenance.md`](../adr/0018-keyless-signing-and-slsa-provenance.md) —
  forward-only Sigstore cosign + SLSA Build L3 regime (v1.0.9 cited as
  the proof point).
- [`docs/release/verifying-signatures.md`](../release/verifying-signatures.md) —
  the v1.0.9 worked example for verifying release signatures and
  provenance offline.
- [`docs/security/openssf-best-practices.md`](../security/openssf-best-practices.md) —
  passing-tier evidence.
- [`docs/security/openssf-silver-roadmap.md`](../security/openssf-silver-roadmap.md) —
  silver-tier roadmap (no committed dates beyond the 2026-08-15 GA
  anchor).
