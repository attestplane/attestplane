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
| "cryptographically anchored" (today) | "designed for RFC-3161 anchoring (ships v0.1 / M5)" |
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
- **"Cryptographically anchored"** (in present tense) — RFC-3161 anchoring
  is M5 / ADR-0003 design; v0.0.1 has no external anchoring.
- **"Cryptographic signatures on every event"** — event signing is M7
  (anticipated ADR-0004).
- **"Zero-trust"** / **"No trust in Attestplane required"** — only
  defensible once cross-implementation conformance with a non-Attestplane
  verifier is demonstrated.

## C. Production / operations

- **"Production-ready"** / **"Production-grade"** / **"Battle-tested"** —
  substrate is v0.0.1-alpha.
- **"Enterprise-ready"** / **"SSO/SCIM/RBAC available"** — Enterprise tier
  is M8+ scope.
- **"High-availability"** / **"Active-active"** — v0.0.1 is single-process;
  multi-writer is M6.
- **"Multi-tenant"** / **"Tenant-isolated"** — tenant isolation is M6+.
- **"Durable"** / **"Crash-safe"** / **"Persistent"** — v0.0.1 is in-memory
  only. JSONL backend ships at v0.1 / M5; SQLite at M6; Postgres at M7.

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
- **"Drop-in replacement for [framework]"** — Attestplane is a substrate
  layer, not a replacement for any agent framework, logging system, or
  observability platform.

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
