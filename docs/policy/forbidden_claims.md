<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Forbidden Claims

Attestplane is positioned as an **attestation and audit substrate** for AI
agents. The founder is an active business/compliance lawyer, and the project
targets EU-regulated entities (EU AI Act, DORA, NIS2 scope). Public claims
that the substrate cannot substantiate are a legal liability — both as
misleading commercial speech and as a future enforcement vector if a
customer relies on an unverified claim.

This document lists claims that **must not appear** in Attestplane's public
surface (README, SDK READMEs, npm/PyPI descriptions, GitHub releases,
marketing copy, conference talks, social posts) until the claim is supported
by an externally verifiable artifact.

Counterpart documents: [`allowed_claims.md`](allowed_claims.md) lists what is
permitted; [`claims_policy.md`](claims_policy.md) defines enforcement.

## Replacement pattern

| Forbidden | Permitted |
|---|---|
| "EU AI Act Article 12 ready" | "designed toward EU AI Act Article 12 auditability" |
| "tamper-proof" | "tamper-evident" |
| "regulator-ready" | "auditor-oriented alpha substrate" |
| "production-grade" | "alpha; not for production without your own compliance review" |
| "certified" | "designed against [framework] criteria; no external certification claimed" |
| "cryptographically anchored" (default verifier) | "sidecar anchoring primitives exist; the CLI verifier remains chain/report-oriented" |
| "full ProofBundle verifier" | "`attestplane verify` performs chain/report-oriented checks only" |
| "signed/anchored verification" | "signing/anchoring are sidecar primitives unless a specific verifier path performs those checks" |
| "fully compliant" | obligation-registry-cited `implementation_status` (see below) |

## A. Regulatory compliance

- **"EU AI Act compliant"** / **"EU AI Act ready"** — Attestplane v0.0.1
  covers Art. 12(2)(a) field set only; Art. 12(1) retention, Art. 12(2)(b)-(d)
  sub-items, Art. 13-17 obligations are out of scope. The substrate is one
  component in an Article 12 implementation, not the whole implementation.
- **"DORA Article 8 compliant"** — DORA Art. 8 covers full ICT risk
  management; Attestplane provides the tamper-evident logging layer only.
- **"NIS2 compliant"** / **"GDPR compliant"** — neither framework is
  satisfied by a logging substrate alone.
- **"Regulator-approved"** / **"Notified-body audited"** — false unless a
  named notified body has actually reviewed the substrate (none has).
- **"Auditor-graded"** / **"Court-admissible evidence"** — admissibility is
  jurisdiction- and case-specific.

## B. Security posture

- **"Tamper-proof"** — SHA-256 hash chains are tamper-evident, not
  tamper-proof. Replace with "tamper-evident".
- **"Cryptographically anchored"** as a default verification claim —
  anchoring sidecar primitives exist, but the current `attestplane
  verify` path does not perform anchored verification. A release note
  may name a specific sidecar record type or provider only when it
  also states that the default CLI verifier is chain/report-oriented.
- **"Cryptographic signatures on every event"** / **"signed
  verification"** — signing sidecar primitives exist, but the current
  `attestplane verify` path does not perform signature verification.
  Do not imply every event is signed or that the CLI validates
  signatures unless that exact path performs the check.
- **"Zero-trust"** / **"No trust in Attestplane required"** — only
  defensible once cross-implementation conformance with a non-Attestplane
  verifier is demonstrated.

## C. Production / operations

- **"Production-ready"** / **"Production-grade"** / **"Battle-tested"** —
  substrate is alpha-grade.
- **"Enterprise-ready"** / **"SSO/SCIM/RBAC available"** — Enterprise tier
  is M8+ scope.
- **"High-availability"** / **"Active-active"** — v0.0.1 is single-process;
  multi-writer is M6.
- **"Multi-tenant"** / **"Tenant-isolated"** — tenant isolation is M6+.
- **"Durable"** / **"Crash-safe"** / **"Persistent"** as a blanket
  production claim — JSONL storage exists as an alpha backend, but
  durability, multi-writer behavior, destructive repair, and
  production operations remain deployer responsibilities unless a
  specific backend and test boundary are cited.

## D. Performance / scale

- **"High-throughput"** / **"Low-latency"** / **"Sub-millisecond"** — no
  published benchmark exists; conformance vectors test correctness, not
  performance.
- **"Scales to N events / second"** — never claim a specific number until a
  published benchmark exists with hardware specs and methodology.

## E. Process / governance

- **"SOC 2 certified"** / **"ISO 27001 certified"** / **"ISO 42001
  certified"** — false until external audit has completed and the
  certification letter exists. Today: zero external certifications.
- **"Autonomous deployment"** / **"Hands-off rollout"** — substrate is opt-in
  instrumentation; the deployer remains responsible for every consequential
  choice.
- **"Marketplace-validated"** / **"Customer-validated"** — no production
  customer has validated the substrate at v0.0.1.

## F. Cross-language and tooling

- **"Verified across all major AI agent frameworks"** — cross-language
  conformance today covers Python and TypeScript only. Rust SDK is M7.
- **"Full ProofBundle verifier"** / **"complete verifier"** —
  forbidden for the current CLI. The safe phrase is:
  "`attestplane verify` is chain/report-oriented with ProofBundle
  metadata and `policy_trace_refs` closure checks, and does not
  perform full ProofBundle, signature, anchor, or compliance
  certification verification."
- **"Runtime governance"** — forbidden when it implies runtime
  execution authority, scheduling, settlement, grant/revoke, billing,
  or policy enforcement. Attestplane adapters ingest and normalize
  evidence; the runtime remains responsible for authority and side
  effects.
- **"Drop-in replacement for [framework]"** — Attestplane is a substrate
  layer, not a replacement for any agent framework, logging system, or
  observability platform.

## G. Competitive framing (post-2026-05-17 positioning realignment)

The 20-agent competitive research captured in
[`competitive_positioning_upgrade_plan_20260517.md`](../architecture/competitive_positioning_upgrade_plan_20260517.md)
identified no direct competitors but five categories of adjacent
products. Public-facing material MUST observe the following claim
restrictions:

- **"Replaces LangSmith / LangFuse / Arize / Helicone /
  OpenLLMetry"** — false. Attestplane adds the cryptographic
  evidence layer those tools intentionally don't provide. The
  permitted phrasing is "complements" or "evidence layer beneath".
- **"Replaces Credo AI / Holistic AI / Modulos / Trustible /
  Saidot"** — false. Attestplane produces evidence those governance
  dashboards ingest as their `field_supported` data source. The
  permitted phrasing is "evidence source for [governance platform]"
  or "below the governance layer".
- **"EU AI Act compliant"** (and variants: "Art. 12 compliant",
  "DORA Article 8 compliant") — forbidden absolutely, even though
  LangSmith makes similar claims in its 2025+ marketing. Permitted
  phrasings are limited to the four implementation_status values
  below.
- **"First / only / leading / best [in category]"** in competitive
  context — forbidden. Lawyer-founder claim-safety discipline
  prohibits superlatives whose negation requires market-wide
  research the marketing copy doesn't show.
- **"Bitcoin-anchored timestamping"** / **"PoW-anchored"** — false
  for v0.1. The substrate uses RFC-3161 TSAs and (M5) Sigstore
  Rekor; Bitcoin / OpenTimestamps integration is not on the M5–M7
  roadmap.
- **"Successor to Amazon QLDB"** — false. QLDB reached
  end-of-support 2025-07-31 in a different category (managed ledger
  database). The categories are adjacent, not the same.
- **"SLSA-affiliated"** / **"SLSA member"** / **"OpenSSF project"**
  — false. The README's "SLSA-for-AI-Agents" phrasing describes
  architectural inspiration. Attestplane is published independently
  by Attestplane Pte. Ltd. The README disclaimer carries this
  language verbatim.
- **"eIDAS qualified trust service provider"** — false absolutely
  for the foreseeable future. Attestplane does not apply for QTSP
  status (Guardtime KSI's patent portfolio and existing slot make
  this defensive). Permitted phrasing: "consumes eIDAS qualified-TSA
  trust roots via `load_qualified_tsa_trust_roots()`".

## Obligation-registry implementation_status

When entries under `attestplane/obligations/` are cited in public material,
the entry's `implementation_status` is one of four values; **only these
phrasings are permitted**:

| Value | Public-facing wording |
|---|---|
| `mapping_target` | "framework mapping target" |
| `designed_toward` | "designed toward [obligation X]" |
| `field_supported` | "field set supports [obligation X]" |
| `verified_in_test` | "automated test verifies [obligation X] field presence" |

Never claim `compliant`, `certified`, `ready`, or `complete` in public
material referencing obligation entries until one of the four implementation
states is supplemented by an externally issued attestation (audit firm,
notified body, or court decision).

## Revisions

This document evolves with the project. Each new milestone typically retires
forbidden claims because the corresponding evidence ships. Removing an item
requires:

1. The corresponding feature or attestation to be merged on `main`.
2. An ADR or release note explicitly retiring the constraint.
3. The same-PR update of [`allowed_claims.md`](allowed_claims.md).
