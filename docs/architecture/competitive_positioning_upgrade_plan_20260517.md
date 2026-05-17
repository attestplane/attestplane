<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Competitive Positioning Upgrade Plan — 2026-05-17

> **Status:** Planning. Authored after the 20-agent competitive
> research session of 2026-05-17 (Trillian / Sigstore / Rekor / immudb
> / QLDB / Guardtime KSI / in-toto / SLSA / TUF / Notary / GUAC /
> OpenTimestamps / LangSmith / LangFuse / Arize Phoenix / Helicone /
> OpenLLMetry / Credo AI / Holistic AI / Modulos / Trustible /
> Saidot).
>
> **Scope:** v0.0.2-alpha → v0.1.0 (M5) realignment based on the
> finding that Attestplane has zero direct competitors but several
> adjacent threats and opportunities that require explicit
> positioning + integration work.

## 1. Findings driving this plan

The competitive research surfaced five load-bearing facts:

1. **No direct competitor exists**. The five-dimensional intersection
   (AI agent runtime SDK + cryptographic hash chain + RFC-3161/OCSP +
   EU AI Act / DORA obligation registry + Apache 2.0 + lawyer-founder
   narrative) is currently unoccupied by any of the 20 surveyed
   products.
2. **LangSmith is the biggest indirect threat**. Its 2025+ official
   claim of EU AI Act Art. 12 / 19 compliance is technically
   incomplete (no hash chain, no RFC-3161, no tamper evidence) but
   marketing-strong. If LangChain adds these, the moat narrows.
3. **Standards exist; Attestplane should adopt them, not compete**.
   in-toto (CNCF graduated 2025-02), SLSA, Sigstore, DSSE are the
   wire formats and transparency-log primitives the broader ecosystem
   has converged on. Inventing parallel formats is competitive
   suicide.
4. **Tier D AI governance platforms (Credo AI, Holistic AI, Modulos,
   Trustible, Saidot) are channel partners, not competitors**. None
   of them ship cryptographic attestation primitives; all of them
   have enterprise GRC sales channels Attestplane lacks.
5. **eIDAS QTSP territory is occupied by Guardtime KSI** (40+
   patents, NATO/Estonian government deployment). Attestplane MUST
   NOT apply for QTSP status; instead, treat any eIDAS-listed QTSP
   as a pluggable anchor backend.

## 2. Strategic re-framing

The pre-2026-05-17 positioning was implicitly "**audit substrate for
AI agents**". The post-research positioning is:

> **Attestplane is the SLSA-for-AI-Agents.** A bottom-up cryptographic
> evidence substrate that compliance platforms cite, not replace.

Three operational consequences:

- **For developers**: integration story is "add Attestplane SDK to
  your existing LangSmith / LangFuse / Arize pipeline — we don't
  replace them, we add the cryptographic layer they don't have."
- **For compliance officers**: integration story is "your existing
  Credo AI / Holistic AI / Saidot dashboard ingests Attestplane
  evidence as its `field_supported` data source for Art. 12."
- **For regulators**: positioning is "Attestplane records produce
  evidence in the same in-toto / Sigstore family of formats that
  SLSA / supply-chain compliance already accepts; the only novel
  element is the 12-event AI-agent-runtime predicate vocabulary."

## 3. Tracks

Five parallel tracks. Each track has a measurable acceptance criterion.

### Track 1 — Wire-format alignment with in-toto / DSSE

**Goal:** Attestplane evidence events serialize as `in-toto Statement`
envelopes with a custom `predicateType =
"https://attestplane.io/v1/agent-runtime-event"`. This makes every
Attestplane chain natively consumable by `cosign verify`, `slsa-verifier`,
GUAC ingestion, and any downstream tool that already speaks in-toto.

**Acceptance:**

- `attestplane.proof_bundle` ships an `as_in_toto_statement()` method
  that produces a valid in-toto Statement v1 envelope.
- The envelope's `subject[0].digest.sha256` matches the chain head
  `event_hash`.
- Round-trip: a Statement produced by Attestplane can be parsed by
  `in-toto-rs` or `python-in-toto` without error.
- DSSE envelope (`payloadType =
  "application/vnd.in-toto+json"`, `payload = base64(Statement)`) is
  the default serialization.

**Effort:** 2 PD. **Priority:** P0.

### Track 2 — Sigstore / Rekor as secondary anchor

**Goal:** Add `SigstoreRekorAnchor` alongside the existing RFC-3161
anchor implementation. ADR-0006 (Sigstore / Rekor transparency-log
integration) was anticipated but unimplemented; this track ships it.

**Acceptance:**

- `attestplane.anchoring.SigstoreRekorAnchor` provider implements
  `TSAProvider` and submits DSSE envelopes to a public Rekor
  instance (default `https://rekor.sigstore.dev`).
- `AnchorRecord` carries the Rekor `logIndex` + `logID` + inclusion
  proof.
- Multi-anchor mode (RFC-3161 + Rekor) recommended in updated docs;
  plurality recommendation in ADR-0003 § 2 generalised.
- Test using `sigstore-python` library (optional dep in `[anchor]`
  extras).

**Effort:** 3 PD (the optional dep is heavy). **Priority:** P0.

### Track 3 — LangSmith / LangFuse integration adapters

**Goal:** Ship two concrete `GenericRuntimeAdapter` implementations
that translate LangSmith trace events and LangFuse trace events into
Attestplane `EventDraft` values. This is the "compliance patch
layer" play — existing LangSmith / LangFuse users add Attestplane
SDK alongside their observability tool, not instead.

**Acceptance:**

- `attestplane.adapters.langsmith` ships an adapter that consumes
  the LangSmith `Run` shape (https://docs.smith.langchain.com/) and
  emits `tool_call_event` / `policy_check_event` /
  `human_approval_event` etc. per the v1 taxonomy.
- `attestplane.adapters.langfuse` ships the same for LangFuse's
  `Trace` / `Observation` shape.
- Both adapters are subject to the `GenericRuntimeAdapter`
  forbidden-verb gate (no execute / grant / decide methods).
- Round-trip example in `examples/python/`: ingest a sample
  LangSmith / LangFuse trace, produce a verifiable proof bundle.
- Live integration tests use Recorded fixtures (no live API calls
  in CI).

**Effort:** 3 PD (1.5 each). **Priority:** P0.

### Track 4 — Channel partner integration framework

**Goal:** A documented framework for "Attestplane as Evidence
Source" — the pattern that Tier D AI governance platforms (Credo AI
/ Holistic AI / Modulos / Trustible / Saidot) can ingest Attestplane
proof bundles as their `field_supported` evidence layer.

**Acceptance:**

- `docs/integrations/governance_platforms.md` documents the data
  flow (Attestplane substrate → proof bundle → governance platform's
  evidence ingestion).
- `schemas/v1/governance_ingestion.schema.json` — opinionated subset
  of `proof_bundle.schema.json` optimized for governance-platform
  consumption (drops events, keeps `framework_mappings` + chain
  metadata + Sigstore bundle).
- One worked example: a Markdown walkthrough of "how a Credo AI
  customer would surface Attestplane evidence in their dashboard"
  (no actual Credo AI API call, just the schema mapping).

**Effort:** 1.5 PD. **Priority:** P1.

### Track 5 — Positioning, framing, claim updates

**Goal:** README, claims policy, allowed_claims, forbidden_claims,
and the public-facing tagline updated to match the new positioning.
No code changes — pure messaging.

**Acceptance:**

- README headline updated to **"Attestplane is the SLSA-for-AI-Agents"**.
- README integration table lists LangSmith / LangFuse / Arize
  Phoenix / OpenLLMetry as supported observability partners.
- README compliance-mapping table adds rows for Sigstore / in-toto
  / SLSA wire-format compatibility.
- `docs/policy/allowed_claims.md` adds permitted phrases:
  - "in-toto Statement compatible"
  - "Sigstore-bundle compatible"
  - "SLSA-for-AI-Agents"
  - "LangSmith / LangFuse evidence-layer adapter"
- `docs/policy/forbidden_claims.md` adds:
  - "EU AI Act compliant" (still forbidden — only LangSmith's marketing claim)
  - "Replaces Credo AI / Holistic AI / Modulos / Trustible / Saidot"
    (forbidden — positioning is complement, not replacement)
  - "First / only / leading" superlatives in competitive context.

**Effort:** 1 PD. **Priority:** P0 (do first; everything else
references the new framing).

## 4. Sequencing

Implementation order (highest leverage first):

| Order | Track | Effort | Rationale |
|-------|-------|--------|-----------|
| 1 | **Track 5** (framing) | 1 PD | Everything else depends on the new positioning; ship the words first |
| 2 | **Track 1** (in-toto wire) | 2 PD | Unlocks Tracks 2, 3, 4; smallest code surface; highest ecosystem leverage |
| 3 | **Track 3** (LangSmith / LangFuse adapters) | 3 PD | Directly addresses the #1 indirect threat (LangSmith); creates immediate "use both" upgrade story |
| 4 | **Track 2** (Sigstore / Rekor anchor) | 3 PD | Anticipated ADR-0006 lands; gives users a free public transparency log alternative to paid TSAs |
| 5 | **Track 4** (channel framework) | 1.5 PD | Sales-enablement; can lag until first concrete partner conversation |

**Total effort:** 10.5 PD. **Target completion:** M5 (2026-08-15).

## 5. Out of scope (explicit "no")

Each item below was considered and deliberately rejected. Future
proposals to add these MUST cite this section and explain why the
rationale has changed.

- **eIDAS QTSP application.** Guardtime KSI's 40+ patents + their
  existing eIDAS Trusted List slot make this both expensive and
  defensive. Treat QTSPs as backends, not become one.
- **Rewriting the substrate on Trillian / Tessera.** Premature; the
  in-tree SHA-256 chain is sufficient for v0.1 and migration to
  Tessera-as-backend is a non-breaking change at any time.
- **Building a governance dashboard / UI**. Tier D occupants have
  established sales channels; competing on UI is a loss. The CLI +
  proof bundle JSON are the v0.1 user surface.
- **Forking or supporting AGPL / SSPL / BSL**. Apache 2.0 is
  load-bearing for procurement acceptance (immudb's BSL is a
  cautionary tale of how license drift erodes adoption).
- **Direct comparison marketing**. The competitive research is
  internal-only intelligence. Public-facing material describes what
  Attestplane is, not what other products lack (the lawyer-founder
  claim-safety discipline prohibits competitive disparagement).
- **Hosted SaaS for v0.1**. M7-C1 SaaS is the existing roadmap slot;
  do not pull it forward. v0.1 ships OSS only.

## 6. Implementation tickets

Concrete tickets aligned with the Track structure. Each maps to a
single commit-sized deliverable.

| # | Track | Title | Effort | Priority |
|---|-------|-------|--------|----------|
| 27 | 5 | README + positioning realignment | 0.5 PD | P0 |
| 28 | 5 | allowed_claims / forbidden_claims updates | 0.5 PD | P0 |
| 29 | 1 | `as_in_toto_statement()` on ProofBundle | 1.5 PD | P0 |
| 30 | 1 | DSSE envelope serialization | 0.5 PD | P0 |
| 31 | 3 | `attestplane.adapters.langsmith` (Python) | 1.5 PD | P0 |
| 32 | 3 | `attestplane.adapters.langfuse` (Python) | 1.5 PD | P0 |
| 33 | 2 | `SigstoreRekorAnchor` + ADR-0006 | 3 PD | P0 |
| 34 | 4 | `governance_ingestion.schema.json` + docs | 1.5 PD | P1 |

Total: **10.5 PD**, all targetable for M5.

## 7. Risk register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| LangSmith ships hash-chain primitives before M5 | Medium | Track 3 (adapter) lands first so we have an integration story regardless |
| Sigstore community pushes back on AI-agent predicateType | Low | Use a custom URL we control (`attestplane.io/v1/...`); does not require upstream blessing |
| in-toto v1 spec changes during Track 1 implementation | Low | Pin to in-toto Statement v1 (locked since 2023-06); future v2 is a separate ADR |
| Tier D platform requests OEM exclusivity | High (if/when sales start) | Apache 2.0 license means exclusivity is structurally impossible; document the answer in `docs/integrations/governance_platforms.md` |
| User confuses "SLSA-for-AI-Agents" framing with claiming SLSA membership | Medium | Disclaimer in README: "Attestplane is independent of the OpenSSF / SLSA project; the phrasing describes architectural inspiration, not affiliation." |

## 8. Update protocol

This plan supersedes the competitive sections of the
2026-05-17 `aios_to_attestplane_migration_plan_20260517.md` only
where they conflict (which is nowhere — the AIOS migration plan does
not address competitive positioning).

Updates to this plan require an entry at the bottom of this document
with date + rationale, NOT silent edits.

### Revisions

- **2026-05-17** — Initial draft after 20-agent competitive research.
