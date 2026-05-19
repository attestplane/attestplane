<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# AIA-12 Aligned Evidence Profile

## Status

Alpha design profile. This document describes an evidence shape aligned with
EU AI Act Article 12 logging expectations. It is not a legal opinion, not a
conformity assessment, and not a statement that any deployed AI system satisfies
EU AI Act obligations.

## Purpose

Article 12 focuses on automatic recording of events for high-risk AI systems.
Attestplane's substrate already provides tamper-evident event chains, typed
evidence payloads, chain/report-oriented verification, and optional sidecar
signing and anchoring primitives. This profile narrows those primitives into a
more regulator-readable shape for systems that need to reconstruct:

- when a system was used,
- which system, model, policy, and dataset references were active,
- which party or role performed or reviewed an action,
- what decision, intervention, exception, or drift signal occurred,
- whether the log has continuity gaps, and
- which export and verifier versions are needed for offline review.

## Explicit Non-Claims

This profile does not claim:

- legal sufficiency for any deployed system,
- replacement for deployer or provider obligations,
- right-to-erasure automation,
- default signed or anchored verification by `attestplane verify`,
- completeness of operational logs outside what callers emit, or
- external certification status.

## Profile Identity

Recommended profile identifier:

```text
https://attestplane.io/profiles/aia-12/alpha-2026-05
```

The identifier is versioned because the profile is a public contract. Future
changes should create a new profile identifier rather than silently changing
the meaning of this one.

## Required Event References

An AIA-12 aligned event SHOULD carry the following references where the caller
has access to them:

| Reference | Purpose |
|---|---|
| `session_id` | Binds events to a specific system-use period or workflow span. |
| `system_ref` | Stable reference to the deployed AI system or service. |
| `model_ref` | Stable model or model-family reference, including version where available. |
| `policy_ref` | Policy, guardrail, or approval rule version active at decision time. |
| `actor` | Machine or human actor that emitted or caused the event. |
| `human_verifier` | Pseudonymous reference to a human reviewer when one participated. |
| `reference_db_ref` | Reference to the database or corpus used for matching, if applicable. |
| `matched_input_ref` | Content-addressed or pseudonymous reference to matched input, if applicable. |
| `evidence_schema_ref` | Schema version used to validate the event payload. |

These values are references. Raw personal data, prompts, medical records,
financial records, biometric material, and large media objects should not be
inlined into append-only evidence unless the deployer has separately approved
that retention model.

## Recommended Event Categories

The profile maps regulator-readable operations onto the existing evidence
taxonomy instead of creating a parallel log format.

| Category | Example use | Preferred event family |
|---|---|---|
| `system_use_started` | Begin a logged use period. | session or replay evidence event |
| `decision_recorded` | Record a model- or policy-mediated output. | AI decision event |
| `human_intervention` | Record override, review, escalation, or approval. | human approval or policy check event |
| `policy_check` | Record deterministic policy result. | policy check event |
| `exception_recorded` | Record blocked, malformed, or failed operation. | policy check or replay event |
| `drift_signal` | Record model, data, or policy drift observation. | replay or adapter evidence event |
| `continuity_checkpoint` | Make missing event spans detectable. | checkpoint or replay event |
| `export_recorded` | Record generation of an auditor-readable export. | evidence export event |

## Continuity Rules

An export using this profile SHOULD include:

1. The ordered evidence chain segment.
2. The starting and ending chain heads.
3. A profile identifier.
4. Schema version references.
5. The verifier version or source revision.
6. Any sidecar signature or anchor records that the caller wants reviewed.
7. Explicit gap markers when the exporter knows a span is incomplete.

The verifier should fail closed on malformed metadata, broken chain continuity,
unknown required schema versions, or an export that claims this profile but
omits profile-critical references without an explicit limitation.

## Offline Review Model

A third-party reviewer should be able to verify a complete export without
trusting an Attestplane-hosted API:

```text
export bundle + schema version + verifier source/release + trust roots
  -> deterministic verification report
```

Hosted APIs may help with search and retrieval, but they are convenience
surfaces only. The exported bytes and open verifier are the review substrate.

## GDPR and PII Boundary

This profile assumes PII minimization:

- put commitments, hashes, opaque handles, or content-addressed references in
  the chain where practical;
- keep raw/deletable material in controller-owned sidecar stores;
- append redaction or deletion evidence when sidecar material is removed; and
- preserve chain continuity while making the deletion action reviewable.

This is an evidence pattern, not a guarantee that a controller has satisfied a
right-to-erasure request.

## Relationship to Issue #7

This document resolves the Article 12 surface part of issue #7 by making the
profile concrete while preserving the alpha boundary: aligned evidence
infrastructure, not a legal conclusion.
