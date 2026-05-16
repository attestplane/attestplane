# Attestplane

**Open Trust Substrate for AI Agents**

[![Apache 2.0 License](https://img.shields.io/github/license/attestplane/attestplane?color=blue)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/attestplane/attestplane/main)](https://github.com/attestplane/attestplane/commits/main)
[![Open Issues](https://img.shields.io/github/issues/attestplane/attestplane)](https://github.com/attestplane/attestplane/issues)
[![GitHub Stars](https://img.shields.io/github/stars/attestplane/attestplane?style=social)](https://github.com/attestplane/attestplane/stargazers)
[![Alpha — API may change](https://img.shields.io/badge/status-alpha-orange.svg)](#roadmap)
[![DCO](https://img.shields.io/badge/contributor_agreement-DCO-lightgrey.svg)](CONTRIBUTING.md)

> **Alpha software.** API surfaces are not yet stable. Not for production use without review of your specific compliance obligations.

---

## What is Attestplane?

Attestplane is a cryptographic audit substrate for AI agent systems. It provides a tamper-evident chain of evidence that makes every consequential action your AI agents take — tool calls, model invocations, data accesses, decisions — verifiable, attributable, and regulatorily mappable.

The substrate captures events into a BLAKE3 hash chain, anchors chain roots to RFC-3161 compliant timestamps, integrates with Sigstore for signing, and emits structured evidence bundles that map directly to EU AI Act Articles 12–17, NIST AI RMF, ISO/IEC 42001, SOC 2, DORA, and CRA 2027 control families. You get an auditor-ready JSON API, not application logs.

Attestplane is not a compliance-as-a-service platform. It is infrastructure your team owns, operates, and audits independently. The framework mappings ship with the substrate; the audit chain stays in your control plane.

---

## Why Open Trust Substrate?

**Regulation demands verifiable evidence, not best-effort logs.** EU AI Act Article 12 requires "logging capabilities" that allow reconstruction of the system's behaviour. DORA Article 8 requires operational resilience with "audit trail" that survives incident investigation. NIST AI RMF asks for "traceable" processes. None of these obligations are satisfied by application logs that can be silently truncated, retroactively modified, or that carry no cryptographic proof of integrity.

**Why open-source, why substrate?** AI agents interact with financial data, health records, legal documents, and critical infrastructure. The code responsible for producing compliance evidence must itself be auditable. A closed SaaS audit platform creates the contradiction of an unverifiable verifier. Attestplane's core substrate is Apache 2.0 so that CISOs, auditors, regulators, and engineers can inspect, fork, and validate every hash function, every chain link, and every framework mapping — not as a marketing claim but as a technical guarantee.

A substrate is by design not a finished product. It is a composable layer your application or platform embeds, connects to its own event streams, and operates within its own trust boundary. Your audit data never leaves your control plane.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  Enterprise layer                    │  Coming M8+ (2027-Q1)        │
│  (proprietary, private repo)         │  SSO/SCIM/RBAC               │
│                                      │  Multi-tenant control plane  │
│                                      │  Regulator dashboard (M7 DP) │
├──────────────────────────────────────┴──────────────────────────────┤
│  Core Substrate  —  Apache 2.0  —  github.com/attestplane/          │
│                                                                      │
│  ┌──────────────┐   ┌────────────────┐   ┌──────────────────────┐  │
│  │  BLAKE3      │   │  RFC-3161      │   │  Sigstore / SLSA L3  │  │
│  │  hash chain  │──▶│  TSA anchoring │──▶│  signing + SBOM      │  │
│  └──────────────┘   └────────────────┘   └──────────────────────┘  │
│          │                                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  /v1/auditor  JSON API                                        │   │
│  │  • chain_verify   • evidence_bundle   • replay_audit          │   │
│  │  • framework_map  • anchor_status     • install_auto_audit    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│          │                                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Framework mapping layer                                      │   │
│  │  EU AI Act Art 12-17 / NIST AI RMF / ISO 42001 / SOC 2 CC7  │   │
│  │  DORA Art 8 / CRA 2027 / GDPR Art 30                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│          │                                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  SDK helpers                                                  │   │
│  │  FastAPI  │  Express  │  NestJS  │  Django  │  Rust crate    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

- **Tamper-evident BLAKE3 hash chain** — each event record includes the hash of the previous record; any insertion, deletion, or modification breaks the chain and is immediately detectable on `chain_verify`.
- **RFC-3161 timestamp anchoring** — chain roots are anchored to an RFC-3161 compliant TSA, giving a cryptographically-verifiable, legally-recognised wall-clock anchor to the evidence record.
- **Sigstore integration + SLSA L3 build provenance** — event signatures and release artifacts are verifiable against the public Sigstore transparency log; no private key management required for common deployments.
- **Multi-framework compliance mapping** — a single evidence bundle maps to EU AI Act Articles 12–17, NIST AI RMF subcategories, ISO/IEC 42001 clauses, SOC 2 CC7.2, DORA Article 8, and CRA 2027 sections via the `/v1/auditor/framework_map` endpoint.
- **Auditor JSON API** — structured, schema-versioned output designed for ingestion by Big-4 audit toolchains, regulators, and internal compliance teams; not a log aggregator, not a SIEM.
- **Self-hosted first** — substrate runs inside your own infrastructure; your attestation data stays in your control plane. EU financial entities subject to DORA Recital 56 can deploy without adding Attestplane as a Critical Third-Party Provider.
- **Multi-language SDK helpers** — `install_auto_audit` one-liner integration for FastAPI, Express, NestJS, Django; Rust crate for native agent runtimes.

---

## Quickstart

> **Alpha note:** All package names, API shapes, and configuration keys below are subject to change before M5 GA (target 2026-08-15).

### Python / FastAPI

```bash
pip install attestplane  # alpha; API may change
```

```python
from attestplane import AttestSubstrate
from attestplane.helpers.fastapi import install_auto_audit

substrate = AttestSubstrate(
    chain_store="postgresql://...",   # your DB
    tsa_endpoint="https://freetsa.org/tsr",
)

# One-line audit instrumentation for a FastAPI app
install_auto_audit(app, substrate=substrate)
```

### Node.js / Express / NestJS

```bash
npm install @attestplane/sdk  # alpha; API may change
```

```typescript
import { AttestSubstrate, installAutoAudit } from "@attestplane/sdk";

const substrate = new AttestSubstrate({
  chainStore: "postgresql://...",
  tsaEndpoint: "https://freetsa.org/tsr",
});

// Express
installAutoAudit(expressApp, { substrate });
```

### Rust

```toml
# Cargo.toml  —  alpha; API may change
[dependencies]
attestplane = "0.1"
```

```rust
use attestplane::{AttestSubstrate, ChainConfig};

let substrate = AttestSubstrate::new(ChainConfig {
    chain_store: "postgresql://...",
    tsa_endpoint: "https://freetsa.org/tsr".parse()?,
})?;
```

### Verify a chain

```bash
# CLI — alpha
attestplane chain verify --from=2026-08-01T00:00:00Z --to=2026-08-15T23:59:59Z
# → chain integrity: OK  |  anchors verified: 14/14  |  gaps: 0
```

---

## Compliance Framework Coverage

The table below shows which regulatory controls Attestplane's evidence bundles directly address. The mapping is maintained by the founder's compliance practice and updated with each regulatory enforcement update.

| Framework | Relevant controls | Coverage in substrate |
|---|---|---|
| **EU AI Act** | Articles 12 (logging), 13 (transparency), 14 (human oversight), 15 (accuracy/robustness), 16 (obligations for providers), 17 (quality management) | Chain integrity + event taxonomy + evidence bundle schema |
| **NIST AI RMF** | GOVERN 1.1–1.7, MAP 1.1–5.2, MEASURE 1.1–4.2, MANAGE 1.1–4.4 | Framework mapping endpoint + risk tagging |
| **ISO/IEC 42001** | §6.1 risk, §8.4 data for AI, §9.1 monitoring and measurement, §10.2 nonconformity | Audit chain + anomaly rate metrics |
| **SOC 2** | CC7.2 (system monitoring), CC7.3 (security event evaluation), CC4.1 (COSO monitoring) | Structured event records + replay audit |
| **DORA** | Article 8 (ICT risk management), Article 10 (detection), Article 17 (incident reporting) | TSA-anchored chain + incident evidence bundle |
| **CRA 2027** | Article 13 (essential cybersecurity requirements), Annex I Part I §2 (logging) | SBOM (CycloneDX) + secure-by-default audit configuration |

> *This table represents technical mapping. It does not constitute legal advice. Your organization's compliance obligations depend on your specific facts and jurisdiction. Consult qualified legal counsel before relying on any regulatory interpretation.*

---

## Roadmap

| Milestone | Target | Scope |
|---|---|---|
| **M5 — GA v1.0.0** | 2026-08-15 | Self-hosted OSS substrate · BLAKE3 chain · RFC-3161 · Sigstore · SLSA L3 · FastAPI/Express helpers · full framework mapping · SBOM (CycloneDX) |
| **M6 — Cloud preview** | 2026-09 | Attestplane Cloud hosted TSA + Sigstore Rekor mirror + framework auto-update · free for EU deployments · Design Partner Program launch |
| **M7 — Client-side DP aggregation** | 2026-Q4 | Client-side differential privacy SDK (Rust + TypeScript + Python) · ε-configurable Laplace noise · regulator dashboard preview · customer attestation data never leaves customer control plane |
| **M8 — Paid tier** | 2027-Q1+ | Pro / Team / Enterprise paid tiers · SSO/SCIM/RBAC · SLA · first FTE hire |

Current status: **pre-M5 alpha** — community velocity stage. Contributions, issue reports, and deployment feedback are the project's most valuable input right now.

---

## Who is Behind Attestplane

Attestplane was designed and built by a China-licensed Business and Compliance lawyer who became frustrated with the gap between how compliance frameworks describe AI system obligations and what engineering teams are actually given to work with. Most tooling in this space is built by engineers who interpret regulatory text at arm's length, through summaries and third-party analysis. The result is mapping that is plausible but imprecise — adequate for checkbox compliance, insufficient for enforcement scrutiny.

The founder reads EU AI Act Articles 12–17, DORA Article 8, GDPR Article 30, and NIS2 Article 21 in original numbered text, not digests. The framework mappings in `/v1/auditor/framework_map` reflect that legal reading directly — each mapping entry cites the specific article, paragraph, and sub-clause it addresses. Customer engagements include Data Processing Agreement and Master Service Agreement templates drafted to EU AI Act, GDPR, and DORA jurisdiction requirements. Cross-border compliance perspective — EU, US, and China — is structurally built into the roadmap, not an afterthought.

This combination of legal precision and direct engineering ownership is the substrate's primary differentiator. It is not reproducible by purchasing a compliance consultant or adding a legal reviewer to an engineering-led project.

---

## Community and Support

- **GitHub Discussions** — [github.com/attestplane/attestplane/discussions](https://github.com/attestplane/attestplane/discussions) — architecture questions, deployment guidance, framework mapping discussions
- **Discord** — coming M6 (2026-09); link will appear here
- **Mailing list** — TBD; announcements will be posted in GitHub Discussions until then
- **Compliance consulting engagements** — M5-M7 limited availability; contact via GitHub Discussions or the maintainer entity below

If you are an EU-regulated entity (DORA, BaFin, NIS2 scope) evaluating Attestplane for a 2026-08 deployment, reach out in Discussions. Design Partner Program slots will open at M6.

---

## Governance, License, and Legal

| Document | Purpose |
|---|---|
| [LICENSE](LICENSE) | Apache License 2.0 |
| [GOVERNANCE.md](GOVERNANCE.md) | Decision-making process, maintainer roles, succession plan |
| [TRADEMARK.md](TRADEMARK.md) | Attestplane™ trademark policy and permitted use |
| [SECURITY.md](SECURITY.md) | Vulnerability disclosure policy and contact |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution workflow, DCO sign-off requirements |

**License:** Apache 2.0. Contributions are accepted under the [Developer Certificate of Origin (DCO)](https://developercertificate.org/); sign off your commits with `git commit -s`.

**Trademark:** "Attestplane" and the Attestplane logo are trademarks of Attestplane Pte. Ltd. (Singapore). Use is governed by [TRADEMARK.md](TRADEMARK.md). The Apache 2.0 license grants broad code use rights; it does not grant trademark rights.

---

## Citation

If you use Attestplane in academic work, a published audit report, or a regulatory submission, please cite:

```bibtex
@software{attestplane2026,
  title        = {Attestplane: Open Trust Substrate for AI Agents},
  author       = {{Attestplane Pte. Ltd.}},
  year         = {2026},
  url          = {https://github.com/attestplane/attestplane},
  license      = {Apache-2.0},
  note         = {Pre-M5 alpha. Framework mappings cover EU AI Act Articles
                  12--17, NIST AI RMF, ISO/IEC 42001, SOC 2, DORA Article 8,
                  CRA 2027. Cite specific release tag for reproducibility.}
}
```

---

## Maintainer Entity

**Attestplane Pte. Ltd.**
Singapore (in formation as of 2026-05-17)

Attestplane Pte. Ltd. is the trademark holder, software publisher, and invoicing entity for commercial engagements. The Singapore entity structure is designed to support EU, US, and Asia-Pacific customer relationships.

*Attestplane provides technical compliance mapping. This software and its documentation do not constitute legal advice in any jurisdiction.*

---

*Built with Apache 2.0. Verified by the founder reading the actual articles.*
