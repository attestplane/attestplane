<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# ISO/IEC 42001 AIMS mapping for Attestplane

## Status

Alpha — evidence-supporting alignment mapping, NOT compliance certification.

This document maps Attestplane's substrate primitives to selected clauses
and Annex A controls of ISO/IEC 42001 (Artificial Intelligence Management
System, AIMS). It is not a conformity assessment, not an ISO endorsement,
not an audit, and not a statement that any deployed system or organisation
satisfies ISO/IEC 42001.

## Purpose

ISO/IEC 42001 specifies requirements for establishing, implementing,
maintaining, and continually improving an AI management system. An
organisation pursuing alignment with ISO/IEC 42001 must produce documented
information across multiple management-system domains. Attestplane provides
primitives — append-only hash chain, role-bound event fields, signed events,
anchored timestamps, retention and deletion profile, reason codes — that an
organisation may cite as one input to that documented information.

This crosswalk lists the cited primitives; it does not perform a management
system audit and does not interpret clause language for any specific
organisation.

## Source metadata

- **Version**: `alpha-2026-05`
- **Source planning issue**: [#61](https://github.com/attestplane/attestplaneissues61)
- **Traceability matrix**: [`docs/spec/compliance-traceability-matrix.md`](compliance-traceability-matrix.md)

The traceability matrix records the claim -> argument -> evidence chain for
this mapping and the explicit gap rows tied to issue #61.

## Explicit non-claims

This crosswalk does not claim:

- compliance certification with ISO/IEC 42001 or any AIMS variant,
- AIMS conformity assessment by Attestplane or any third party,
- replacement for the organisation's AIMS obligations under ISO/IEC 42001,
- a legal opinion on the sufficiency of Attestplane evidence for any
  ISO/IEC 42001 clause,
- a Stage 1 or Stage 2 audit, or
- forward-looking guarantees beyond this alpha mapping.

The phrase "evidence-supporting alignment mapping, NOT compliance
certification" applies to every row below.

## Profile identifier

```text
https://attestplane.io/profiles/iso-iec-42001/alpha-2026-05
```

The identifier is versioned because the mapping is a public contract.
Future revisions create a new profile identifier rather than silently
changing the meaning of this one. The `alpha-2026-05` suffix is a
calendar-month stamp on when the mapping was drafted; it is not a
forward commitment to a future release.

## Control-family → primitive table

| ISO/IEC 42001 clause or Annex A control | Attestplane primitive providing supporting evidence | Citation file |
|---|---|---|
| Clause 5.3 — organisational roles, responsibilities, authorities | role-bound event fields (provider / deployer / operator / auditor) recommended by the AIA-12 aligned profile | `docs/spec/aia-12-aligned-profile.md` (sibling, unmodified) |
| Clause 6.1 — actions to address risks and opportunities | `policy_trace_refs` field links each event to the policy or guardrail revision active at the time of the action | `docs/adr/0012-proof-bundle-policy-trace-refs.md` |
| Clause 7.5 — documented information | entire substrate, with audit-export readable offline against the open verifier | `docs/spec/aia-12-aligned-profile.md` (sibling), `docs/adr/0008-evidence-event-taxonomy-v1.md` |
| Annex A.4 — AI system impact assessment record-keeping | event taxonomy categories (decision, human intervention, exception, drift, audit export) | `docs/spec/evidence-event-taxonomy-v1.md`, `docs/adr/0008-evidence-event-taxonomy-v1.md` |
| Annex A.6.2.4 — logging of AI system operation | append-only hash chain providing tamper-evident logs of system operation | `docs/adr/0002-substrate-data-model-and-hash-chain-v0.md` |
| Annex A.6.2.5 — timestamp and integrity of records | RFC 3161 trusted time-stamp anchoring plus optional Sigstore / Rekor redundant anchor | `docs/adr/0003-tsa-rfc-3161-anchoring.md`, `docs/adr/0006-sigstore-rekor-redundant-anchor.md` |
| Annex A.7.2 — data protection of AI system records | pseudonymous `SubjectRef`-style references recommended by the AIA-12 aligned profile | `docs/spec/aia-12-aligned-profile.md` (sibling, unmodified) |
| Annex A.7.3 — data retention of AI system records | commit-then-redact retention and deletion profile, which preserves chain continuity while allowing operator-driven removal of subject material | `docs/adr/0015-retention-deletion-proof-profile.md` |
| Annex A.7.4 — integrity / signing of AI system records | Ed25519 event signing scheme | `docs/adr/0005-event-signing-scheme.md` |
| Annex A.9.3 — verification and monitoring of AI system operation | verifier reason-code taxonomy emitted on every check | `docs/adr/0010-verification-reason-codes.md` |

Each row is alignment scaffolding only. The organisation is responsible for
selecting which AIMS clauses it will pursue, how it will weigh Attestplane
evidence inside its own documented information set, and how it will combine
that evidence with management-system controls outside the substrate.

The mapping addresses selected clauses and Annex A controls only. Clauses
not listed above (for example Clause 4 organisational context, Clause 9
performance evaluation, Clause 10 improvement) are deliberately out of
scope because they depend primarily on organisational practice rather than
substrate primitives.

## How an organisation may cite Attestplane evidence

An organisation pursuing alignment with ISO/IEC 42001 may cite Attestplane
evidence in any of the following ways. None of these citations turns
Attestplane into a certification body or an accredited auditor:

- as supporting evidence for Clause 7.5 documented-information requirements,
- as supporting evidence for Annex A.6.2 controls covering logging,
  timestamping, and integrity,
- as supporting evidence for Annex A.7 controls covering data protection,
  retention, and signing of AI system records,
- as supporting evidence for Annex A.9.3 monitoring and verification
  records.

In every case the organisation cites a concrete Attestplane export bundle,
the verifier version used, and the trust roots accepted at the time of
review.

## Out of scope

This mapping does not address:

- legal interpretation of ISO/IEC 42001 clauses,
- accreditation or certification of any kind,
- ISO/IEC 23894 risk-management guidance overlays, which would be a
  separate sibling crosswalk if drafted in future,
- ISO/IEC 22989, 38507, or other AIMS-adjacent standards,
- sector-specific management-system overlays (for example ISO/IEC 27001
  ISMS interplay), and
- forward-looking guarantees about future ISO/IEC 42001 amendments or
  technical corrigenda.

## Relationship to AIA-12 aligned profile

This ISO/IEC 42001 mapping is a sibling overlay to
`docs/spec/aia-12-aligned-profile.md`. The AIA-12 profile remains the
canonical EU AI Act Article 12 framing; this ISO/IEC 42001 mapping does
NOT extend, replace, or rephrase it.

Both documents reuse the same Attestplane primitives (hash chain,
role-bound event fields, policy-trace references, retention / deletion
profile, signing, reason codes). Each crosswalk explains, in its own
framework's vocabulary, how a deployer or organisation may cite those
primitives. The crosswalks are non-exclusive: an organisation deploying a
high-risk AI system under the EU AI Act while also pursuing an AIMS may
cite both crosswalks in parallel.

The AIA-12 profile is referenced as a sibling for role-bound event fields
and pseudonymous references only; this crosswalk does not edit it.

## Versioning

Future revisions of this mapping will mint a new profile identifier (for
example `https://attestplane.io/profiles/iso-iec-42001/alpha-YYYY-MM`)
rather than mutating this one in place. A new mapping is required when:

- a cited ADR is superseded or withdrawn,
- a cited primitive changes its observable behaviour,
- ISO publishes an amendment or technical corrigendum to ISO/IEC 42001
  that alters a cited clause or Annex A control, or
- a new event category is added to the taxonomy with management-system
  weight.

This versioning rule preserves the alpha boundary: the mapping is
alignment scaffolding, never a certification claim.
