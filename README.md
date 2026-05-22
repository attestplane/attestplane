# Attestplane

**Provenance for AI Agents** — open cryptographic evidence substrate that AI-using organisations record into, and that compliance professionals cite.

*Architectural inspiration: SLSA — the OpenSSF supply-chain attestation framework — applied to AI agent runtime behaviour rather than build artefacts.*

[![CI](https://github.com/attestplane/attestplane/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/attestplane/attestplane/actions/workflows/ci.yml)
[![Latest Release](https://img.shields.io/github/v/release/attestplane/attestplane?include_prereleases&sort=semver&display_name=tag&color=blueviolet&label=release)](https://github.com/attestplane/attestplane/releases)
[![PyPI](https://img.shields.io/pypi/v/attestplane?label=PyPI)](https://pypi.org/project/attestplane/)
[![npm](https://img.shields.io/npm/v/@attestplane/attestplane?label=npm)](https://www.npmjs.com/package/@attestplane/attestplane)
[![Apache 2.0 License](https://img.shields.io/github/license/attestplane/attestplane?color=blue)](LICENSE)
[![REUSE compliant](https://img.shields.io/badge/REUSE-3.3%20compliant-green)](REUSE.toml)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/12924/badge)](https://www.bestpractices.dev/projects/12924)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/attestplane/attestplane/badge)](https://scorecard.dev/viewer/?uri=github.com/attestplane/attestplane)
[![Last Commit](https://img.shields.io/github/last-commit/attestplane/attestplane/main)](https://github.com/attestplane/attestplane/commits/main)
[![Open Issues](https://img.shields.io/github/issues/attestplane/attestplane)](https://github.com/attestplane/attestplane/issues)
[![GitHub Stars](https://img.shields.io/github/stars/attestplane/attestplane?style=social)](https://github.com/attestplane/attestplane/stargazers)
[![DCO](https://img.shields.io/badge/contributor_agreement-DCO-lightgrey.svg)](CONTRIBUTING.md)

> **v1.0.x pre-GA tag line.** Not GA, not production-ready, not a
> compliance certification. v1.0 GA target 2026-08-15 per
> [SECURITY.md](SECURITY.md). Supply-chain evidence (Sigstore keyless +
> SLSA Build L3) live since v1.0.9 per
> [ADR-0018](docs/adr/0018-keyless-signing-and-slsa-provenance.md);
> cosign+SLSA verification recipes in
> [docs/release/verifying-signatures.md](docs/release/verifying-signatures.md).
>
> **Current verifier scope.** Attestplane is a pre-GA dual-SDK
> tamper-evident evidence substrate. It provides restricted
> canonicalization, SHA-256 hash-chain primitives, evidence payload
> schemas, sidecar signing/anchoring primitives, and read-only verifier
> predicates. The current CLI `attestplane verify` path is
> chain/report-oriented with ProofBundle metadata and
> `policy_trace_refs` closure checks. It must not be treated as a full
> ProofBundle, signed, anchored, or compliance certification verifier.

---

## What is Attestplane?

Attestplane is an Apache-2.0 cryptographic evidence substrate for recording AI agent actions, decisions, policy checks, lease lifecycle events, replay outcomes, and human approvals into a tamper-evident hash chain. The current pre-GA line includes sidecar signing and anchoring primitives plus proof-bundle export surfaces, but those sidecars are not part of the default CLI verifier path. `attestplane verify` is chain/report-oriented: it replays bundle events, compares the embedded `verification_report` with the recomputed chain result, and fails closed on malformed ProofBundle metadata and `policy_trace_refs` closure.

### Two sides of one evidence protocol

Attestplane is built around a single shared protocol — **`AP-EVD/1.0`** (Attestplane Evidence Protocol, [locked in ADR-0014](docs/adr/0014-adapter-conformance-fixture-pinning.md)) — that two distinct audiences interoperate through:

| Side | Who | Role |
|---|---|---|
| **Produce** | Banks · Insurers · Hospitals · Governments · HR platforms · any AI-using organisation under EU AI Act / DORA / NIS2 / GDPR / NIST AI RMF / China algorithmic-recommendation regs | Embed the SDK; emit byte-faithful evidence events from the AI runtime |
| **Verify** | Law firms · Big 4 AI assurance practices · Notified bodies (TÜV / BSI / DEKRA) · regulators (BaFin / CSSF / DNB / CAC) | Consume proof bundles and sidecar evidence; cite `AP-EVD/1.0` conformance in legal opinions, audit reports, conformity assessments |

Both sides depend on the same OSS protocol; both can independently inspect and replay the same bundle bytes. Law firms and Big 4 audit practices participate on **both** sides — they use AI internally (Produce) **and** issue compliance opinions to clients (Verify). The current pre-GA release line does not itself issue those opinions and does not certify legal compliance.

### What Attestplane is not

It does **not** replace LLM observability tools (LangSmith, LangFuse, Arize Phoenix, OpenLLMetry, Helicone) — those observe traces for development and debugging; Attestplane provides the forensic evidence layer they intentionally don't offer. *They observe. Attestplane attests.*

It does **not** replace AI governance SaaS (Credo AI, Holistic AI, Modulos, Saidot, Trustible) — those produce executive-facing dashboards; Attestplane is the cryptographic substrate they (and law firms / auditors) ingest as their `field_supported` evidence source.

It does **not** issue legal opinions or compliance certifications. `AP-EVD/1.0` makes one positive claim — that the recorded evidence is byte-faithful — and explicitly disclaims six others ([ADR-0014 § 11](docs/adr/0014-adapter-conformance-fixture-pinning.md)): legal compliance, runtime event semantics, PII redaction, AI output factuality, LLM provider endorsement, and replacement for professional opinions.

### SLSA framing note

The architectural inspiration is [SLSA](https://slsa.dev/) — the OpenSSF supply-chain attestation framework. Where SLSA proves the integrity of how a binary was built, Attestplane proves the integrity of how an AI agent behaved at runtime. Both produce signed, timestamped, verifiable evidence in formats that compliance, audit, and regulator workflows already accept.

> **A note on the SLSA framing.** This describes architectural inspiration and a positioning analogue, not affiliation with the OpenSSF or the SLSA project. Attestplane is an independent OSS project published by Attestplane Pte. Ltd. (Singapore, in formation 2026-05-17).

### Release status

> 🚀 New here? See [docs/quickstart.md](docs/quickstart.md) for a 5-minute walkthrough.
>
> A user-facing roadmap covering current capabilities (v1.0.x pre-GA), the v1.0 GA target (2026-08-15), and stability gates is published at [`docs/roadmap/USER_ROADMAP.md`](docs/roadmap/USER_ROADMAP.md). It complements the engineering-internal [`docs/roadmap/p3_release_roadmap.md`](docs/roadmap/p3_release_roadmap.md).

v0.0.1-alpha shipped foundational Python and TypeScript SDKs (deterministic serialization, SHA-256 hash chain, cross-language conformance vectors). **v0.8.0-beta.0** opened the beta prerelease line; the project is now on the **v1.0.x pre-GA tag line** — not GA, not production-ready, not a compliance certification. v1.0 GA target 2026-08-15 per [SECURITY.md](SECURITY.md). The public API and wire-format freeze is documented in [ADR-0016](docs/adr/0016-rc-api-freeze.md). Supply-chain evidence (Sigstore keyless + SLSA Build L3) has been live since **v1.0.9** per [ADR-0018](docs/adr/0018-keyless-signing-and-slsa-provenance.md); cosign+SLSA verification recipes in [docs/release/verifying-signatures.md](docs/release/verifying-signatures.md). The current pre-GA line ships:

- Verifier predicates + `attestplane` CLI for chain/report-oriented checks with metadata and `policy_trace_refs` closure; the CLI does not perform full ProofBundle, signature, anchor, or compliance certification verification
- JSONL storage backend (newline-terminated records, optional fsync,
  read-only corruption scan, 9-verb forbidden gate; alpha opt-in, not
  production storage)
- RFC-3161 anchoring with FreeTSA / DigiCert / Sigstore Rekor + real OCSP + multi-hop cert chains + eIDAS Trusted List
- Ed25519 sidecar signing scheme ([ADR-0005](docs/adr/0005-event-signing-scheme.md)) with KeyProvider abstraction + plurality verification
- v1 evidence event taxonomy ([ADR-0008](docs/adr/0008-evidence-event-taxonomy-v1.md), 12 types)
- Payload schemas + validators for `lease_lifecycle_event` ([A.7](docs/adr/0009-aios-absorption-boundary.md)), `policy_check_event` (A.8), `replay_event` (A.9)
- Machine-readable `ReasonCodeV1` enum (25 stable codes, [ADR-0010](docs/adr/0010-verification-reason-codes.md))
- `ProofBundle.policy_trace_refs` auto-derived index ([ADR-0012](docs/adr/0012-proof-bundle-policy-trace-refs.md))
- `GenericRuntimeAdapter` ABC + 14-verb forbidden gate ([ADR-0013](docs/adr/0013-generic-runtime-adapter-abc.md))
- `AP-EVD/1.0` adapter conformance fixture-pinning protocol ([ADR-0014](docs/adr/0014-adapter-conformance-fixture-pinning.md))
- Settlement-precondition + replay-manifest verifier predicates (read-only walkers, never re-execute)
- Obligation registries for EU AI Act Article 12 + DORA Article 8

The v1.0.x pre-GA tag line tightens verifier conformance, stable error taxonomy, retention/deletion proof markers, deterministic CLI JSON, and release-integrity evidence. It remains pre-GA substrate work and is not a legal compliance certification.

Cross-language byte-equality is enforced by frozen conformance fixtures (Python ↔ TypeScript). Green tests indicate substrate conformance, not production readiness or regulatory compliance.

Attestplane is infrastructure your team owns, operates, and audits independently. The substrate stays in your control plane.

---

## Why a cryptographic evidence substrate?

**Regulation demands verifiable evidence, not best-effort logs.** EU AI Act Article 12 requires "logging capabilities" that allow reconstruction of the system's behaviour. DORA Article 8 requires operational resilience with "audit trail" that survives incident investigation. NIST AI RMF asks for "traceable" processes. None of these obligations are satisfied by application logs that can be silently truncated, retroactively modified, or that carry no cryptographic proof of integrity.

**Why open-source, why substrate?** AI agents interact with financial data, health records, legal documents, and critical infrastructure. The code responsible for producing compliance evidence must itself be auditable. A closed SaaS audit platform creates the contradiction of an unverifiable verifier. Attestplane's core substrate is Apache 2.0 so that CISOs, auditors, regulators, and engineers can inspect, fork, and validate every hash function, every chain link, and future framework mapping logic — not as a marketing claim but as a technical design goal.

A substrate is by design not a finished product. It is a composable layer your application or platform embeds, connects to its own event streams, and operates within its own trust boundary. Your audit data never leaves your control plane.

## Integration partners (M5 roadmap)

Attestplane is designed to live underneath, not replace, the AI observability and governance tools you already use. The v0.1 / M5 release ships adapters for:

| Layer | Partner | Role | Status |
|-------|---------|------|--------|
| LLM observability (OSS) | [LangFuse](https://langfuse.com/) | Trace producer → Attestplane evidence sink | **Shipped** `LangFuseAdapter` + AP-EVD/1.0 fixture `langfuse_v1.json` |
| LLM observability (SaaS) | [LangSmith](https://docs.smith.langchain.com/) | Trace producer → Attestplane evidence sink | **Shipped** `LangSmithAdapter` + AP-EVD/1.0 fixture `langsmith_v1.json` |
| LLM observability (Arize) | [Phoenix](https://github.com/Arize-ai/phoenix) | OpenInference / OTel trace ingest | OpenLLMetry-compatible at M6 |
| Standards (transparency log) | [Sigstore / Rekor](https://www.sigstore.dev/) | Public transparency-log anchor (alongside RFC-3161 TSAs) | **Shipped** on `main` ([ADR-0006](docs/adr/0006-sigstore-rekor-redundant-anchor.md)) |
| Standards (wire format) | [in-toto Statement v1](https://github.com/in-toto/attestation) / [DSSE](https://github.com/secure-systems-lab/dsse) | Native serialization of Attestplane evidence events | **Shipped** on `main` |
| Standards (supply chain) | [SLSA](https://slsa.dev/) | Architectural framing inspiration; not membership | N/A — independent project |
| Standards (this project's protocol) | **`AP-EVD/1.0`** Attestplane Evidence Protocol ([ADR-0014](docs/adr/0014-adapter-conformance-fixture-pinning.md)) | Two-sided conformance protocol — Side B adapters target it; Side A verifiers cite it | Protocol v1.0 published in-repo (AP-EVD/1.0 conformance frozen); not GA package release (founder + 14-day RFC governance; OpenSSF/CNCF donation path reserved) |
| AI governance (US) | [Credo AI](https://www.credo.ai/), [Trustible](https://www.trustible.ai/) | Evidence ingestion into governance dashboards | Schema at M5; integration path documented |
| AI governance (UK/EU) | [Holistic AI](https://www.holisticai.com/), [Modulos](https://www.modulos.ai/), [Saidot](https://www.saidot.ai/) | Evidence ingestion into governance dashboards | Schema at M5; integration path documented |
| TSA (free/OSS) | [FreeTSA](https://freetsa.org/) | RFC-3161 anchor (default for OSS/dev) | Shipped on `main` (v0.0.3-alpha line) |
| TSA (commercial) | [DigiCert](https://www.digicert.com/) | RFC-3161 anchor (commercial SLA) | Shipped on `main` (v0.0.3-alpha line) |
| eIDAS qualified TSAs | EU LOTL members (e.g., [Guardtime KSI](https://guardtime.com/ksi)) | Pluggable qualified-TSA backends via `load_qualified_tsa_trust_roots()` | Shipped on `main` (v0.0.3-alpha line) |

Integration with each partner does **not** imply endorsement by the partner. These are technical integration paths from Attestplane's side; downstream partners may or may not formally support Attestplane in their documentation.

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
│  │  SHA-256     │   │  sidecar       │   │  supply-chain        │  │
│  │  hash chain  │──▶│  anchoring     │──▶│  provenance/SBOM     │  │
│  │  (shipped) ✓ │   │  primitives    │   │  (release gates)     │  │
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
│  │  Python (v1.0.x)    │  TypeScript (v1.0.x)                   │   │
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
- **Supply-chain attestation hygiene** — npm provenance, reproducible-wheel checks, and CycloneDX SBOM generation are part of the release pipeline. These release gates must not be described as SLSA L3 certification or production readiness.
- **RFC-3161 TSA anchoring sidecar primitives** — [ADR-0003](docs/adr/0003-tsa-rfc-3161-anchoring.md) defines pluggable TSA providers, batch-tail anchoring off the `append()` critical path, and sidecar `AnchorRecord` data that preserves the v0.0.1 chain contract. The current CLI verify path does not perform anchored verification.

---

## Current release posture: v1.0.x pre-GA tag line

The project is currently on the **v1.0.x pre-GA tag line**: not GA, not
production-ready, not a compliance certification. The **v1.0 GA target
is 2026-08-15** per [SECURITY.md](SECURITY.md). The historical beta
line remains reproducible as `0.8.0-beta.0`; the prior Controlled
Availability cut `v0.8.5` is superseded by the v1.0.x pre-GA tag line.

Supply-chain evidence (Sigstore keyless cosign bundles + SLSA Build L3
provenance) has been live on every release since **v1.0.9** per
[ADR-0018](docs/adr/0018-keyless-signing-and-slsa-provenance.md);
downstream cosign and slsa-verifier recipes are documented in
[docs/release/verifying-signatures.md](docs/release/verifying-signatures.md).

The v1.0.x line freezes public SDK exports and wire-format behavior under
[ADR-0016](docs/adr/0016-rc-api-freeze.md) and the [compatibility policy](docs/spec/compat.md).
It expands the core with schemas, sidecar primitives, storage,
adapters, verifier predicates, public API drift gates, storage compatibility
policy, and release provenance hygiene, but it is not GA, not production-ready,
and not compliance-ready.

The package and release registry surfaces remain the source of truth. Package
publication now runs through the GitHub Actions CD path documented in
[`docs/runbooks/github-cd-release.md`](docs/runbooks/github-cd-release.md);
local machines prepare and dispatch releases but do not directly publish to
PyPI or npm.

The local automation programming loop is named
[`autodev-train`](docs/runbooks/autodev-train.md). The old
`attestplane-alpha-train` name remains only as a compatibility alias for the
alpha-stage wrapper and state directory.

The current `attestplane verify` command is deliberately narrow:

- It replays bundle events and checks hash-chain/report agreement.
- It fails closed on malformed ProofBundle metadata and `policy_trace_refs` closure.
- It emits stable `VERIFY_*` error codes in JSON output.
- It verifies optional `retention_proofs` marker shape and event-hash references.
- It does not perform full ProofBundle verification.
- It does not verify signatures or anchors.
- It does not issue compliance certification.

## Published v1.0.x pre-GA status

Implemented in the published v1.0.x pre-GA artifacts:

- Python SDK
- TypeScript SDK
- deterministic serialization
- SHA-256 hash-chain primitives
- cross-language conformance vectors
- CI / CodeQL / OSV / SBOM / reproducible-build hygiene

Designed and merged on `main` since v0.0.1-alpha (pre-GA substrate surface
through the current v1.0.x pre-GA tag line; not a production claim):

- [ADR-0004 — AIOS-to-Attestplane scope boundary](docs/adr/0004-aios-to-attestplane-boundary.md): substrate-vs-execution-plane separation locked
- [ADR-0008 — Evidence event taxonomy v1](docs/adr/0008-evidence-event-taxonomy-v1.md): twelve evidence event types + the [taxonomy spec](docs/spec/evidence-event-taxonomy-v1.md)
- [`ATTESTATION_GATES.md` — five gates A1–A5](docs/architecture/ATTESTATION_GATES.md): pre-merge / nightly / release-blocker discipline
- `GenericRuntimeAdapter` ABC (Python + TypeScript): runtime evidence ingestion/normalization only; it is not runtime execution authority
- Compliance obligation registry (EU AI Act Article 12 + DORA Article 8): machine-readable framework mappings with locked `implementation_status` enum per the claim-safety triad
- Negative conformance vectors: five frozen broken-chain fixtures pinning gates A2 and A3
- Stable verifier error taxonomy and retention/deletion proof marker checks,
  now expanded with RC-prep negative/version-skew/tampered conformance cases,
  still under prerelease/non-certification boundaries

Not yet implemented:

- additional obligation registries (NIS2 Article 21, GDPR Article 30, ISO 42001, NIST AI RMF)
- AIOS / LangGraph / OpenAI / Claude / Codex / MCP runtime integrations beyond
  the shipped generic adapter/conformance substrate
- production / enterprise / cloud features

| Artifact | Channel | Verify |
|---|---|---|
| `attestplane` (latest v1.0.x) | [PyPI](https://pypi.org/project/attestplane/) | GitHub OIDC trusted publishing; cosign + SLSA Build L3 since v1.0.9 |
| `@attestplane/attestplane` (latest v1.0.x) | [npm](https://www.npmjs.com/package/@attestplane/attestplane) | npm provenance via GitHub OIDC; cosign + SLSA Build L3 since v1.0.9 |
| GitHub Releases | [`v1.0.x` tags](https://github.com/attestplane/attestplane/releases) | wheel + sdist + npm tarball + checksums + artifact manifest + cosign bundles + `.intoto.jsonl` SLSA provenance |
| v1.6.2 release note | [docs/releases/v1.6.2.md](docs/releases/v1.6.2.md) | user-visible planned-task refetch race fix; CI-only items separated as infrastructure |

Default PyPI and npm installs resolve to the latest v1.0.x tag. This is
the pre-GA tag line; resolving to it does not change the pre-GA claim
boundary. v1.0 GA target 2026-08-15 per [SECURITY.md](SECURITY.md).

The local release train also writes a post-release integration evidence packet
under `release/alpha-train/reports/`. It reads GitHub Release/workflow facts,
PyPI/npm registry facts, Linear issue-flow facts, Sentry failure-source facts,
CodeRabbit advisory availability, local Codex Security check surfaces, and the
SQLite `git_push_tasks` queue, then emits JSON plus Markdown for human review.
These integration reports are non-authoritative: they do not approve publish,
create tags or releases, dispatch workflows, move npm dist-tags, or grant
compliance claims. Transient git-push failures are recorded as queued
transport state and do not block later alpha candidates. See
[`docs/runbooks/alpha-release-integrations.md`](docs/runbooks/alpha-release-integrations.md).

## Quickstart

What works today, end-to-end.

### Python

```bash
pip install attestplane
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
npm install @attestplane/attestplane
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
| Full CLI ProofBundle, signed, and anchored verification | v0.1+ |
| FastAPI / Express / NestJS / Django helpers | M5 |
| Rust SDK (`cargo add attestplane`) | M7 |
| Auditor JSON API + framework-mapping endpoint | M5 + M6 |
| Production storage and multi-writer concurrency | M6+ |

---

## Future Compliance Framework Mapping Targets

The table below lists roadmap targets for future compliance mapping. The
published v1.0.x pre-GA artifacts include obligation registry data and
chain/report-oriented verifier predicates, but they do not ship a full
ProofBundle, signed, anchored, or compliance certification verifier. All
entries below carry `implementation_status` values from the locked four-value
enum (`mapping_target` / `designed_toward` / `field_supported` /
`verified_in_test`) per [`docs/policy/`](docs/policy/forbidden_claims.md).

| Framework | Relevant controls | Current substrate status |
|---|---|---|
| **EU AI Act** | Articles 12 (logging), 13 (transparency), 14 (human oversight), 15 (accuracy/robustness), 16 (obligations for providers), 17 (quality management) | Designed toward EU AI Act Article 12 auditability; the Art. 12(3) field set (`session_id`, `reference_db_ref`, `matched_input_ref`, `human_verifier`) is `field_supported`. Obligation registry merged on `main`; ships in v0.1 / M5. |
| **DORA** | Article 8 (ICT risk management), Article 10 (detection), Article 17 (incident reporting) | Designed toward DORA Article 8 audit-trail obligations; Art. 8(5) privileged-access inventory mechanism is `field_supported`; Art. 8(1), 8(3), 8(7), 8(8) are `designed_toward`. Obligation registry merged on `main`; ships in v0.1 / M5. |
| **NIST AI RMF** | GOVERN 1.1–1.7, MAP 1.1–5.2, MEASURE 1.1–4.2, MANAGE 1.1–4.4 | Mapping target for future compliance mapping (M7+) |
| **ISO/IEC 42001** | §6.1 risk, §8.4 data for AI, §9.1 monitoring and measurement, §10.2 nonconformity | Mapping target for future compliance mapping (M7+) |
| **SOC 2** | CC7.2 (system monitoring), CC7.3 (security event evaluation), CC4.1 (COSO monitoring) | Mapping target for future compliance mapping (M7+) |
| **CRA 2027** | Article 13 (essential cybersecurity requirements), Annex I Part I §2 (logging) | SBOM hygiene exists; CRA mapping is a roadmap target |

> *This table represents technical mapping. It does not constitute legal advice. Your organization's compliance obligations depend on your specific facts and jurisdiction. Consult qualified legal counsel before relying on any regulatory interpretation.*

---

## Roadmap

| Milestone | Target | Scope |
|---|---|---|
| **M5 — v1.0 GA** | 2026-08-15 | Self-hosted OSS substrate · full CLI ProofBundle verification · FastAPI/Express helpers · expanded framework mapping · production-storage design review |
| **M6 — Cloud preview** | 2026-09 | Attestplane Cloud hosted TSA + Sigstore Rekor mirror + framework auto-update · free for EU deployments · Design Partner Program launch |
| **M7 — Client-side DP aggregation** | 2026-Q4 | Client-side differential privacy SDK (Rust + TypeScript + Python) · ε-configurable Laplace noise · regulator dashboard preview · customer attestation data never leaves customer control plane |
| **M8 — Paid tier** | 2027-Q1+ | Pro / Team / Enterprise paid tiers · SSO/SCIM/RBAC · SLA · first FTE hire |

Current status: **v1.0.x pre-GA tag line; v1.0 GA target 2026-08-15** — community velocity stage. Contributions,
issue reports, and deployment feedback are the project's most valuable input
right now.

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
| [docs/architecture/ATTESTATION_GATES.md](docs/architecture/ATTESTATION_GATES.md) | Five substrate-level gates A1–A5 (pre-merge / nightly / release-blocker) |
| [docs/non-goals.md](docs/non-goals.md) | Alpha non-goals and forbidden over-claims |
| [docs/errors.md](docs/errors.md) | Stable verifier error taxonomy |
| [docs/spec/aia-12-aligned-profile.md](docs/spec/aia-12-aligned-profile.md) | Alpha AIA-12 aligned evidence profile; not a legal conclusion |
| [docs/architecture/verifier_independence.md](docs/architecture/verifier_independence.md) | Independent verifier trust model for exported evidence |
| [docs/architecture/tsa-provider-interface.md](docs/architecture/tsa-provider-interface.md) | TSA provider abstraction boundary; not a new trust root |
| [docs/security/threat-model-v0.0.5-alpha.md](docs/security/threat-model-v0.0.5-alpha.md) | v0.0.5-alpha threat model snapshot |
| [docs/spec/evidence-event-taxonomy-v1.md](docs/spec/evidence-event-taxonomy-v1.md) | The v1 evidence event taxonomy (twelve types) |
| [docs/policy/](docs/policy/forbidden_claims.md) | Public-facing claim policy (forbidden / allowed / enforcement) |

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
  version      = {0.0.3-alpha},
  note         = {Public alpha; substrate core only. Cite the specific
                  release tag (e.g. v0.0.3-alpha) for reproducibility.
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
