<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Threat model — v1 (GSN-style Claims / Arguments / Evidence)

## 1. Status and scope

- **Status**: Alpha — evidence-supporting alignment mapping, NOT compliance certification.
- **Version**: `v1` — pre-GA threat model covering the `v1.0.x` release line.
- **Source planning issue**: [#61](https://github.com/attestplane/attestplaneissues61)
- **Traceability matrix**: [`docs/spec/compliance-traceability-matrix.md`](../spec/compliance-traceability-matrix.md)
- **Posture**: This is an **evidence-supporting** document. It is **not** a
  compliance certification, not a conformity assessment, and not a
  notified-body opinion. The AIA-12 *aligned* framing in
  [`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md)
  is unchanged by this document.
- **Forward only** per [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md):
  historical tags below `v1.0.x` are not re-evaluated against this model.
- **Supersedes** the snapshot in
  [`threat-model-v0.0.5-alpha.md`](threat-model-v0.0.5-alpha.md), which is
  retained as a historical anchor.
- **Methodology**: Goal Structuring Notation (GSN)-style **Claims →
  Arguments → Evidence** triples per attack, with a STRIDE × interface
  cross-check and an explicit residual-risk section.

## 2. System under analysis

The substrate scope per [ADR-0004 §1](../adr/0004-aios-to-attestplane-boundary.md)
and [`docs/architecture/verifier_independence.md`](../architecture/verifier_independence.md):

- **SDK surface**: Python (`sdk/python`) and TypeScript
  (`sdk/typescript`); auditor-API on top.
- **Verifier surface**: independent SDK-level chain + signature + anchor
  verification; no Attestplane-hosted endpoint in the verification path.
- **Anchor adapters**: RFC 3161 TSA providers per
  [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md); Sigstore Rekor
  redundant anchor per
  [ADR-0006](../adr/0006-sigstore-rekor-redundant-anchor.md).
- **Signing providers**: `InMemoryKeyProvider`, `FileKeyProvider`,
  `EnvKeyProvider`, `MultiSignerProvider` per
  [ADR-0005](../adr/0005-event-signing-scheme.md). Sigstore keyless cosign
  for release-asset signing per
  [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md).

Trust roots (re-derivable by an external party without contacting
Attestplane infrastructure):

- Sigstore Fulcio root + Rekor public key (embedded in `cosign` /
  `slsa-verifier`).
- RFC 3161 TSA root certificates published by each TSA operator (FreeTSA,
  DigiCert, etc.); also distributable via `trust_roots/` per ADR-0003 §6.
- `TrustRoots` file (YAML / JSON) listing accepted `key_id` values for
  substrate-operator event signing per ADR-0005 §6.

Out of scope per ADR-0004 §1:

- Deployer-side ingest, retention policy, sidecar storage, lawful basis
  determination, controller obligations, and any production deployment
  configuration. Those remain the deployer's responsibility.

## 3. Adversary model

Six adversary tiers anchor the threat list in §5. The model is
intentionally pessimistic and explicitly admits the boundary above which
the substrate alone cannot defend.

- **AD1 — External attacker**. No system access; observes public release
  artifacts, published Rekor entries, and TSA query responses.
- **AD2 — Compromised AI agent**. Emits malicious or fabricated events
  through a legitimate SDK call path. Detectable post-hoc through chain
  introspection, but can persist undetected for some window before
  review.
- **AD3 — Compromised deployer ops**. Mid-tier trust. Can rewrite local
  storage but cannot forge third-party RFC 3161 tokens, Sigstore Rekor
  log entries, or substrate-operator signatures without also compromising
  AD4-tier credentials.
- **AD4 — Compromised single maintainer (xz scenario)**. A maintainer
  key, GitHub access token, or release-bot identity is captured. Can
  push code and produce signed releases until detected.
- **AD5 — State-level actor**. Long-term capability: simultaneous
  supply-chain insertion across multiple ecosystems; cryptanalytic
  resources beyond the current public state of the art (harvest-now,
  decrypt-later posture against pre-quantum primitives).
- **AD6 — Mid-tier offline auditor**. Not adversarial in intent, but the
  threat model must hold under their review: an honest auditor with an
  offline export must be able to re-derive integrity claims without
  contacting Attestplane infrastructure.

## 4. STRIDE × interface mitigation table

Four substrate interfaces × six STRIDE categories. Each cell names the
mitigation and the ADR or file that documents it, then the residual.

| Interface ↓ / STRIDE → | Spoofing | Tampering | Repudiation | Information Disclosure | Denial of Service | Elevation of Privilege |
|---|---|---|---|---|---|---|
| **Event emit** (`append()`) | Caller identity is deployer-scoped; `SubjectRef` strong type forbids raw PII in subject field (ADR-0002 §5). **Residual**: payload spoofing inside the deployer trust boundary. | Append-only hash chain; `prev_hash` linkage; canonical-text v1 (ADR-0002, ADR-0011). **Residual**: pre-discovery tampering of unanchored tail. | Sequence + `event_id` (UUIDv7) plus per-event or segment-head signature (ADR-0005). **Residual**: pre-signing-policy events emitted before the first segment-head. | `SubjectRef` scheme constrains shape; commit-then-redact profile per [ADR-0015](../adr/0015-retention-deletion-proof-profile.md) keeps raw PII out of chain. **Residual**: caller-side payload misuse. | `append()` is local and never blocks on TSA reachability (ADR-0003 §4). **Residual**: deployer-side storage exhaustion. | Substrate components hold key **access**, not **authority** (ADR-0004 §1; ADR-0005 §4 forbidden-verb gate). **Residual**: deployer-side key-store privilege escalation outside the substrate boundary. |
| **Signing** | `key_id` derivation pinned to SHA-256(SPKI) (ADR-0005 §5). **Residual**: trust-roots-file misconfiguration. | `signed_payload` carries the exact bytes signed (ADR-0005 §1). **Residual**: signing-key compromise pre-discovery. | Ed25519 + `TrustRoots` validity windows (ADR-0005 §6). **Residual**: lost or destroyed `TrustRoots` snapshot at audit time. | Public-key DER is not secret; private key never leaves provider boundary (ADR-0005 §4). **Residual**: AD4 maintainer-workstation private-key extraction. | Sync-only API in TS; background worker in Python (ADR-0005 §3, §9). **Residual**: storage-layer back-pressure. | Forbidden-verb gate on `KeyProvider` subclasses (ADR-0005 §4). **Residual**: monkey-patched subclasses at runtime (reviewer-detectable). |
| **Anchoring** | TSA / Rekor provider identity pinned via `tsa_provider_id` (ADR-0003 §1; ADR-0006 §3). **Residual**: malicious provider impersonating a known `tsa_provider_id`. | LTV freeze: cert chain + OCSP at issuance (ADR-0003 §6). **Residual**: post-issuance LTV-evidence loss in storage. | Independent third-party RFC 3161 time + Rekor `integratedTime` (ADR-0003, ADR-0006). **Residual**: TSA / Rekor collusion (mitigated by plurality recommendation). | Anchors store hashes, not raw events (ADR-0003 §1, ADR-0006 §3, GDPR Art. 5(1)(c) intent). **Residual**: hash pre-image grinding on low-entropy values (see AT-05). | `Anchorer` is off the `append()` critical path; retries with backoff (ADR-0003 §4). **Residual**: persistent multi-TSA outage produces `unanchored` tail. | No anchor-time privileged operation against substrate state (ADR-0003 §4). **Residual**: none material. |
| **Verifier** | Trust roots are external files chosen by the verifier operator (ADR-0005 §6; ADR-0018 §3). **Residual**: verifier operator misconfigures `trust_roots`. | Pure functions, no I/O in core verification (ADR-0002 §3). **Residual**: downstream "roll-your-own" verifier introduces drift. | `verify_chain_full` returns forensic-grade per-step results (ADR-0005 §7). **Residual**: verifier operator ignores `expired_key` / `unknown_key` outcomes. | Verifier does not phone home; offline-verifiable by design (`docs/architecture/verifier_independence.md`). **Residual**: side-channel inference from verification timing in adversarial harnesses. | Verifier is bounded by input size; no recursion in canonical-text v1 (ADR-0011). **Residual**: pathological bundle sizes at the deployer ingress. | Verifier has no privileged surface. **Residual**: none material. |

## 5. Threat list (AT-01 .. AT-14)

Each entry follows GSN structure: **Claim** (what is asserted),
**Argument** (why it follows from the system design), **Evidence**
(which artifact in the repository supports it), **Residual** (what
remains open).

### AT-01 — Tampering with historical events

- **Claim**: An attacker who gains read/write access to local storage
  after an event has been appended cannot rewrite that event without
  detection.
- **Argument**: Hash-chain `prev_hash` linkage + segment-head or
  per-event signatures + third-party RFC 3161 anchoring together require
  the attacker to forge the chain *and* the signature *and* a TSA token
  bearing an earlier `genTime`. The first two require AD4-tier key
  compromise; the third requires AD3+AD5 (TSA collusion). The combined
  attack surface is strictly larger than any single mitigation.
- **Evidence**:
  [ADR-0002 §3 (`verify_chain`)](../adr/0002-substrate-data-model-and-hash-chain-v0.md),
  [ADR-0005 §1, §7 (signatures)](../adr/0005-event-signing-scheme.md),
  [ADR-0003 §1, §5 (anchors)](../adr/0003-tsa-rfc-3161-anchoring.md).
- **Residual**: A signing-key compromise discovered only **after** the
  attacker has appended events with the compromised key. Mitigated by
  short signing-key validity windows in `TrustRoots` (ADR-0005 §6) but
  not eliminated.

### AT-02 — Forged anchoring (single-TSA collusion)

- **Claim**: An attacker who controls one anchor provider cannot produce
  a backdated chain-tip attestation that survives external verification.
- **Argument**: ADR-0006 §5 generalises ADR-0003 §2's plurality
  recommendation to ≥ 2 independent anchor providers, with at least one
  Sigstore Rekor instance as a public transparency log. A single
  compromised provider can be cross-checked against the redundant
  anchor.
- **Evidence**: [ADR-0003 §2](../adr/0003-tsa-rfc-3161-anchoring.md),
  [ADR-0006 §5](../adr/0006-sigstore-rekor-redundant-anchor.md).
- **Residual**: Simultaneous compromise of both anchors (an RFC 3161 TSA
  **and** Sigstore Rekor) is outside the substrate's control. The
  substrate documents the residual and ships plurality as the
  recommended deployment, not the only deployment.

### AT-03 — Replay of historical events

- **Claim**: An adversary cannot inject a previously-recorded event
  into the chain at a later position without detection.
- **Argument**: `seq` is monotonic per ADR-0002 §4; `prev_hash` binds
  every event to its predecessor; the canonical-text v1 form
  (ADR-0011) renders the entire chain a single hash-linked structure.
- **Evidence**:
  [ADR-0002 §4 (`ChainHead`)](../adr/0002-substrate-data-model-and-hash-chain-v0.md),
  [ADR-0011 (canonical-text v1)](../adr/0011-canonical-text-v1.md).
- **Residual**: Replay against a substrate **before** its first
  observation (e.g., during pre-deployment seeding). Mitigated by the
  v1 SDK rejecting non-genesis initial events, but the residual against
  an adversarially-prepared genesis state is documented.

### AT-04 — Long-term verifier viability (post-GA)

- **Claim**: A bundle produced under the `v1.0.x` line will remain
  verifiable by a future SDK or by an independently-derived verifier
  after the substrate has evolved beyond v1.
- **Argument**: Schema is frozen per ADR-0002 §7; conformance vectors
  in `vectors.json` are a permanent external contract per ADR-0002 §11;
  canonical-text v1 fixes the byte-level shape per ADR-0011; adapter
  fixtures are pinned per
  [ADR-0014](../adr/0014-adapter-conformance-fixture-pinning.md).
- **Evidence**:
  [ADR-0002 §7, §11](../adr/0002-substrate-data-model-and-hash-chain-v0.md),
  [ADR-0011](../adr/0011-canonical-text-v1.md),
  [ADR-0014](../adr/0014-adapter-conformance-fixture-pinning.md).
- **Residual**: Future migration semantics (a `schema_version = 2`
  transition) are constrained to be additive per ADR-0002 §"Reversibility",
  but a substrate that has emitted under v1 then v2 will require
  dual-verification tooling forever.

### AT-05 — PII leakage via low-entropy hash pre-image

- **Claim**: An auditor reading a bundle that committed personal data
  through a hash cannot trivially recover the underlying value.
- **Argument**: The commit-then-redact profile per
  [ADR-0015](../adr/0015-retention-deletion-proof-profile.md) keeps raw
  personal data out of the append-only chain. Hashes and content
  references are recorded; raw material lives in a controller-owned
  sidecar.
- **Evidence**: [ADR-0015](../adr/0015-retention-deletion-proof-profile.md).
- **Residual**: For low-entropy domains (email addresses, dates of
  birth, national-ID fragments), a naive unsalted SHA-256 is grindable.
  Mitigated when the caller uses `SubjectRef.scheme = "sha256_salted"`
  or commits to an opaque reference (ADR-0002 §5), but the substrate
  cannot force this discipline on the caller. AT-12 covers the related
  selective-disclosure gap.

### AT-06 — Selective-disclosure attack on an offline export

- **Claim**: A controller-owned export delivered to one auditor does not
  expose unrelated subjects' material.
- **Argument**: The commit-then-redact profile partitions deletable
  material into a controller-owned sidecar (ADR-0015 §1–§3). The
  controller chooses which sidecar slices accompany a given export.
- **Evidence**: [ADR-0015 §1–§5](../adr/0015-retention-deletion-proof-profile.md).
- **Residual**: There is **no cryptographic selective-disclosure
  primitive** (e.g., BBS+ signatures, zero-knowledge proofs of
  inclusion) in the `v1.0.x` substrate. Selective disclosure is a
  policy-and-process control, not a cryptographic guarantee in v1.
  Tracked as forward-looking work in §7.

### AT-07 — Maintainer key compromise (xz-style supply-chain attack)

- **Claim**: A single maintainer whose credentials are captured cannot
  silently ship a malicious release through the project's CD pipeline.
- **Argument**: Sigstore keyless cosign per ADR-0018 §1 binds every
  release asset to the GitHub Actions OIDC identity; SLSA Build L3
  provenance per ADR-0018 §2 records the source-repo + workflow + ref
  triple. Both records publish to the Sigstore public transparency log.
  DCO sign-off is required per `CONTRIBUTING.md`; supermajority release
  gates are recorded in `GOVERNANCE.md` §8.
- **Evidence**:
  [ADR-0018 §1, §2, §3](../adr/0018-keyless-signing-and-slsa-provenance.md),
  [`SECURITY.md`](../../SECURITY.md),
  [`GOVERNANCE.md` §8](../../GOVERNANCE.md).
- **Residual**: Bus-factor remains one active maintainer at the time of
  this document (`openssf-silver-roadmap.md` row `bus_factor` =
  `unmet`). A second maintainer + a published `MAINTAINERS.md` are
  tracked as a future commitment, with no date promised.

### AT-08 — Quantum cryptanalysis (harvest-now, decrypt-later)

- **Claim**: None for the current cryptographic suite. The substrate's
  primitives are pre-quantum.
- **Argument**: SHA-256 and Ed25519 are explicitly pre-quantum. AD5 with
  a future cryptographically-relevant quantum computer could forge
  signatures or find hash collisions retroactively.
- **Evidence**:
  [ADR-0005 §3, §8](../adr/0005-event-signing-scheme.md),
  [`openssf-silver-roadmap.md` row `crypto_algorithm_agility`](openssf-silver-roadmap.md).
- **Residual**: Full. A post-quantum cryptography (PQC) migration plan
  is documented as forward-looking work in §7. No date is promised. The
  rotation playbook is named as a low-touch item in
  `openssf-silver-roadmap.md` (row "low-hanging item 4").

### AT-09 — Supply-chain compromise of a build-time dependency

- **Claim**: A downstream consumer can detect a release whose
  dependency closure has been tampered with after the fact.
- **Argument**: CycloneDX SBOMs are produced for every release;
  dependencies are pulled via pinned manifests per
  `openssf-silver-roadmap.md` row `external_dependencies`; Sigstore
  keyless cosign signs every primary asset; SLSA Build L3 provenance
  records the build environment. The reproducible-build workflow
  (`reproducible-build.yml`) provides a re-derivation path.
- **Evidence**: [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md),
  [`openssf-silver-roadmap.md` rows `external_dependencies`,
  `signed_releases`, `build_repeatable`](openssf-silver-roadmap.md).
- **Residual**: Typosquatting on the publishing ecosystems (PyPI / npm)
  and maintainer mistake during a dependency bump remain non-zero. OSV
  Scanner + Dependabot + Scorecard provide detection, not prevention.

### AT-10 — TSA endpoint compromise

- **Claim**: A single compromised TSA endpoint cannot invalidate the
  substrate's temporal-integrity claim when plurality is configured.
- **Argument**: The recommended deployment per ADR-0003 §2 and
  ADR-0006 §5 is ≥ 2 independent anchor providers (e.g., FreeTSA +
  Sigstore Rekor, or DigiCert + Sigstore Rekor). A single compromised
  anchor is cross-checked against the second.
- **Evidence**: [ADR-0003 §2](../adr/0003-tsa-rfc-3161-anchoring.md),
  [ADR-0006 §5](../adr/0006-sigstore-rekor-redundant-anchor.md).
- **Residual**: The substrate ships no **quorum semantics** in v1 — the
  verifier accepts any single valid anchor per seq as evidence of
  temporal binding (ADR-0006 §4.1). A "≥ k of n must match" predicate
  is forward-looking work; see §7.

### AT-11 — Verifier code compromise (downstream "roll your own")

- **Claim**: The substrate-published verifier produces consistent
  results regardless of which independent SDK the auditor uses.
- **Argument**: Two SDKs (Python, TypeScript) are released in lockstep
  with a cross-language conformance gate per ADR-0002 §11 and
  ADR-0005 §8. `signature_vectors.json` and `anchor_vectors.json` are
  the permanent external contracts that pin byte stability.
- **Evidence**:
  [ADR-0002 §11](../adr/0002-substrate-data-model-and-hash-chain-v0.md),
  [ADR-0005 §8](../adr/0005-event-signing-scheme.md),
  [`docs/architecture/verifier_independence.md`](../architecture/verifier_independence.md).
- **Residual**: A downstream verifier implementer who reimplements the
  spec incorrectly introduces drift. The substrate publishes the
  conformance fixtures as the authoritative contract; the residual
  remains an incentive concern outside the substrate's enforceable
  surface.

### AT-12 — PII export to an unauthorised auditor

- **Claim**: An auditor receiving an export cannot see material outside
  the controller-approved scope.
- **Argument**: The commit-then-redact profile and the controller-owned
  sidecar (ADR-0015 §2–§5) place per-auditor disclosure control in the
  hands of the deployer, not the substrate. The verifier never assumes
  it can read material that has been redacted from the sidecar.
- **Evidence**: [ADR-0015](../adr/0015-retention-deletion-proof-profile.md).
- **Residual**: No cryptographic per-auditor selective disclosure in v1
  (see AT-06). The controller bears the policy responsibility.

### AT-13 — Clock skew or local-time manipulation

- **Claim**: The substrate's temporal claims do not depend on its
  local clock.
- **Argument**: ADR-0002 §10 explicitly downgrades
  `AuditEvent.timestamp` to "claimed time" once TSA anchoring is
  active. The authoritative time is the RFC 3161 `genTime` (ADR-0003 §4)
  or the Rekor `integratedTime` (ADR-0006 §3). A `clock_skew_warning`
  is recorded when local-time disagrees with TSA time by > 60s
  (ADR-0003 §4 failure-mode table).
- **Evidence**:
  [ADR-0002 §10](../adr/0002-substrate-data-model-and-hash-chain-v0.md),
  [ADR-0003 §4](../adr/0003-tsa-rfc-3161-anchoring.md),
  [ADR-0006 §3](../adr/0006-sigstore-rekor-redundant-anchor.md).
- **Residual**: A pre-anchor window (≤ 64 events or ≤ 60 s, whichever
  fires first per ADR-0003 §3) where only the local clock is recorded.
  Per-event anchoring closes this for high-value events at the cost of
  more anchor traffic (ADR-0003 §3).

### AT-14 — Substrate-operator signing-key extraction

- **Claim**: The substrate's signing primitives minimise the value of
  a private-key theft.
- **Argument**: Release-asset signing uses Sigstore **keyless** cosign
  (ADR-0018 §1) — there is no long-lived private key in CI to steal.
  Event-signing keys are accessed through `KeyProvider` abstractions
  whose lifecycle (creation, rotation, retirement) is the deployer's
  operational responsibility per ADR-0004 §1 and the ADR-0005 §4
  forbidden-verb gate.
- **Evidence**:
  [ADR-0018 §1](../adr/0018-keyless-signing-and-slsa-provenance.md),
  [ADR-0005 §4](../adr/0005-event-signing-scheme.md),
  [ADR-0004 §1](../adr/0004-aios-to-attestplane-boundary.md).
- **Residual**: Pre-GA, GPG-signed git tags depend on the
  `security@attestplane.com` GPG key being published (tracked in
  `SECURITY.md` and `openssf-silver-roadmap.md` row
  `crypto_credential_agility`). Until that lands, maintainer-workstation
  signing keys for tag verification are a documented residual.

## 6. Residual-risk summary

As of `v1.0.x` pre-GA, the following AT-X items carry residuals that
are partially open and must be disclosed in any audit packet generated
under this model:

- **AT-05**: low-entropy hash pre-image grinding without
  `SubjectRef.scheme = "sha256_salted"`.
- **AT-06 / AT-12**: no cryptographic selective-disclosure primitive in
  v1; disclosure is a controller-policy control.
- **AT-07**: bus-factor remains one active maintainer; `MAINTAINERS.md`
  is a future artifact.
- **AT-08**: full residual against post-quantum AD5; PQC plan is
  forward-looking.
- **AT-10**: no quorum-of-anchors predicate; verifier accepts any single
  valid anchor.
- **AT-14**: maintainer-workstation GPG signing keys for git tags
  pending GPG-key publication.

Each residual maps to a forward-looking mitigation in §7.

## 7. Forward-looking mitigations (no dates promised)

This section names documented future work. Per the R11 discipline of
[`openssf-silver-roadmap.md`](openssf-silver-roadmap.md), the only
schedule anchor used here is the v1.0 GA target (`2026-08-15`) already
published in [`SECURITY.md`](../../SECURITY.md). Everything below is a
**direction**, not a commitment.

- **Post-quantum cryptography migration** (closes AT-08). Rotation
  playbook is named in `openssf-silver-roadmap.md` low-touch item 4. A
  dedicated ADR (TBD) is anticipated.
- **Quorum-of-anchors predicate** (closes AT-10). A future ADR will
  formalise "≥ k of n providers must agree" as an opt-in verifier
  parameter.
- **Cryptographic selective disclosure** (closes AT-06, AT-12).
  BBS+ signatures and ZKP-of-inclusion are candidate primitives. A
  dedicated ADR (TBD) is anticipated.
- **`MAINTAINERS.md` + second active maintainer** (closes AT-07).
  Tracked in `GOVERNANCE.md` §8.5 and `openssf-silver-roadmap.md` row
  `bus_factor`; community-growth decision, no date promised.
- **GPG key publication for `security@attestplane.com`** (closes
  AT-14's GPG-tag residual). Tracked in `SECURITY.md` and
  `openssf-silver-roadmap.md` row `crypto_credential_agility`.
- **Third-party cryptanalysis review** (additional assurance posture
  for AT-01, AT-02, AT-08). Governance decision, no date promised.

## 8. Verification methodology

How an external auditor re-derives the claims in §5 from the
substrate's own artifacts, without contacting Attestplane
infrastructure:

1. Obtain the published bundle (events + signatures + anchors).
2. Recompute the chain hashes from the SDK-published conformance
   vectors `sdk/python/tests/conformance/vectors.json` (ADR-0002 §11);
   confirm byte equality.
3. Verify per-event or segment-head signatures against the deployer's
   published `TrustRoots` file (ADR-0005 §6, §7).
4. Verify anchors against TSA root certificates obtained from each
   TSA operator's publication site, and against Sigstore Rekor's public
   key embedded in `cosign` / `slsa-verifier` (ADR-0003 §6,
   ADR-0006 §3).
5. Re-derive supply-chain integrity for the SDK itself via
   `cosign verify-blob` against the release-asset OIDC identity and
   `slsa-verifier verify-artifact` against the SLSA provenance
   (ADR-0018 §3,
   [`docs/release/verifying-signatures.md`](../release/verifying-signatures.md)).
6. Confirm the export carries the expected redaction-evidence events
   per ADR-0015 §5 when sidecar material has been removed.

Steps 1–6 are independent. A failure in any single step is recoverable
by re-running with a different SDK or verifier (Python ↔ TypeScript)
per the cross-language conformance discipline.

## 9. Out of scope

This document is explicitly **not**:

- a legal opinion on any framework (EU AI Act, GDPR, DORA, NIS2,
  ISO/IEC 42001, NIST AI RMF);
- a specification of any deployer's configuration;
- a compliance certification, conformity assessment, or notified-body
  determination for any framework;
- a modification of the AIA-12 *aligned* profile framing in
  [`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md),
  which is a sibling document and is intentionally not modified here.

## 10. Relationship to existing artifacts

- Sibling spec: [`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md) — Article 12 *aligned* profile, untouched by this document.
- Sibling architecture: [`docs/architecture/verifier_independence.md`](../architecture/verifier_independence.md) — verifier independence rule cited in §2 and §5/AT-11.
- Sibling security: [`docs/security/openssf-best-practices.md`](openssf-best-practices.md) — passing-tier mirror.
- Sibling roadmap: [`docs/security/openssf-silver-roadmap.md`](openssf-silver-roadmap.md) — this document is the `assurance_case` row evidence pointer.
- Disclosure process: [`SECURITY.md`](../../SECURITY.md) — private vulnerability reporting, response-timeline targets, hardening guidance.
