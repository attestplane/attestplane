<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Integration: AI Governance Platforms

> **Audience:** integration engineers at AI governance / GRC SaaS
> platforms (Credo AI, Holistic AI, Modulos, Trustible, Saidot, or
> others) who want to surface Attestplane evidence inside their
> dashboards.
>
> **TL;DR:** Attestplane substrates emit a self-contained JSON
> document — `governance_ingestion.schema.json` — that your platform
> can ingest as a `field_supported` evidence source for EU AI Act
> Article 12 / DORA Article 8 obligations. The document does NOT
> include event payloads; it's a verification summary + framework
> coverage map + redaction policy echo. Per-event detail lives in the
> full proof bundle (separately downloadable). No special protocol
> required; HTTPS GET of a static JSON file is sufficient.

## 1. Why integrate?

The 2026-05-17 competitive research session (see
[`competitive_positioning_upgrade_plan_20260517.md`](../architecture/competitive_positioning_upgrade_plan_20260517.md))
identified Tier-D AI governance platforms as **channel partners**, not
competitors. Specifically:

- Tier-D platforms **do not ship cryptographic attestation
  primitives**. They surface controls, risk scores, and obligation
  tracking — but their underlying evidence layer is whatever the
  customer's runtime happens to log.
- Attestplane substrates **do not ship governance dashboards**. They
  produce verifiable cryptographic evidence; the substrate stays in
  the customer's control plane.
- The natural composition: Tier-D platform dashboards display
  obligation rows; Attestplane substrates populate the `evidence
  available` indicator with cryptographically-anchored, tamper-evident
  data.

For the customer, the result is "we cite Attestplane in our existing
Credo AI / Holistic AI / Modulos / Trustible / Saidot dashboard as the
evidence source for Art. 12 audit logs."

## 2. The data flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  Customer's AI agent runtime (LangSmith / LangFuse / custom)        │
│  Emits events into Attestplane SDK                                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ append()
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Attestplane substrate (Apache-2.0, customer-owned)                 │
│  • SHA-256 hash chain                                               │
│  • RFC-3161 anchor (FreeTSA / DigiCert / eIDAS QTSP)                │
│  • Sigstore Rekor anchor (per ADR-0006)                             │
│  • Obligation registry (EU AI Act Art. 12, DORA Art. 8)             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ Periodic export (daily / weekly / per-audit)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  governance_ingestion.json — single self-contained document         │
│  • chain_summary (head hash, event count, time range)               │
│  • verification_status (verifier output)                            │
│  • framework_coverage (which obligations have evidence)             │
│  • redaction_policy (forbidden_fields echo + redaction_status)      │
│  • anchor_summary (rfc3161/rekor flags + provider list)             │
│  • proof_bundle_uri (optional pointer to full per-event detail)     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS GET (or pushed via webhook)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Governance platform's evidence ingestion endpoint                  │
│  Surfaces 'evidence available' against EU AI Act / DORA rows        │
│  Displays implementation_status (mapping_target / designed_toward / │
│  field_supported / verified_in_test) verbatim from the document     │
└─────────────────────────────────────────────────────────────────────┘
```

The substrate side knows nothing about the specific governance
platform. The platform side knows only the JSON Schema.

## 3. Document shape

The full schema is at
[`schemas/v1/governance_ingestion.schema.json`](../../schemas/v1/governance_ingestion.schema.json).
Key top-level fields:

| Field | Type | Purpose |
|-------|------|---------|
| `ingestion_version` | `integer (const 1)` | Frozen at 1 for v1. |
| `producer` | object | Identifies the Attestplane substrate instance. |
| `chain_summary` | object | Head hash, event count, time range, event-type histogram, anchor status. |
| `verification_status` | object | Verifier output: `ok`, `first_bad_index`, `reason`, `verified_at`, `verifier_version`, `verification_method`. |
| `framework_coverage` | array | Per (framework, article) rollup: obligations with evidence vs without. |
| `redaction_policy` | object | `forbidden_fields` echo (13-term floor) + `redaction_status` (enforced_by_adapter / enforced_by_producer / unenforced) + optional `consent_status`. |
| `anchor_summary` | object | Boolean flags + provider list (which TSA / Rekor instances). |
| `proof_bundle_uri` | string | Optional pointer to the full proof bundle (deployer hosts). |
| `legal_disclaimer` | string | Plain-language "not a compliance opinion" statement; defaults to a canonical phrasing. |

Critically, the document does **not** carry event payloads, signatures,
or anchor token bytes. The full proof bundle (per
[`schemas/v1/proof_bundle.schema.json`](../../schemas/v1/proof_bundle.schema.json))
contains those; the governance dashboard fetches it on demand via
`proof_bundle_uri` if a regulator audit requires deeper inspection.

## 4. The implementation_status discipline

The single most important field your dashboard renders is
`framework_coverage[].obligation_ids_with_evidence[].implementation_status`.

The Attestplane claim-safety triad
([`docs/policy/forbidden_claims.md`](../policy/forbidden_claims.md))
locks this to a **four-value enum**:

| Value | Permitted public phrasing |
|-------|---------------------------|
| `mapping_target` | "framework mapping target" |
| `designed_toward` | "designed toward [obligation X]" |
| `field_supported` | "field set supports [obligation X]" |
| `verified_in_test` | "automated test verifies [obligation X] field presence" |

**Dashboards MUST surface these values verbatim.** Translating them
to "compliant" / "certified" / "ready" is prohibited by
`forbidden_claims.md`. The legal_disclaimer field on every ingestion
document repeats this rule for the auditor reading the document
out of context.

If your platform's UI has a column called "Compliance Status" with
values like ✅ Compliant / ⚠️ Partial / ❌ Non-Compliant, you'll need
a mapping layer. Suggested:

| Attestplane status | Dashboard rendering | Rationale |
|--------------------|---------------------|-----------|
| `verified_in_test` | "Evidence verified" + ✅ | Automated test gates the claim |
| `field_supported` | "Substrate field shipped" + 🟢 | Type-level support, no test yet |
| `designed_toward` | "Designed, not yet shipped" + ⚪ | Roadmap commitment |
| `mapping_target` | "Mapping target" + ◯ | Outermost framing only |

The mapping itself is your platform's call; the claim-safety triad
only governs Attestplane-side public material.

## 5. Producing the document — Python example

```python
import json
from datetime import UTC, datetime

from attestplane import (
    AttestSubstrate, EventDraft, ProofBundleBuilder,
    build_auditor_export, load_all_registries,
)

# 1. Build the proof bundle from the substrate's chain.
substrate = ...  # caller's existing AttestSubstrate instance
builder = ProofBundleBuilder(
    chain_id="customer-prod-eu-1",
    producer_runtime="langsmith-via-attestplane-adapter v0.0.3a0",
)
builder.extend(substrate.snapshot())
bundle = builder.build()

# 2. Compute auditor export (governance_ingestion is a strict subset).
auditor_export = build_auditor_export(
    bundle,
    framework_coverage_registries=list(load_all_registries()),
    redaction_status="enforced_by_adapter",
    consent_status="consent_not_applicable",
)

# 3. Slim down to the governance_ingestion shape.
ingestion_doc = {
    "ingestion_version": 1,
    "producer": {
        "substrate_version": "0.0.3a0",
        "runtime_name": "langsmith",
        "instance_id": "customer-prod-eu-1",
    },
    "chain_summary": auditor_export["chain_summary"],
    "verification_status": auditor_export["verification_status"],
    "framework_coverage": [
        {
            "framework": row["framework"],
            "article": row["article"],
            "obligation_ids_with_evidence": [
                {
                    "obligation_id": oid,
                    "implementation_status": _status_lookup(oid),
                    # evidence_event_indexes omitted in this example
                }
                for oid in row["obligation_ids_with_evidence"]
            ],
            "obligation_ids_without_evidence": row["obligation_ids_without_evidence"],
        }
        for row in auditor_export["framework_coverage"]
    ],
    "redaction_policy": auditor_export["redaction_policy"],
    "anchor_summary": {
        "rfc3161_anchored": False,  # set based on actual anchor records
        "sigstore_rekor_anchored": False,
        "anchor_count": 0,
        "anchor_providers": [],
    },
    "legal_disclaimer": auditor_export["legal_disclaimer"],
}

# 4. Write to wherever the dashboard fetches from.
with open("governance_ingestion.json", "w") as f:
    json.dump(ingestion_doc, f, indent=2, sort_keys=True)
```

`_status_lookup(oid)` is the deployer's helper — they query their
loaded registries for the entry's `implementation_status` value.

## 6. Constraints the integration MUST respect

These come from Attestplane's claim-safety triad and ADR-0004
boundary:

- **No execution semantics.** The governance platform ingests the
  document and renders it. It does NOT instruct Attestplane to do
  anything (no API for `revoke_evidence`, `delete_evidence`,
  `update_implementation_status`). Per ADR-0004 § 1 universal rule,
  authority/execution stays in the customer's substrate.
- **No silent rewording.** If the platform UI displays
  `implementation_status`, it MUST use the four locked values or a
  mapping documented in the platform's own legal review. Quietly
  rendering `designed_toward` as "Compliant" is a claim-safety
  violation that flows back to the customer's regulator submission.
- **Optional `proof_bundle_uri` is deployer-controlled.** The
  Attestplane substrate does NOT host the bundle anywhere. The
  customer chooses storage (S3 / Azure Blob / on-prem) and is
  responsible for access control on it.
- **Document is a subset, not a replacement.** A regulator audit
  that requires per-event detail goes to the full proof bundle, not
  this summary. The governance dashboard's role is "first-line
  visibility" + "drill-down link"; it is not the source of truth.

## 7. Why this isn't a SaaS API

Some integration patterns assume the substrate vendor offers a hosted
ingestion API that the governance platform polls. Attestplane v0.1
explicitly does NOT do this, for three reasons:

1. **Trust boundary.** The substrate is supposed to live inside the
   customer's control plane (the entire Apache-2.0 + lawyer-founder
   positioning depends on this). A hosted ingestion API would put
   Attestplane Pte. Ltd. in the customer's compliance perimeter
   without an audit relationship.
2. **No exclusive partnerships.** The Apache 2.0 license makes
   exclusivity structurally impossible — any governance platform can
   build this integration without permission, contract, or fee.
3. **Substrate stays simple.** The substrate ships SDK + verifier +
   CLI; not a network service. Adding a hosted ingestion service is
   the M7-C1 SaaS deliverable in the existing roadmap, NOT v0.1.

## 8. Frequently asked questions

**Q: Does the governance platform need a license from Attestplane Pte. Ltd. to integrate?**
A: No. The substrate is Apache 2.0, the JSON Schemas are MIT-equivalent
inside an Apache 2.0 repo, the wire format is in-toto Statement /
DSSE (industry-standard, no encumbrance). Build the integration freely.

**Q: Can we badge our product "Attestplane Certified" / "Powered by Attestplane"?**
A: No, not without a separate trademark agreement.
[TRADEMARK.md](../../TRADEMARK.md) governs the marks; the Apache 2.0
license does NOT grant trademark rights.

**Q: We want the substrate to call our API instead of writing JSON to disk. Can we get a webhook?**
A: Not in v0.1. The HTTP transport pattern shipped for Sigstore Rekor
(`Rfc3161HttpProvider` with injectable transport) is a precedent —
build your own outgoing-webhook component in your customer's
deployment, sourcing data from
`build_auditor_export(builder.build())`. The substrate's job is to
produce evidence; pushing it anywhere is the deployer's choice.

**Q: How does our dashboard verify the document hasn't been tampered with between substrate and us?**
A: Two paths:

- **Cheap**: re-fetch the full proof bundle via `proof_bundle_uri`,
  run `attestplane verify <bundle.json>`, compare the resulting
  `verification_status` to the ingestion document's. Mismatch = the
  ingestion document was edited.
- **Cryptographic**: have the substrate sign the ingestion document
  with the same Ed25519 key it uses for Sigstore Rekor anchoring
  (per [ADR-0006](../adr/0006-sigstore-rekor-redundant-anchor.md))
  and embed the signature as `signature` (proof_bundle.schema.json
  has the `signature` slot reserved; the M6 deliverable will extend
  this to the ingestion shape).

## 9. Cross-references

- [`schemas/v1/governance_ingestion.schema.json`](../../schemas/v1/governance_ingestion.schema.json)
- [`schemas/v1/proof_bundle.schema.json`](../../schemas/v1/proof_bundle.schema.json) (parent shape)
- [`schemas/v1/auditor_export.schema.json`](../../schemas/v1/auditor_export.schema.json) (sibling shape; governance_ingestion is a strict subset)
- [ADR-0004 § 1](../adr/0004-aios-to-attestplane-boundary.md) — boundary universal rule
- [ADR-0008](../adr/0008-evidence-event-taxonomy-v1.md) — twelve event types
- [`docs/policy/forbidden_claims.md`](../policy/forbidden_claims.md) — claim-safety triad
- [`competitive_positioning_upgrade_plan_20260517.md`](../architecture/competitive_positioning_upgrade_plan_20260517.md) Track 4
