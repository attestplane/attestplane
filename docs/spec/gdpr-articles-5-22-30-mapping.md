<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# GDPR Articles 5 / 22 / 30 mapping for Attestplane

## Status

Alpha — evidence-supporting alignment mapping, NOT compliance certification.

This document maps Attestplane's substrate primitives to specific articles of
Regulation (EU) 2016/679 (the General Data Protection Regulation, GDPR). It
is not a legal opinion, not a Data Protection Impact Assessment, not a
statement that any deployed system satisfies GDPR, and not a substitute for
controller- or processor-specific legal review.

## Purpose

GDPR places obligations on controllers and processors that often require
durable, reviewable records of how personal data was handled — including
which automated decision was taken, who handled it, when, under which policy
version, and how integrity is preserved. Attestplane provides primitives
(append-only hash chain, role-bound event fields, signed events, anchored
timestamps, commit-then-redact retention) that a controller may cite as one
input to its GDPR record-keeping and accountability work.

This crosswalk lists the cited primitives; it does not interpret the law for
any specific controller.

## Source metadata

- **Version**: `alpha-2026-05`
- **Source planning issue**: [#61](https://github.com/attestplane/attestplane/issues/61)
- **Traceability matrix**: [`docs/spec/compliance-traceability-matrix.md`](compliance-traceability-matrix.md)

The traceability matrix records the claim -> argument -> evidence chain for
this mapping and the explicit gap rows tied to issue #61.

## Explicit non-claims

This crosswalk does not claim:

- compliance certification with the GDPR or any national implementation,
- a legal opinion on the sufficiency of Attestplane evidence for any GDPR
  obligation,
- replacement for controller or processor obligations under the GDPR,
- automation of Article 17 right-to-erasure outcomes,
- replacement for Data Protection Impact Assessments (DPIA, Article 35),
- a "certified mechanism" under Article 42, or
- forward-looking guarantees beyond this alpha mapping.

The phrase "evidence-supporting alignment mapping, NOT compliance
certification" applies to every row below.

## Profile identifier

```text
https://attestplane.io/profiles/gdpr/alpha-2026-05
```

The identifier is versioned because the mapping is a public contract. Future
revisions create a new profile identifier rather than silently changing the
meaning of this one. The `alpha-2026-05` suffix is a calendar-month stamp on
when the mapping was drafted; it is not a forward commitment to a future
release.

## Control-family → primitive table

| GDPR article / principle | Attestplane primitive providing supporting evidence | Citation file |
|---|---|---|
| Art. 5(1)(f) — integrity and confidentiality | SHA-256 hash chain plus Ed25519 event signing, optionally anchored via RFC 3161 and Sigstore | `docs/adr/0002-substrate-data-model-and-hash-chain-v0.md`, `docs/adr/0005-event-signing-scheme.md`, `docs/adr/0003-tsa-rfc-3161-anchoring.md`, `docs/adr/0006-sigstore-rekor-redundant-anchor.md` |
| Art. 5(1)(e) — storage limitation | commit-then-redact retention and deletion profile, which preserves chain continuity while allowing controller-driven removal of subject material | `docs/adr/0015-retention-deletion-proof-profile.md` |
| Art. 5(2) — accountability | entire substrate, with audit-export readable offline against the open verifier | `docs/spec/aia-12-aligned-profile.md` (sibling, unmodified), `docs/adr/0010-verification-reason-codes.md` |
| Art. 22 — automated individual decision-making | decision events and human-intervention events in the evidence taxonomy | `docs/spec/evidence-event-taxonomy-v1.md`, `docs/adr/0008-evidence-event-taxonomy-v1.md` |
| Art. 30 — records of processing activities | continuity checkpoints plus auditor export profile that pins schema and verifier versions | `docs/adr/0002-substrate-data-model-and-hash-chain-v0.md`, `docs/spec/aia-12-aligned-profile.md` |
| Art. 17 — right to erasure | commit-then-redact retention and deletion profile (see non-claim below) | `docs/adr/0015-retention-deletion-proof-profile.md` |
| Art. 32 — security of processing | event signing scheme that makes tampering detectable | `docs/adr/0005-event-signing-scheme.md` |
| Art. 4(5) — pseudonymisation | pseudonymous `SubjectRef`-style references recommended by the AIA-12 aligned profile | `docs/spec/aia-12-aligned-profile.md` (sibling, unmodified) |

Each row is alignment scaffolding only. The controller is responsible for
deciding whether the substrate, combined with its own controls, meets a
specific GDPR obligation in its specific processing context.

## Article 17 explicit non-claim

The Article 17 row above is intentionally narrow. Attestplane's
commit-then-redact profile is an evidence substrate that is intended to be
compatible with controller-driven erasure: deletable subject material is held
in controller-owned sidecar stores, and a redaction or deletion evidence
event is appended to make the removal action reviewable while preserving
chain continuity.

That is "evidence substrate supports GDPR erasure flows", NOT "GDPR
right-to-erasure compliant". Legal sufficiency of any specific erasure
operation requires controller-specific review, including but not limited to:

- whether the controller has a lawful basis for retaining the residual
  redaction / deletion evidence event,
- whether the sidecar store's deletion is itself sufficient under the
  controller's threat model,
- whether the controller's notification obligations under Article 19 are
  satisfied through other channels, and
- whether downstream recipients of personal data have been informed.

The substrate cannot substitute for any of those determinations.

## How a controller may cite Attestplane evidence

A controller or processor working through GDPR documentation may cite
Attestplane evidence in any of the following ways. None of these citations
turns Attestplane into a certifying authority or a supervisory authority:

- as supporting evidence for Article 5(2) accountability narratives,
- as supporting evidence for Article 30 records of processing,
- as supporting evidence for Article 32 integrity and resilience controls,
- as supporting evidence for Article 22 documentation of automated decisions,
- as supporting evidence for Article 17 erasure-handling records (with the
  Article 17 non-claim above).

In every case the controller cites a concrete Attestplane export bundle, the
verifier version used, and the trust roots accepted at the time of review.

## Out of scope

This mapping does not address:

- legal interpretation of GDPR articles,
- Member State derogations under Article 23 or specific national
  implementations,
- Article 35 Data Protection Impact Assessments,
- Article 42 certification schemes,
- Articles 44 to 50 international data transfer mechanisms,
- forward-looking guarantees about future European Data Protection Board
  guidance, or
- e-Privacy Directive (2002/58/EC) overlays, which would be a separate
  sibling crosswalk if drafted in future.

## Relationship to AIA-12 aligned profile

This GDPR mapping is a sibling overlay to
`docs/spec/aia-12-aligned-profile.md`. The AIA-12 profile remains the
canonical EU AI Act Article 12 framing; this GDPR mapping does NOT extend,
replace, or rephrase it.

The AIA-12 profile already addresses a GDPR / PII boundary section in its
own vocabulary. This crosswalk reuses the same underlying primitives (hash
chain, role-bound event fields, retention / deletion profile, signing,
pseudonymous references) but expresses them in GDPR vocabulary. The two
documents are non-exclusive: a controller deploying a high-risk AI system
under the EU AI Act may cite both crosswalks in parallel.

The AIA-12 profile is referenced as a sibling for `SubjectRef`-style
pseudonymisation guidance only; this crosswalk does not edit it.

## Versioning

Future revisions of this mapping will mint a new profile identifier (for
example `https://attestplane.io/profiles/gdpr/alpha-YYYY-MM`) rather than
mutating this one in place. A new mapping is required when:

- a cited ADR is superseded or withdrawn,
- a cited primitive changes its observable behaviour,
- the GDPR is amended in a way that alters a cited article, or
- the European Data Protection Board issues guidance that materially
  reshapes a cited article's interpretation.

This versioning rule preserves the alpha boundary: the mapping is alignment
scaffolding, never a certification claim.
