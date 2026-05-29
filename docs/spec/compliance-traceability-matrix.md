<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Compliance traceability matrix for alignment docs

## Status

Alpha — evidence-supporting alignment mapping, NOT compliance certification.

This document is the traceability matrix for the alpha compliance-alignment
docs. It records claim -> argument -> evidence links and makes gaps explicit
instead of leaving empty cells ambiguous.

## Source metadata

- **Version**: `alpha-2026-05`
- **Source planning issue**: [#61](https://github.com/attestplane/attestplane/issues/61)
- **Traceability scope**: [NIST AI RMF mapping](./nist-ai-rmf-1.0-mapping.md), [GDPR mapping](./gdpr-articles-5-22-30-mapping.md), [ISO/IEC 42001 mapping](./iso-iec-42001-aims-mapping.md), [Threat model v1](../security/threat-model-v1.md)

Empty evidence cells are represented as `gap:` and linked to issue #61 so the
matrix stays auditable without implying certification or production readiness.

## NIST AI RMF

Source doc: [docs/spec/nist-ai-rmf-1.0-mapping.md](./nist-ai-rmf-1.0-mapping.md)

| Claim | Argument | Evidence | Gap / backlog |
|---|---|---|---|
| Govern 1.4 accountability structures, transparent policies, and oversight | append-only hash chain, signed events, and anchors make oversight reviewable offline | [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md), [ADR-0006](../adr/0006-sigstore-rekor-redundant-anchor.md) | — |
| Govern 2.x culture of risk management and documented policy linkage | `policy_trace_refs` links each event to the policy revision active at decision time | [ADR-0012](../adr/0012-proof-bundle-policy-trace-refs.md) | — |
| Map 3.x system context, AI requirements, and role-bound responsibilities | role-bound event fields recommended by the AIA-12 aligned profile keep responsibility visible | [AIA-12 profile](./aia-12-aligned-profile.md) | — |
| Map 5.2 system, model, and policy version references for impact tracking | continuity checkpoints plus `system_ref`, `model_ref`, and `policy_ref` carry the active context | [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md), [AIA-12 profile](./aia-12-aligned-profile.md) | — |
| Measure 2.7 privacy, safety, accuracy, and robustness measurement | typed evidence categories record measured events and review activity | [evidence-event-taxonomy-v1](./evidence-event-taxonomy-v1.md), [ADR-0008](../adr/0008-evidence-event-taxonomy-v1.md) | — |
| Measure 2.8 reason codes for verification outcomes | the verifier emits a reason-code taxonomy on every check | [ADR-0010](../adr/0010-verification-reason-codes.md) | — |
| Manage 3.1 risk treatment, deletion, or redaction of evidence subjects | commit-then-redact preserves chain continuity while making removal reviewable | [ADR-0015](../adr/0015-retention-deletion-proof-profile.md) | — |
| Workforce training, supplier flow-down, and organisational governance evidence | the current docs trace substrate-supporting evidence only; these controls live outside the substrate boundary | gap: no machine-readable organisational-controls artifact yet | [Issue #61](https://github.com/attestplane/attestplane/issues/61) |

## GDPR

Source doc: [docs/spec/gdpr-articles-5-22-30-mapping.md](./gdpr-articles-5-22-30-mapping.md)

| Claim | Argument | Evidence | Gap / backlog |
|---|---|---|---|
| Art. 5(1)(f) integrity and confidentiality | hash chain plus event signing, optionally anchored, make tampering detectable | [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0005](../adr/0005-event-signing-scheme.md), [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md), [ADR-0006](../adr/0006-sigstore-rekor-redundant-anchor.md) | — |
| Art. 5(1)(e) storage limitation | commit-then-redact preserves continuity while allowing controller-driven removal | [ADR-0015](../adr/0015-retention-deletion-proof-profile.md) | — |
| Art. 5(2) accountability | the substrate plus the open verifier provide an offline-auditable record spine | [AIA-12 profile](./aia-12-aligned-profile.md), [ADR-0010](../adr/0010-verification-reason-codes.md) | — |
| Art. 22 automated individual decision-making | decision events and human-intervention events encode the decision path | [evidence-event-taxonomy-v1](./evidence-event-taxonomy-v1.md), [ADR-0008](../adr/0008-evidence-event-taxonomy-v1.md) | — |
| Art. 30 records of processing activities | continuity checkpoints plus the auditor export profile pin schema and verifier versions | [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md), [AIA-12 profile](./aia-12-aligned-profile.md) | — |
| Art. 17 right to erasure | commit-then-redact keeps deletion reviewable without claiming legal sufficiency | [ADR-0015](../adr/0015-retention-deletion-proof-profile.md) | — |
| Art. 32 security of processing | the event-signing scheme makes tampering and unauthorised alteration detectable | [ADR-0005](../adr/0005-event-signing-scheme.md) | — |
| Art. 4(5) pseudonymisation | pseudonymous `SubjectRef`-style references keep raw identifiers out of the chain | [AIA-12 profile](./aia-12-aligned-profile.md) | — |
| Article 35 DPIA and Article 42 certification traces | these are controller-specific legal and procedural artifacts, not substrate primitives | gap: controller-specific review is not machine-traced here | [Issue #61](https://github.com/attestplane/attestplane/issues/61) |

## ISO/IEC 42001

Source doc: [docs/spec/iso-iec-42001-aims-mapping.md](./iso-iec-42001-aims-mapping.md)

| Claim | Argument | Evidence | Gap / backlog |
|---|---|---|---|
| Clause 5.3 organisational roles, responsibilities, and authorities | role-bound event fields preserve who did what and under which role | [AIA-12 profile](./aia-12-aligned-profile.md) | — |
| Clause 6.1 actions to address risks and opportunities | `policy_trace_refs` binds actions to the policy or guardrail version in force | [ADR-0012](../adr/0012-proof-bundle-policy-trace-refs.md) | — |
| Clause 7.5 documented information | the substrate plus offline verifier provide reviewable documented information | [AIA-12 profile](./aia-12-aligned-profile.md), [ADR-0008](../adr/0008-evidence-event-taxonomy-v1.md) | — |
| Annex A.4 AI system impact assessment record-keeping | typed evidence categories capture decision, intervention, exception, drift, and export events | [evidence-event-taxonomy-v1](./evidence-event-taxonomy-v1.md), [ADR-0008](../adr/0008-evidence-event-taxonomy-v1.md) | — |
| Annex A.6.2.4 logging of AI system operation | the append-only hash chain provides tamper-evident operation logs | [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md) | — |
| Annex A.6.2.5 timestamp and integrity of records | RFC 3161 anchoring plus optional Sigstore redundancy preserve timing and integrity evidence | [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md), [ADR-0006](../adr/0006-sigstore-rekor-redundant-anchor.md) | — |
| Annex A.7.2 data protection of AI system records | pseudonymous `SubjectRef`-style references keep direct identifiers out of the record spine | [AIA-12 profile](./aia-12-aligned-profile.md) | — |
| Annex A.7.3 data retention of AI system records | commit-then-redact supports retention and removal without breaking continuity | [ADR-0015](../adr/0015-retention-deletion-proof-profile.md) | — |
| Annex A.7.4 integrity and signing of AI system records | event signing makes record alteration detectable | [ADR-0005](../adr/0005-event-signing-scheme.md) | — |
| Annex A.9.3 verification and monitoring of AI system operation | reason codes make verification outcomes reviewable | [ADR-0010](../adr/0010-verification-reason-codes.md) | — |
| Clause 4 context, Clause 9 performance evaluation, and Clause 10 improvement traces | these management-system clauses depend on organisational controls outside the substrate | gap: management-system evidence is not yet traced in machine-readable form | [Issue #61](https://github.com/attestplane/attestplane/issues/61) |

## Threat model v1

Source doc: [docs/security/threat-model-v1.md](../security/threat-model-v1.md)

| Claim | Argument | Evidence | Gap / backlog |
|---|---|---|---|
| AT-01 tampering with historical events | hash-chain linkage plus signatures plus anchors require multiple compromises for a rewrite | [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0005](../adr/0005-event-signing-scheme.md), [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md) | — |
| AT-02 forged anchoring (single-TSA collusion) | plurality lets a second anchor cross-check the first | [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md), [ADR-0006](../adr/0006-sigstore-rekor-redundant-anchor.md) | — |
| AT-03 replay of historical events | monotonic sequence numbers, `prev_hash`, and canonical text bind every event to its predecessor | [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0011](../adr/0011-canonical-text-v1.md) | — |
| AT-04 long-term verifier viability | frozen schema, permanent vectors, and pinned fixtures preserve offline re-verifiability | [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0011](../adr/0011-canonical-text-v1.md), [ADR-0014](../adr/0014-adapter-conformance-fixture-pinning.md) | — |
| AT-05 PII leakage via low-entropy hash pre-image | commit-then-redact keeps raw personal data out of the append-only chain | [ADR-0015](../adr/0015-retention-deletion-proof-profile.md) | — |
| AT-06 selective-disclosure attack on an offline export | controller-owned sidecar material controls what accompanies each export | [ADR-0015](../adr/0015-retention-deletion-proof-profile.md) | — |
| AT-07 maintainer key compromise | keyless release signing and provenance bind releases to the workflow identity | [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md), [SECURITY.md](../../SECURITY.md), [GOVERNANCE.md](../../GOVERNANCE.md) | — |
| AT-08 quantum cryptanalysis | the current suite is explicitly pre-quantum and therefore exposes a residual | [ADR-0005](../adr/0005-event-signing-scheme.md), [openssf-silver-roadmap.md](openssf-silver-roadmap.md) | — |
| AT-09 supply-chain compromise of a build-time dependency | pinned manifests, SBOMs, signatures, and reproducible builds provide post-hoc detection | [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md), [openssf-silver-roadmap.md](openssf-silver-roadmap.md) | — |
| AT-10 TSA endpoint compromise | plurality and redundant anchors prevent a single compromised TSA from dominating the claim | [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md), [ADR-0006](../adr/0006-sigstore-rekor-redundant-anchor.md) | — |
| AT-11 verifier code compromise | cross-language conformance and offline verification keep results consistent | [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0005](../adr/0005-event-signing-scheme.md), [docs/architecture/verifier_independence.md](../architecture/verifier_independence.md) | — |
| AT-12 PII export to an unauthorised auditor | the export scope is governed by the controller-owned sidecar, not the verifier | [ADR-0015](../adr/0015-retention-deletion-proof-profile.md) | — |
| AT-13 clock skew or local-time manipulation | authoritative time comes from TSA or Rekor, not the local clock | [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md), [ADR-0006](../adr/0006-sigstore-rekor-redundant-anchor.md) | — |
| AT-14 substrate-operator signing-key extraction | keyless release signing and constrained key-provider lifecycles reduce the value of theft | [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md), [ADR-0005](../adr/0005-event-signing-scheme.md), [ADR-0004](../adr/0004-aios-to-attestplane-boundary.md) | — |
| Quorum-of-anchors, cryptographic selective disclosure, and PQC migration | these are documented as forward-looking mitigations, not yet as implemented evidence | gap: residual-risk roadmap items remain future work | [Issue #61](https://github.com/attestplane/attestplane/issues/61) |
