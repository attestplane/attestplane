<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# NIST AI RMF 1.0 mapping for Attestplane

## Status

Alpha — evidence-supporting alignment mapping, NOT compliance certification.

This document maps Attestplane's substrate primitives to NIST AI Risk
Management Framework 1.0 (AI RMF) function families. It is not a conformity
assessment, not a NIST endorsement, and not a statement that any deployed
system satisfies AI RMF objectives.

## Purpose

The AI RMF 1.0 organises trustworthy-AI practice into four core functions —
Govern, Map, Measure, and Manage. Attestplane provides tamper-evident event
chains, role-bound event fields, typed evidence payloads, optional sidecar
signing and anchoring, and policy-trace references. This crosswalk shows how
deployers can cite Attestplane evidence as one input to their own AI RMF
implementation.

Deployers remain solely responsible for interpreting AI RMF outcomes against
their concrete AI system, organisational context, and stakeholder set.

## Explicit non-claims

This crosswalk does not claim:

- compliance certification against the NIST AI RMF,
- replacement for the deployer's or operator's AI RMF obligations,
- a legal opinion on the sufficiency of Attestplane evidence for any
  particular AI RMF outcome,
- conformity assessment by NIST or any third party,
- forward-looking guarantees beyond this alpha mapping, or
- coverage of AI RMF outcomes that depend on organisational policy or human
  judgement outside the substrate.

The phrase "evidence-supporting alignment mapping, NOT compliance
certification" applies to every row below.

## Profile identifier

```text
https://attestplane.io/profiles/nist-ai-rmf/alpha-2026-05
```

The identifier is versioned because the mapping is a public contract. Future
revisions create a new profile identifier rather than silently changing the
meaning of this one. The `alpha-2026-05` suffix is a calendar-month stamp on
when the mapping was drafted; it is not a forward commitment to a future
release.

## Control-family → primitive table

| AI RMF function / outcome | Attestplane primitive providing supporting evidence | Citation file |
|---|---|---|
| Govern 1.5 — accountability structures, transparent oversight | append-only hash chain, signed events, RFC 3161 / Sigstore anchors that make oversight reviewable offline | `docs/adr/0002-substrate-data-model-and-hash-chain-v0.md`, `docs/adr/0003-tsa-rfc-3161-anchoring.md`, `docs/adr/0006-sigstore-rekor-redundant-anchor.md` |
| Govern 2.x — culture of risk management, documented policy linkage | `policy_trace_refs` field links each event to the policy or guardrail revision active at decision time | `docs/adr/0012-proof-bundle-policy-trace-refs.md` |
| Map 3.x — system context, AI requirements, role-bound responsibilities | role-bound event fields (provider / deployer / operator / auditor) recommended by the AIA-12 aligned profile | `docs/spec/aia-12-aligned-profile.md` (sibling, unmodified) |
| Map 5.2 — system, model, and policy version references for impact tracking | continuity checkpoints in the hash chain plus `system_ref`, `model_ref`, `policy_ref` carried per event | `docs/adr/0002-substrate-data-model-and-hash-chain-v0.md`, `docs/spec/aia-12-aligned-profile.md` |
| Measure 2.7 — privacy, safety, accuracy, and robustness measurement | event categories (decision, human intervention, exception, drift, audit export) recorded as typed evidence | `docs/spec/evidence-event-taxonomy-v1.md`, `docs/adr/0008-evidence-event-taxonomy-v1.md` |
| Measure 2.8 — reason codes for verification outcomes | reason-code taxonomy emitted by the verifier on every check | `docs/adr/0010-verification-reason-codes.md` |
| Manage 3.1 — risk treatment, deletion or redaction of evidence subjects | commit-then-redact retention and deletion profile preserves chain continuity while making the deletion action reviewable | `docs/adr/0015-retention-deletion-proof-profile.md` |

Each row is alignment scaffolding only. The deployer is responsible for
selecting which AI RMF outcomes it will pursue, how it will weigh Attestplane
evidence inside its own risk register, and how it will combine that evidence
with non-substrate controls.

## Function-by-function notes

The AI RMF organises trustworthy-AI practice into Govern, Map, Measure, and
Manage. The mapping above touches all four functions but is deliberately
incomplete: the substrate observes events, not organisational practice, and
each function contains outcomes that depend on practice the substrate cannot
observe.

- Govern outcomes that depend on workforce training, governance committee
  composition, or contractual flow-down to suppliers are out of scope.
- Map outcomes that depend on stakeholder consultation, qualitative impact
  narratives, or contextual mission framing are out of scope.
- Measure outcomes that depend on the quality of the metrics themselves (for
  example, whether a fairness metric is appropriate for the population) are
  out of scope; Attestplane records the measurement event, not the validity
  of the measurement.
- Manage outcomes that depend on incident-response playbooks executed
  outside the substrate are out of scope.

Within each function the substrate provides supporting evidence for the
record-keeping spine of the deployer's AI RMF implementation.

## How a deployer may cite Attestplane evidence

A deployer working through the AI RMF Playbook may cite Attestplane evidence
in any of the following ways. None of these citations turns Attestplane into a
certifying authority:

- as supporting evidence for Govern outcomes that require demonstrable record
  retention,
- as supporting evidence for Map outcomes that require articulated system /
  model / policy provenance per decision,
- as supporting evidence for Measure outcomes that require auditable record of
  measured events and reason codes,
- as supporting evidence for Manage outcomes that require reviewable risk
  treatment, including redaction or deletion of subject material.

In every case the deployer cites a concrete Attestplane export bundle, the
verifier version used, and the trust roots accepted at the time of review.

## Out of scope

This mapping does not address:

- legal interpretation of AI RMF outcomes,
- deployer- or operator-specific obligations that the substrate cannot
  observe (for example: organisational governance committee composition,
  third-party impact-assessment narratives, or external stakeholder
  consultation),
- forward-looking guarantees about future AI RMF releases or NIST publications
  beyond the alpha mapping,
- conformity assessment, accreditation, or certification of any kind,
- AI RMF Generative AI Profile (NIST AI 600-1) extensions; those would be a
  separate sibling overlay if drafted in future.

## Relationship to AIA-12 aligned profile

This NIST AI RMF mapping is a sibling overlay to
`docs/spec/aia-12-aligned-profile.md`. The AIA-12 profile remains the
canonical EU AI Act Article 12 framing; this NIST AI RMF mapping does NOT
extend, replace, or rephrase it.

Both documents reuse the same Attestplane primitives (hash chain, role-bound
event fields, policy-trace references, retention / deletion profile, reason
codes). Each crosswalk explains, in its own framework's vocabulary, how a
deployer may cite those primitives. The crosswalks are non-exclusive: a
deployer may rely on both AIA-12 and AI RMF in parallel without either
crosswalk being treated as authoritative for the other framework's outcomes.

## Versioning

Future revisions of this mapping will mint a new profile identifier (for
example `https://attestplane.io/profiles/nist-ai-rmf/alpha-YYYY-MM`) rather
than mutating this one in place. A new mapping is required when:

- a cited ADR is superseded or withdrawn,
- a cited primitive changes its observable behaviour,
- NIST releases an AI RMF revision that alters the cited function family, or
- a new event category is added to the taxonomy with regulatory weight.

This versioning rule preserves the alpha boundary: the mapping is alignment
scaffolding, never a certification claim.
