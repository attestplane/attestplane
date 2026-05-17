# Attestplane

**Open Trust Substrate for AI Agents**

[![CI](https://github.com/attestplane/attestplane/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/attestplane/attestplane/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/attestplane/attestplane?include_prereleases&sort=semver&display_name=tag&color=blueviolet&label=release)](https://github.com/attestplane/attestplane/releases)
[![PyPI (TestPyPI)](https://img.shields.io/badge/TestPyPI-attestplane%200.0.1-blue)](https://test.pypi.org/project/attestplane/0.0.1/)
[![npm](https://img.shields.io/npm/v/@attestplane/attestplane?label=npm)](https://www.npmjs.com/package/@attestplane/attestplane)
[![Apache 2.0 License](https://img.shields.io/github/license/attestplane/attestplane?color=blue)](LICENSE)
[![REUSE compliant](https://img.shields.io/badge/REUSE-3.3%20compliant-green)](REUSE.toml)
[![Last Commit](https://img.shields.io/github/last-commit/attestplane/attestplane/main)](https://github.com/attestplane/attestplane/commits/main)
[![Open Issues](https://img.shields.io/github/issues/attestplane/attestplane)](https://github.com/attestplane/attestplane/issues)
[![GitHub Stars](https://img.shields.io/github/stars/attestplane/attestplane?style=social)](https://github.com/attestplane/attestplane/stargazers)
[![Alpha — API may change](https://img.shields.io/badge/status-alpha-orange.svg)](#roadmap)
[![DCO](https://img.shields.io/badge/contributor_agreement-DCO-lightgrey.svg)](CONTRIBUTING.md)

> **Alpha software.** API surfaces are not yet stable. Not for production use without review of your specific compliance obligations.

---

## What is Attestplane?

Attestplane is an Apache-2.0 open-source attestation and audit substrate for AI agents, extracted from AIOS.

It records agent actions, decisions, policy checks, and compliance checkpoints into tamper-evident evidence chains. v0.0.1-alpha provides foundational Python and TypeScript SDKs, deterministic serialization, SHA-256 hash-chain primitives, and cross-language conformance vectors. It is a developer alpha substrate, not a finished compliance platform.

Attestplane is designed toward independent auditability and future compliance framework mapping, including EU AI Act Article 12 and DORA Article 8. External anchoring, verifier CLI, proof bundles, durable storage, and runtime adapters are roadmap items for v0.1/M5 and later.

Attestplane is not a compliance-as-a-service platform. It is infrastructure your team owns, operates, and audits independently. Framework mappings are roadmap targets; the audit chain stays in your control plane.

---

## Why Open Trust Substrate?

**Regulation demands verifiable evidence, not best-effort logs.** EU AI Act Article 12 requires "logging capabilities" that allow reconstruction of the system's behaviour. DORA Article 8 requires operational resilience with "audit trail" that survives incident investigation. NIST AI RMF asks for "traceable" processes. None of these obligations are satisfied by application logs that can be silently truncated, retroactively modified, or that carry no cryptographic proof of integrity.

**Why open-source, why substrate?** AI agents interact with financial data, health records, legal documents, and critical infrastructure. The code responsible for producing compliance evidence must itself be auditable. A closed SaaS audit platform creates the contradiction of an unverifiable verifier. Attestplane's core substrate is Apache 2.0 so that CISOs, auditors, regulators, and engineers can inspect, fork, and validate every hash function, every chain link, and future framework mapping logic — not as a marketing claim but as a technical design goal.

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
│  │  SHA-256     │   │  RFC-3161      │   │  Sigstore / SLSA L3  │  │
│  │  hash chain  │──▶│  TSA anchoring │──▶│  signing + SBOM      │  │
│  │  (v0.0.1) ✓  │   │  (v0.1, M5)    │   │  (v0.2, M6+)         │  │
│  └──────────────┘   └────────────────┘   └──────────────────────┘  │
│          │                                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Auditor JSON API  (M5)                                       │   │
│  │  • chain_verify   • evidence_bundle   • replay_audit          │   │
│  │  • framework_map  • anchor_status                             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│          │                                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Framework mapping layer  (M5)                                │   │
│  │  EU AI Act Art 12-17 / NIST AI RMF / ISO 42001 / SOC 2 CC7   │   │
│  │  DORA Art 8 / CRA 2027 / GDPR Art 30                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│          │                                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  SDKs                                                         │   │
│  │  Python (v0.0.1 ✓)  │  TypeScript (v0.0.1 ✓)                  │   │
│  │  FastAPI / Express / NestJS / Django helpers (M5)             │   │
│  │  Rust crate (M7)                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

- **Tamper-evident SHA-256 hash chain (shipping in v0.0.1-alpha)** — each event record includes the hash of the previous record; any insertion, deletion, or modification breaks the chain and is immediately detectable by `substrate.verify()`. Locked by [ADR-0002](docs/adr/0002-substrate-data-model-and-hash-chain-v0.md) and a frozen set of cross-language conformance vectors.
- **Cross-language byte-conformance** — Python and TypeScript SDKs at v0.0.1 produce byte-identical `event_hash` values for every entry in [`sdk/python/tests/conformance/vectors.json`](sdk/python/tests/conformance/vectors.json). Drift fails CI on every commit. A Rust SDK is planned for M7.
- **EU AI Act Article 12(2)(a) fields built in** — `session_id`, `reference_db_ref`, `matched_input_ref`, `human_verifier` are first-class fields on every event from v0.0.1.
- **GDPR pseudonymization at the type level** — the `SubjectRef` strong type forces callers to declare a pseudonymization scheme (`sha256_salted`, `opaque`, `none`); raw PII cannot be silently written into the subject field.
- **Self-hosted first** — the substrate runs inside your own infrastructure; your attestation data stays in your control plane. EU financial entities subject to DORA Recital 56 can deploy without adding Attestplane as a Critical Third-Party Provider.
- **Supply-chain attestation** — npm provenance is published to the Sigstore transparency log on every TypeScript SDK release; Python SDK ships with reproducible-wheel verification and CycloneDX SBOM on every push. Full Sigstore release signing and SLSA L3 build provenance are planned for M5–M6.
- **RFC-3161 TSA anchoring design** — [ADR-0003](docs/adr/0003-tsa-rfc-3161-anchoring.md) locks the v0.1 design: pluggable TSA providers, batch-tail anchoring off the `append()` critical path, CAdES-A long-term validation evidence frozen at issuance, sidecar `AnchorRecord` that preserves the v0.0.1 chain contract. Code ships with M5.

---

## Current release: v0.0.1-alpha (2026-05-17)

The first public alpha is live on TestPyPI (sandbox) and npm (production with the `alpha` dist-tag). The shipped surface is the substrate core (types, restricted-JCS canonicalization, SHA-256 hash chain, in-memory append-only container). RFC-3161 anchoring, signing, framework-mapping endpoint, FastAPI/Express/NestJS helpers, and a Rust SDK are **not** in v0.0.1 — see the [roadmap](#roadmap) below.

## v0.0.1-alpha status

Implemented in v0.0.1-alpha:

- Python SDK
- TypeScript SDK
- deterministic serialization
- SHA-256 hash-chain primitives
- cross-language conformance vectors
- CI / CodeQL / OSV / SBOM / reproducible-build hygiene

Not yet implemented:

- verifier CLI
- proof bundle / auditor export schema
- full EU AI Act / DORA / NIS2 / GDPR obligation registry
- RFC3161/TSA anchoring
- Sigstore/Rekor integration
- durable storage backend
- AIOS / LangGraph / OpenAI / Claude / Codex / MCP adapters
- production / enterprise / cloud features

| Artifact | Channel | Verify |
|---|---|---|
| `attestplane==0.0.1` | [TestPyPI](https://test.pypi.org/project/attestplane/0.0.1/) | OIDC trusted publishing |
| `@attestplane/attestplane@0.0.1` | [npm](https://www.npmjs.com/package/@attestplane/attestplane) | Sigstore provenance: [logIndex=1556001175](https://search.sigstore.dev/?logIndex=1556001175) |
| GitHub Release | [v0.0.1-alpha](https://github.com/attestplane/attestplane/releases/tag/v0.0.1-alpha) | wheel + sdist + npm tarball + CycloneDX SBOM (JSON + XML) |

## Quickstart

What works today, end-to-end.

### Python

```bash
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            attestplane==0.0.1
```

```python
from datetime import UTC, datetime
from attestplane import AttestSubstrate, EventDraft, SubjectRef

sub = AttestSubstrate()

chained = sub.append(
    EventDraft(
        event_type="ai_decision",
        actor="agent://recsys/v1",
        payload={"outcome": "approved", "confidence_bp": 9120},
        session_id="session-2026-05-17-abc",
        subject_ref=SubjectRef(scheme="sha256_salted", value="2c1b...e9"),
    ),
    now=datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC),
)

print(chained.event_hash.hex())   # 32-byte SHA-256 of the canonical event
assert sub.verify().ok            # chain integrity check
```

### TypeScript

```bash
npm install @attestplane/attestplane@alpha
```

```typescript
import {
  AttestSubstrate,
  makeEventDraft,
  makeSubjectRef,
} from "@attestplane/attestplane";

const sub = new AttestSubstrate();

const chained = sub.append(
  makeEventDraft({
    event_type: "ai_decision",
    actor: "agent://recsys/v1",
    payload: { outcome: "approved", confidence_bp: 9120 },
    session_id: "session-2026-05-17-abc",
    subject_ref: makeSubjectRef("sha256_salted", "2c1b...e9"),
  }),
  { now: new Date("2026-05-17T12:00:00.000Z") },
);

console.log(Buffer.from(chained.event_hash).toString("hex"));
console.log(sub.verify().ok);
```

The Python and TypeScript snippets above produce **byte-identical** `event_hash` values for the same input. Cross-language conformance is enforced in CI against the frozen [`vectors.json`](sdk/python/tests/conformance/vectors.json) contract.

### Not yet shipped (planned)

| Surface | Target |
|---|---|
| RFC-3161 TSA anchoring | v0.1, M5 — [ADR-0003](docs/adr/0003-tsa-rfc-3161-anchoring.md) |
| Production PyPI publication | M5 |
| FastAPI / Express / NestJS / Django helpers | M5 |
| Rust SDK (`cargo add attestplane`) | M7 |
| Auditor JSON API + framework-mapping endpoint | M5 + M6 |
| Event signing (Ed25519 per-substrate keypair) | M7 — anticipated ADR-0004 |
| Sigstore / Rekor as redundant anchor | M6 — anticipated ADR-0005 |
| Durable storage + multi-writer concurrency | M6 — anticipated ADR-0004 |
| Attestplane CLI | M5 |

---

## Future Compliance Framework Mapping Targets

The table below lists roadmap targets for future compliance mapping. v0.0.1-alpha does not ship a full obligation registry, verifier expectation registry, or proof bundle schema.

| Framework | Relevant controls | Current v0.0.1-alpha status |
|---|---|---|
| **EU AI Act** | Articles 12 (logging), 13 (transparency), 14 (human oversight), 15 (accuracy/robustness), 16 (obligations for providers), 17 (quality management) | Designed toward EU AI Act Article 12 auditability; only selected Art. 12(2)(a) reference fields are implemented today |
| **NIST AI RMF** | GOVERN 1.1–1.7, MAP 1.1–5.2, MEASURE 1.1–4.2, MANAGE 1.1–4.4 | Roadmap target for future compliance mapping |
| **ISO/IEC 42001** | §6.1 risk, §8.4 data for AI, §9.1 monitoring and measurement, §10.2 nonconformity | Roadmap target for future compliance mapping |
| **SOC 2** | CC7.2 (system monitoring), CC7.3 (security event evaluation), CC4.1 (COSO monitoring) | Roadmap target for future compliance mapping |
| **DORA** | Article 8 (ICT risk management), Article 10 (detection), Article 17 (incident reporting) | Roadmap target for future compliance mapping |
| **CRA 2027** | Article 13 (essential cybersecurity requirements), Annex I Part I §2 (logging) | SBOM hygiene exists; CRA mapping is a roadmap target |

> *This table represents technical mapping. It does not constitute legal advice. Your organization's compliance obligations depend on your specific facts and jurisdiction. Consult qualified legal counsel before relying on any regulatory interpretation.*

---

## Roadmap

| Milestone | Target | Scope |
|---|---|---|
| **M5 — v0.1.0 alpha hardening** | 2026-08-15 | Self-hosted OSS substrate · SHA-256 chain (v0.0.1 ✓) · RFC-3161 anchoring implementation · FastAPI/Express helpers · initial framework mapping · CycloneDX SBOM (v0.0.1 ✓) · CLI |
| **M6 — Cloud preview** | 2026-09 | Attestplane Cloud hosted TSA + Sigstore Rekor mirror + framework auto-update · free for EU deployments · Design Partner Program launch |
| **M7 — Client-side DP aggregation** | 2026-Q4 | Client-side differential privacy SDK (Rust + TypeScript + Python) · ε-configurable Laplace noise · regulator dashboard preview · customer attestation data never leaves customer control plane |
| **M8 — Paid tier** | 2027-Q1+ | Pro / Team / Enterprise paid tiers · SSO/SCIM/RBAC · SLA · first FTE hire |

Current status: **pre-M5 alpha** — community velocity stage. Contributions, issue reports, and deployment feedback are the project's most valuable input right now.

---

## Who is Behind Attestplane

Attestplane was designed and built by a China-licensed Business and Compliance lawyer who became frustrated with the gap between how compliance frameworks describe AI system obligations and what engineering teams are actually given to work with. Most tooling in this space is built by engineers who interpret regulatory text at arm's length, through summaries and third-party analysis. The result is mapping that is plausible but imprecise — adequate for checkbox compliance, insufficient for enforcement scrutiny.

The founder reads EU AI Act Articles 12–17, DORA Article 8, GDPR Article 30, and NIS2 Article 21 in original numbered text, not digests. The framework-mapping endpoint planned for M5 (`/v1/auditor/framework_map`) will reflect that legal reading directly — each mapping entry will cite the specific article, paragraph, and sub-clause it addresses. The v0.0.1 substrate already exposes the Article 12(2)(a) field set (`session_id`, `reference_db_ref`, `matched_input_ref`, `human_verifier`) as first-class types so that today's recorded events are forward-compatible with the M5 mapping. Customer engagements will include Data Processing Agreement and Master Service Agreement templates drafted to EU AI Act, GDPR, and DORA jurisdiction requirements. Cross-border compliance perspective — EU, US, and China — is structurally built into the roadmap, not an afterthought.

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
| [CONTRIBUTORS.md](CONTRIBUTORS.md) | People who have contributed to this project |
| [CHANGELOG.md](CHANGELOG.md) | Release history and supply-chain hashes |
| [docs/adr/](docs/adr/README.md) | Architecture Decision Records |

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
  version      = {0.0.1-alpha},
  note         = {Pre-M5 alpha; substrate core only. Cite the specific
                  release tag (e.g. v0.0.1-alpha) for reproducibility.
                  Framework mappings cover EU AI Act Articles 12--17,
                  NIST AI RMF, ISO/IEC 42001, SOC 2, DORA Article 8,
                  CRA 2027 (mapping endpoint planned for M5).}
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
