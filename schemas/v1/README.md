<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Attestplane v1 JSON Schemas

Machine-validatable shapes for the v1 wire-format artifacts that ship
out of an Attestplane substrate to verifiers, auditors, and regulators.

| File | Purpose |
|------|---------|
| [`proof_bundle.schema.json`](proof_bundle.schema.json) | Full export — chain segment + verification report + framework mappings + redaction echo. Consumed by `attestplane verify <bundle.json>` (M5). |
| [`auditor_export.schema.json`](auditor_export.schema.json) | Auditor-friendly summary — chain integrity + framework coverage + redaction policy, **without** event payloads. Optimised for human review. |
| [`governance_ingestion.schema.json`](governance_ingestion.schema.json) | Governance-platform ingestion document — strict subset of `auditor_export.schema.json` plus producer metadata. Designed for AI governance dashboards (Credo AI / Holistic AI / Modulos / Trustible / Saidot) to ingest as `field_supported` evidence; see [`docs/integrations/governance_platforms.md`](../../docs/integrations/governance_platforms.md). |

## Versioning

Both schemas pin their version with a `const` integer (`bundle_version`
/ `export_version`). Bumping is governed by the same rule as
[ADR-0008](../../docs/adr/0008-evidence-event-taxonomy-v1.md):

- Adding optional fields = non-breaking, no version bump required.
- Adding required fields, renaming, or removing fields = breaking; new
  version + deprecation window.

The top-level `schema_version` field pins the proof-bundle verifier
contract version. It is separate from `events[].event.schema_version`
and `chain_metadata.schema_version`, which pin the substrate
canonicalization version per [ADR-0002](../../docs/adr/0002-substrate-data-model-and-hash-chain-v0.md);
`chain_metadata.evidence_taxonomy_version` pins the event-taxonomy
version per ADR-0008. All four versions evolve independently.

For verifier JSON consumers, see
[`docs/schema/verify-json.md`](../../docs/schema/verify-json.md) for the
consumer-facing `schema_version` policy. That page describes how unsupported
versions surface through `verify --json` without changing the wire-format
versioning rules above.

## Redaction discipline

`proof_bundle.forbidden_fields` is **not** advisory — it is the
producer's explicit contract that the listed terms are absent from
every event in the bundle. A verifier MAY refuse to process a bundle
whose `forbidden_fields` does not include a regulator-required term.

The canonical default list ships in the schema's `default` clause:

```
customer_names, person_names, pii, raw_documents, contracts,
scripts, tickets, emails, secrets, tokens, jwts, private_keys,
raw_audit_payloads
```

These thirteen terms are seeded from AIOS's customer attestation
template (per the migration plan § 2.1 INTEGRATE-DIRECT row). The set
is the floor, not the ceiling — producers MAY add more.

## Cross-references

- [ADR-0002](../../docs/adr/0002-substrate-data-model-and-hash-chain-v0.md) — substrate hash-chain locked at `schema_version=1`
- [ADR-0004](../../docs/adr/0004-aios-to-attestplane-boundary.md) — boundary that constrains what these bundles can claim
- [ADR-0008](../../docs/adr/0008-evidence-event-taxonomy-v1.md) — event taxonomy referenced by `events[].event_type`
- [`docs/spec/canonical-json-v1.md`](../../docs/spec/canonical-json-v1.md) — canonical-JSON profile used for any signature coverage
- [`docs/spec/evidence-event-taxonomy-v1.md`](../../docs/spec/evidence-event-taxonomy-v1.md) — the twelve event types
- [`sdk/python/src/attestplane/obligations/`](../../sdk/python/src/attestplane/obligations/) — obligation registry referenced by `framework_mappings[].obligation_id`
- [`docs/policy/forbidden_claims.md`](../../docs/policy/forbidden_claims.md) — claim-safety triad
