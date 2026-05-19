<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Allowed Claims (public alpha)

This is the counterpart of [`forbidden_claims.md`](forbidden_claims.md): the
list of statements about Attestplane that are **supported by shipped
artifacts** as of the current milestone. Every claim here has at least one
of: (a) merged code path, (b) test in CI, (c) ADR with `Status: Accepted`,
(d) published artifact (TestPyPI, npm, GitHub Release).

If a claim is here, it is safe to use in README, SDK docs, release notes,
and marketing surface without further qualification.

## v0.0.1-alpha (as of 2026-05-17)

### Shipped substrate

- The SHA-256 hash chain primitive is implemented in
  `sdk/python/src/attestplane/hashchain.py` and `sdk/typescript/src/hashchain.ts`
  and is locked by [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md).
- The chain is **tamper-evident**: any single-event mutation, reorder, or
  deletion within a verified segment is detected by `verify_chain()`.
- Cross-language byte conformance between the Python and TypeScript SDKs is
  enforced on every CI run against
  `sdk/python/tests/conformance/vectors.json` (10 frozen vectors, schema
  version `1`).
- The EU AI Act **Article 12(2)(a) field set** (`session_id`,
  `reference_db_ref`, `matched_input_ref`, `human_verifier`) is built into
  `EventDraft` as first-class fields.
- GDPR Article 4(5) pseudonymization is enforced **at the type level** via
  the `SubjectRef` strong type (no raw PII can be silently written into the
  subject field).
- v0.0.1 is published to **TestPyPI** (sandbox) and **npm** (production with
  the `alpha` dist-tag); both artifacts carry the corresponding supply-chain
  attestation (OIDC trusted publishing for TestPyPI; npm `--provenance` for
  npm).
- GitHub Release v0.0.1-alpha ships the wheel + sdist + npm tarball +
  CycloneDX SBOM (JSON + XML), all signed with **Sigstore keyless cosign**;
  bundles are publicly verifiable against the Sigstore transparency log.
- Supply-chain hygiene: REUSE 3.3 compliance, CodeQL SAST on Python +
  GitHub Actions, OSV-Scanner daily, OSSF Scorecard weekly, reproducible
  wheel-build verification, all third-party GitHub Actions SHA-pinned.
- DCO sign-off is required on every commit; no CLA.

### Designed-toward but not yet shipped

These claims describe intent and design, not current behavior. They are
safe to use when paired with the milestone qualifier ("M5", "M6", or "M7").

- "Designed toward RFC-3161 anchoring" — design locked by
  [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md); implementation in M5.
- "Designed toward EU AI Act Article 12 auditability" — Art. 12(2)(a)
  fields shipped; obligation registry + verifier ship at M5.
- "Designed toward DORA Article 8 audit-trail obligations" — obligation
  registry ships at M5.

## v0.0.2-alpha (release candidate on `main` as of 2026-05-18)

These claims are safe to use ONCE v0.0.2-alpha is tagged and the
artifacts are published. Until publication, milestone-qualified
phrasings remain the safer form. None of these claims permits
production use, compliance readiness, broad verifier-completeness,
signed-verifier, anchored-verifier, or certification language.

### Architectural framing

- "**SLSA-for-AI-Agents**" — describes architectural inspiration and
  positioning analogue from the SLSA / OpenSSF supply-chain
  attestation framework. MUST be paired with the disclaimer that
  Attestplane is independent of the OpenSSF and the SLSA project (see
  README headline + section "What is Attestplane?").
- "**Alpha-grade dual-SDK tamper-evident evidence substrate**" —
  accurate description of v0.0.2-alpha (restricted canonicalization,
  SHA-256 hash-chain primitives, evidence payload schemas, sidecar
  signing/anchoring primitives, and read-only verifier predicates).
- "`attestplane verify` is chain/report-oriented" — accurate. The CLI
  replays bundle events and compares the embedded
  `verification_report` with the recomputed chain result, then fails
  closed on malformed ProofBundle metadata and `policy_trace_refs`
  closure. It does not perform full ProofBundle, signature, anchor, or
  compliance certification verification.
- "**Evidence layer beneath [observability tool]**" — accurate
  framing for the LangSmith / LangFuse / Arize Phoenix / Helicone /
  OpenLLMetry integration pattern.
- "**Evidence source for [governance platform]**" — accurate framing
  for the Credo AI / Holistic AI / Modulos / Trustible / Saidot
  integration pattern.

### Wire-format compatibility (post Track 1, ticket #29/#30)

- "**in-toto Statement compatible**" — after `as_in_toto_statement()`
  ships. Means: Attestplane evidence events serialize as valid
  in-toto Statement v1 envelopes with `predicateType =
  "https://attestplane.io/v1/agent-runtime-event"`. The custom
  predicateType is registered by Attestplane Pte. Ltd. and does NOT
  require OpenSSF blessing.
- "**Sigstore bundle compatible**" — after Track 1 ships.
- "**DSSE-wrapped attestation**" — accurate post-Track 1.

### Anchoring + LTV sidecars

- "**RFC-3161 anchoring sidecar primitives**" — accurate for source
  surfaces that explicitly mention the sidecar boundary. Public
  material MUST NOT say the default CLI performs anchored
  verification.
- "**eIDAS qualified-TSA compatible**" — accurate via
  `load_qualified_tsa_trust_roots()`. Does NOT mean Attestplane is
  itself a QTSP (forbidden per `forbidden_claims.md § G`).
- "**Sigstore Rekor anchor sidecar**" — accurate only for the shipped
  sidecar path and only when it does not imply default CLI anchored
  verification or partner endorsement.

### Integration adapters (post Track 3, ticket #31/#32)

- "**LangSmith adapter**" / "**LangFuse adapter**" — accurate AFTER
  the corresponding adapter module ships with end-to-end tests. MUST
  NOT imply endorsement by LangChain / LangFuse the companies; the
  adapter is built from publicly documented trace shapes.
- "**Translates LangSmith / LangFuse runs into Attestplane evidence
  events**" — accurate descriptive phrasing.

## v0.0.3-alpha (published public alpha as of 2026-05-19)

These claims are safe to use for the current public alpha line. None of these
claims permits production use, compliance readiness, broad verifier
completeness, signed-verifier, anchored-verifier, certification language, or
high-assurance supply-chain certification language.

### Published artifacts

- Python package `attestplane==0.0.3a0` is published to PyPI as a pre-release.
- TypeScript package `@attestplane/attestplane@0.0.9-alpha` is published to
  npm under the `alpha` and `latest` dist-tags. The `latest` dist-tag points at
  the current alpha for installability only; it is not a stable/GA claim.
- GitHub Release `v0.0.3-alpha` is a prerelease and carries five release
  assets: Python wheel, Python sdist, npm tarball, checksums, and artifact
  manifest.
- The `v0.0.3-alpha` tag is frozen; later documentation and validation reports
  on `main` do not move or redefine that release.

### Runtime and verifier scope

- "`attestplane verify` is chain/report-oriented" remains accurate. It replays
  bundle events, compares the embedded `verification_report` with the
  recomputed chain result, and fails closed on malformed ProofBundle metadata
  and `policy_trace_refs` closure.
- "RFC-3161 anchoring sidecar primitives" is accurate for the sidecar provider
  and verification code paths. Public material must still state that the
  default CLI verifier does not perform anchored verification.
- "FreeTSA SHA-512 ECDSA timestamp verification is supported" is accurate
  after the 2026-05-19 recovery fix and live `nightly-anchor` verification.
- "Release provenance hygiene" is accurate for npm provenance, PyPI trusted
  publishing, artifact checksums, release manifests, SBOM generation, CodeQL,
  OSV, OSSF Scorecard, and reproducible-build gates. It must not be shortened
  into certification, SLSA-level, or production security language.
- "Stable verifier error codes" is accurate for the `VERIFY_*` v1 taxonomy.
  The codes classify verifier outcomes; they do not certify legal compliance.
- "Commit-then-redact retention/deletion proof markers" is accurate for
  `retention_proofs` shape and event-reference checks. It must not be phrased
  as GDPR compliance, legal sufficiency, or proof of deletion from external
  processors.

### Issue and limitation status

- Closed nightly FreeTSA failures (#9 and #11) may be described as diagnosed
  and recovered. They should not be described as proof that every external TSA
  outage is impossible.
- Issue #7 is resolved by the AIA-12 aligned profile, verifier independence
  model, and commit-then-redact ADR. Public language may describe the
  conservative stance: AIA-12-aligned substrate mapping, not EU AI Act
  compliance certification; verifier independence via OSS deterministic
  verifiers, not a closed API trust root; and retention/deletion handling as
  deployer policy with minimization and redaction commitments.

## Implementation-status phrasing rule

When a claim references an obligation registry entry under
`attestplane/obligations/`, the public phrasing must use the entry's
`implementation_status` value. Only four values are permitted; see
[`forbidden_claims.md` § Obligation-registry implementation_status](forbidden_claims.md#obligation-registry-implementation_status).

## Update cadence

This document is updated at every milestone (M5, M6, M7, M8+) and at every
release. New claims may be added when:

1. The corresponding feature is merged on `main`.
2. CI verifies the behavior the claim describes.
3. An ADR or release note records the addition.

Removing a claim from this list requires a release note and is generally
only done for security-driven retractions or scope changes.
