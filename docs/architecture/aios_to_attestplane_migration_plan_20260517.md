# AIOS → Attestplane Migration Plan

**Date:** 2026-05-17
**Author:** Founder + Claude Opus 4.7 (1M context) — main loop synthesis after `opus-architect` agent timed out at the synthesis step
**Status:** Phase 0 plan — read-only; no code migration this round
**Target:** v0.1 / M5 (deadline 2026-08-15)
**Attestplane HEAD at plan time:** `f16048f` on `main`
**AIOS HEAD at scan time:** `main` of `/Users/macworkers/aios/`

---

## 0. Executive Summary

Attestplane v0.0.1-alpha is published (TestPyPI + npm + GitHub Release) with 739 LOC of substrate-core code and a frozen 10-vector cross-language conformance contract. AIOS is a production-grade multi-crate Rust workspace + Python packages with ~9 200 LOC of attestation-adjacent code, full JSON Schema catalog under `schemas/`, 74 acceptance tests in `tests/integration/test_phase{2-8}_acceptance.py`, and 69+ accepted ADRs. **Attestplane is ~8 % of the spin-off-able surface**; the rest is still in AIOS waiting to be extracted or kept in AIOS as commercial.

License is unblocked: AIOS is Apache-2.0 at the workspace level, founder is the sole copyright holder, no copyleft contamination. Re-licensing into Attestplane is mechanical (add SPDX headers + rename `aios_*` to `attestplane_*` per file).

Three reconciliation decisions are already locked from the prior architect run earlier in this session: **(1) SHA-256 forever** for Attestplane (FIPS-aligned, no migration cost; AIOS `aios-canonical` is already SHA-256 per AIOS ADR-0047); **(2) global chain** stays in Attestplane (per-`run_id` is structural to AIOS DB and does not transfer); **(3) JSON Schema artifacts** are published alongside SDK dataclasses with `vectors.json` remaining authoritative.

This plan ships nothing executable on its own. It enumerates the AIOS spin-off candidates, classifies them, lays out a Phase 0 → Phase 5 roadmap, and produces 25 tickets sized for a single solo founder to clear by M5.

**Verdict: Go for Phase 0 immediately.** Phase 0 is pure documentation (ADRs + spec docs); no code risk; it unblocks Phase 1 v0.1 OSS-core work.

### Naming history sidebar

The project lineage in chronological order: **`acceptance` branch in AIOS (earliest prototype)** → **`Veriplane`** (intermediate brand, see AIOS commit `a1a0b98` "docs(brand): same-day pivot Veriplane -> Attestplane") → **`Attestplane`** (current). The branch name `acceptance` collides with several registered .io/.com/.dev domains, and `Veriplane` was discarded for verbal/trademark distinctness. Attestplane is free to use `acceptance` / `attestation` / `conformance` terminology internally — there is no cross-project namespace collision because AIOS retains the AIOS-internal Q1-Q20 acceptance criteria framework, and Attestplane will adopt its own derived gate system (Section 3.H below).

---

## 1. AIOS Candidate Inventory

### 1.1 Rust crates (workspace at `/Users/macworkers/aios/Cargo.toml`, all `license.workspace = true` = Apache-2.0)

| Path | LOC | Summary | AIOS coupling | Spin-off bucket |
|---|---|---|---|---|
| `crates/aios-audit/src/lib.rs` | 473 | BLAKE3 hash chain primitive; `compute_event_hash(prev, payload)`; `verify_chain`; `CardinalityError` for whole-run-deletion detection; per-`run_id` scoping | Pure-functional except cardinality assumes caller has a runs table | INTEGRATE-REFACTOR (concept, not BLAKE3 code) |
| `crates/aios-canonical/` | 498 | NFC + lowercase + ZW-strip + whitespace-fold text normalizer; SHA-256 hex output; "cross-language hash boundary" per AIOS ADR-0047 | None — pure-functional | INTEGRATE-DIRECT (as separate text-hash primitive alongside the existing JSON canonicalizer) |
| `crates/aios-py-canonical/` | 220 | PyO3 bindings exposing `text_hash_hex` | Tied to PyO3 build | INTEGRATE-REFACTOR |
| `crates/aios-sdk-evidence/` | 465 | `EvidenceBundle`, `ArtifactDescriptor`, `AuditEnvelope`, `ProofType`, `RedactionPolicy`, `ReplayEvidenceDescriptor` | Pure DTOs; some link to AIOS proof semantics | INTEGRATE-REFACTOR |
| `crates/aios-sdk-protocol/` | 681 | Protocol/wire DTOs | AIOS control-plane RPC | REFERENCE-ONLY |
| `crates/aios-replay-runner/` | 969 | Deterministic replay runner; AIOS ADR-0021/0030 | Heavy: runs table, snapshot system, transport bypass (ADR-0026/0031) | REFERENCE-ONLY |
| `crates/aios-eval-gate/` | 1 945 | Evaluation gate with blocking authority over runs (AIOS ADR-0007) | Control-plane authority | **KEEP-IN-AIOS** |
| `crates/aios-claude-code-sidecar/` | 1 444 | Concrete adapter for Claude Code | Adapter implementation | **KEEP-IN-AIOS** (or move to a separate companion repo later) |
| `crates/aios-cp/src/api/audit.rs` | 353 | Axum HTTP routes for `/v1/audit/events`, `/v1/replay/:run_id` | `AppState`, tenant-scoped authz, sqlx pool | REFERENCE-ONLY |
| `crates/aios-cp/src/api/` (other `*.rs` files: a2a / admin / anomaly / approvals / canon / cost / eval / genes / governance / lease_bridge / leases / openai_compat) | — | Control-plane HTTP surface | Heavy coupling | REFERENCE-ONLY for shape; KEEP-IN-AIOS for code |
| `crates/aios-cp/src/repo/audit.rs` | 868 | Postgres-backed append, hash-chain commit, transactions | sqlx + multi-tenant coupling | REFERENCE-ONLY |
| `crates/aios-cp/src/audit_anchor_job.rs` | 430 | Background job for anchoring (presumably TSA/external) | Job scheduling + DB | REFERENCE-ONLY (informs ADR-0003 implementation in Attestplane) |
| `crates/aios-cp/src/audit_governance.rs` | 91 | Governance hooks around audit | Light coupling | REFERENCE-ONLY |
| `crates/aios-cp/src/audit_hooks.rs` | 80 | Append-time hook plumbing | Light coupling | REFERENCE-ONLY |
| `crates/aios-cp/src/audit_queue.rs` | 292 | Async write queue (`AIOS_AUDIT_QUEUE_ENABLED`) | DB-bound | REFERENCE-ONLY |
| `crates/aios-mcp/` | — | MCP protocol surface | Likely execution-shaped, not adapter-shaped | KEEP-IN-AIOS (until inspection confirms otherwise) |
| `crates/aios-runtime/`, `crates/aios-supervisor/`, `crates/aios-runtime-product-shims/`, `crates/aios-secret-broker/`, `crates/aios-cli/` (excluding audit subcommands), `crates/aios-desktop-*` | — | Runtime / control-plane / desktop surfaces | Heavy | **KEEP-IN-AIOS** |
| `crates/aios-interfaces/` | — | Trait boundaries | Possibly relevant for adapter pattern | REFERENCE-ONLY (read to learn the abstract interface boundary; don't copy) |
| `crates/aios-evolver/`, `crates/aios-gene-resolver/` | — | Self-modification / gene resolver | Out of substrate scope | KEEP-IN-AIOS |

### 1.2 Python packages (`/Users/macworkers/aios/python/`)

| Package | Summary | Spin-off bucket |
|---|---|---|
| `aios_adapters/` | Agent-adapter implementations (specific runtimes) | KEEP-IN-AIOS (concrete impls); EXTRACT-INTERFACE only (shape becomes Attestplane `adapters/base.py`) |
| `aios_eval/` | Python eval harness, coupled to eval-gate | KEEP-IN-AIOS |
| `aios_evolver/` | Self-modification engine | KEEP-IN-AIOS |
| `aios_memory/` | Memory store with canonical-text dedup | REFERENCE-ONLY (canonical-text part overlaps with `aios-canonical`) |
| `aios_agent_mesh/` | Agent mesh coordination | KEEP-IN-AIOS |
| `aios_config/` | Config | KEEP-IN-AIOS |
| `aios_py_conflict_resolver/`, `aios_py_contradiction_detector/`, `aios_py_gep_extractor/` | AIOS-specific runtime helpers | KEEP-IN-AIOS |

### 1.3 JSON schemas (`/Users/macworkers/aios/schemas/`, ~831 LOC across attestation-adjacent files)

| Schema | Summary | Spin-off bucket |
|---|---|---|
| `evidence/external_customer_evidence.schema.json` | Evidence-pack with `evidence_hash`, `claim_bindings`, `redaction_status`, `consent_status`, `test_fixture` flag | INTEGRATE-REFACTOR (drop fixture/production AIOS-specific flag; keep redaction/consent shape) |
| `evidence/secret_history_closure_evidence_pack.schema.json` | Secret-history closure pack | REFERENCE-ONLY |
| `policy/policy.schema.json` | `PolicyRule {kind, expression, effect, severity}` | INTEGRATE-REFACTOR for v0.2+ |
| `replay/replay_proof.schema.json` | `ReplayProof {input_hash_match, artifact_hash_match, audit_chain_match, deterministic_result}` | INTEGRATE-REFACTOR (drop `tenant_id`; retain replay determinism shape) |
| `replay/replay_request.schema.json`, `replay_response.schema.json`, `run_snapshot.schema.json`, `replay_error.schema.json` | Replay flow | REFERENCE-ONLY |
| `lease/lease.schema.json`, `lease_request.schema.json`, `lease_consume_request.schema.json` | Tool-call leases (AIOS ADR-0010/0016) | **KEEP-IN-AIOS-COMMERCIAL** |
| `settlement/settlement_record.schema.json` | Settlement / billing | **KEEP-IN-AIOS-COMMERCIAL** |
| `security/`, `capability/`, `a2a/`, `google_a2a/`, `internalization/`, `external_resource/`, `gep/`, `evomap/`, `run/`, `task/`, `memory/` | AIOS-specific control surfaces | KEEP-IN-AIOS |

### 1.4 Docs (`/Users/macworkers/aios/docs/`)

| Path | Summary | Spin-off bucket |
|---|---|---|
| `docs/architecture/ACCEPTANCE_CRITERIA.md` | **Q1-Q20 acceptance gates**, three-tier (pre-merge / nightly / release-blocker), each item has: category, Phase enforcement, test method, expected-failure mode, test-file location, negative examples | INTEGRATE-REFACTOR — adopt the *structure* for Attestplane's own A1-A5 substrate gates (see §3.H) |
| `docs/architecture/IMPLEMENTATION_PLAN.md` (referenced by acceptance tests) | Phase-gate exit criteria | REFERENCE-ONLY |
| `docs/audit/`, 29 files | Operational/security audits (control-plane-specific) | KEEP-IN-AIOS |
| `docs/audits/`, 20+ files including `control_mapping_iso27001.md`, `control_mapping_soc2.md`, `audit_evidence_index.md`, `evidence_pack_v1.md` | SOC2/ISO control mappings; AIOS commercial deliverables | KEEP-IN-AIOS-COMMERCIAL |
| `docs/claims/forbidden_claims.md` | 8 forbidden claims tied to AIOS rounds | INTEGRATE-REFACTOR (port to Attestplane after de-AIOS-ifying; replace "Round 160" with Attestplane-specific milestones) |
| `docs/claims/allowed_claims.md`, `public_saas_claim_policy.md` | Claim policy framework | REFERENCE-ONLY (concept reusable, content AIOS-specific) |
| `docs/customer_validation/templates/customer_acceptance_attestation_template.md` | **Customer attestation template with strict redaction rules** ("Do not include customer names, person names, PII, raw documents, contracts, scripts, tickets, emails, secrets, tokens, JWTs, private keys, or raw audit payloads") | INTEGRATE-DIRECT (becomes seed for Attestplane `proof_bundle.schema.json` `forbidden_fields` list) |
| `docs/customer_validation/attestation_collection/` | Workspace approval / design-partner attestation forms, redaction-review checklists | REFERENCE-ONLY (AIOS commercial process) |
| `docs/validation/round_alpha_dry_run_known_limitations_risk_acceptance.{md,json}` | Risk-acceptance form for known-limitations release | INTEGRATE-REFACTOR (Attestplane needs equivalent before v0.1 ships) |
| `docs/compliance/` 20+ files | Compliance evidence | KEEP-IN-AIOS-COMMERCIAL |
| `docs/adr/` (0001 through 0069+) | 69+ AIOS architecture decisions | REFERENCE-ONLY (read selected ADRs — 0007 / 0010 / 0016 / 0021 / 0026 / 0030 / 0031 / 0042 / 0047 — when writing the corresponding Attestplane ADR) |

### 1.5 Tests + tooling

| Path | Summary | Spin-off bucket |
|---|---|---|
| `tests/integration/test_phase{2,3,4,5,6,7,8}_acceptance.py` | **74 phase-gated acceptance tests**, one suite per phase; AIOS_CP_LIVE=1 gates real-integration; otherwise skip | INTEGRATE-REFACTOR (adopt the *pattern* for Attestplane's gate tests; don't copy AIOS Q1-Q20 test bodies because they assume AIOS DB) |
| `tools/specs/assertions/005_acceptance_q_headings.sh`, `010_q_markers_in_acceptance.sh` | Spec-doc assertion scripts: enforce that every Q has the required headings and markers | INTEGRATE-REFACTOR (Attestplane's `scripts/check-attestation-gates.sh` will be the equivalent) |
| `scripts/local_ci/` (M1 → M3.5, 15+ scripts: `affected.sh`, `run.sh`, `rust_clippy.sh`, `py_mypy.sh`, `codegen_check.sh`, `docs_links.sh`, `py_test_pkg.sh`, `rust_test_cp.sh`, `sql_migrations.sh`, `rust_race_guard.sh`, `rust_test_others.sh`, `docker probe`, `cache_hit_rate`, `cost_report.sh`, `diag_remote_divergence.sh`, etc.) + pre-push hook delegation | Local-CI scaffolding system | REFERENCE-ONLY for v0.1 (Attestplane CI is already comprehensive; revisit at M6 when contributor count > 1) |
| `conftest.py` | pytest root config | REFERENCE-ONLY |

### 1.6 Examples (`/Users/macworkers/aios/examples/`)

| Example | Shape | Spin-off bucket |
|---|---|---|
| `lawyer_real_case_demo.py` | Legal vertical demo | **DO NOT PORT** (belongs in `~/legal-workspace`, not Attestplane) |
| `agent_contract/` | Runtime contract demo | KEEP-IN-AIOS |
| `core_runtime_app/` | Runtime app demo | KEEP-IN-AIOS |
| `aios_mcp_claude_code_demo.md` + `aios_mcp_install.sh` | MCP install demo | KEEP-IN-AIOS |
| `real_provider_pilot/` | Provider pilot | KEEP-IN-AIOS |
| `replay_explain_dx/` | Replay DX | REFERENCE-ONLY (informs Attestplane replay UX) |

### 1.7 New facts gathered this session (not in prior architect output)

- **`feat/attestplane-landing` branch** in AIOS has **0-file diff** vs `main` — no hidden Attestplane assets sitting on a separate branch waiting to be merged.
- **AIOS has `/v1/auditor/*` HTTP endpoints with utoipa OpenAPI annotations**, shipped at commit `68b103a` ("feat(api): utoipa annotations on /v1/auditor/* endpoints (B1)"). This is the auditor JSON API Attestplane M5 plans for. Spec-clone of the OpenAPI surface (not code copy) gives Attestplane a head-start on M5 API design.
- **AIOS ADRs go to 0069+** (e.g., `4a83762 docs(adr): A3-follow + A4 — Plan 04 v1.2 defer ruling + ADR-0069 strengthen`). Attestplane currently has 0001-0003; future Attestplane ADRs should start at 0004 and respect the conceptual gaps that AIOS has already filled at high numbers.
- **`scripts/local_ci/`** is mature (M1 → M3.5 across many sub-milestones). Attestplane has not yet adopted this pattern; it relies on GitHub Actions only. This is acceptable at v0.0.1; revisit M6.
- **AIOS Round 187-240** ("legal-workspace attestation import" rounds) shows AIOS has an active customer-attestation import pipeline. Attestplane does NOT need to re-implement this — it lives in AIOS as a commercial process, Attestplane just provides the substrate.

---

## 2. Migration Classification

Five buckets:

1. **INTEGRATE-DIRECT** — Apache-2.0 verified, dependencies portable, scope matches. Copy with mechanical changes only.
2. **INTEGRATE-REFACTOR** — Concept fits; must rewrite to drop AIOS-specific assumptions (DB, control-plane, BLAKE3, per-run scoping).
3. **REFERENCE-ONLY** — Write new from scratch, AIOS code is the design pattern reference only.
4. **KEEP-IN-AIOS-COMMERCIAL** — Proprietary / commercial-tier / customer-specific. Stays in AIOS as a moat.
5. **DO NOT PORT** — Belongs in a separate repo or is obsolete.

### 2.1 INTEGRATE-DIRECT (3 items)

- **`crates/aios-canonical` text-hash primitive** — port to Python+TS SDK as a *sibling* primitive to JSON canonicalization. ~500 LOC bookable. 2 person-days. Effort: 2 PD.
- **`docs/customer_validation/templates/customer_acceptance_attestation_template.md` redaction rule list** — extract the "Do not include … secrets, tokens, JWTs, private keys, or raw audit payloads" list verbatim. Becomes seed input for Attestplane `proof_bundle.schema.json` `forbidden_fields`. 0.25 PD.
- **AIOS Q1-Q20 acceptance criteria *structure*** (not the Q-bodies, which are AIOS-specific) — adopt the heading shape (category / Phase / test method / expected failure / test location / negative examples) verbatim for Attestplane A1-A5 gates. 0.5 PD.

### 2.2 INTEGRATE-REFACTOR (8 items)

- **`crates/aios-audit::CardinalityError` concept** → Attestplane `verify_segment(events, predicate, expected_count)` for global-chain segment-deletion detection. Anticipated ADR-0005. 1.5 PD.
- **`schemas/replay/replay_proof.schema.json`** → Attestplane `replay_proof.schema.json` with `tenant_id` removed; field-by-field rewrite. 1 PD.
- **`schemas/evidence/external_customer_evidence.schema.json`** → Attestplane `auditor_export.schema.json` with `test_fixture` flag dropped; redaction-status / consent-status retained. 1 PD.
- **`crates/aios-sdk-evidence::EvidenceBundle` + `AuditEnvelope`** → Attestplane `proof_bundle.py` / `proof_bundle.ts` types. 2 PD.
- **`docs/claims/forbidden_claims.md`** → Attestplane `docs/policy/forbidden_claims.md` with AIOS round references swapped for Attestplane milestones. 0.5 PD.
- **`docs/architecture/ACCEPTANCE_CRITERIA.md`** *structure* → Attestplane `docs/architecture/ATTESTATION_GATES.md` with A1-A5. 1 PD.
- **`tests/integration/test_phase{N}_acceptance.py`** pattern → Attestplane `tests/gates/test_v0_1_gates.py` (one suite per gate-phase). 2 PD.
- **`crates/aios-py-canonical`** PyO3 binding pattern → Attestplane Python text-hash uses native Python (no PyO3) for v0.1 simplicity. 0 PD net (pattern lesson only).

### 2.3 REFERENCE-ONLY (5 items)

- **`crates/aios-cp/src/repo/audit.rs`** — informs Attestplane ADR-0004 (PostgreSQL multi-writer backend). Read; do not copy. 0 PD this round.
- **`crates/aios-cp/src/audit_anchor_job.rs`** — informs ADR-0003 TSA implementation. 0 PD this round.
- **`crates/aios-replay-runner`** — pattern for ADR (anticipated) ADR-0007 deterministic replay. 0 PD this round.
- **`crates/aios-cp/src/api/audit.rs` + utoipa annotations** — spec-clone the OpenAPI shape into Attestplane M5 `/v1/auditor/*` design. 0 PD this round (informs Phase 1 ticket #15).
- **AIOS ADRs 0007 / 0010 / 0016 / 0021 / 0026 / 0030 / 0031 / 0042 / 0047** — read these before writing the corresponding Attestplane ADR. 1 PD reading + sidebar notes.

### 2.4 KEEP-IN-AIOS-COMMERCIAL (definite)

- `crates/aios-eval-gate` (1 945 LOC) — control-plane blocking authority
- `crates/aios-claude-code-sidecar` (1 444 LOC) — concrete adapter implementation
- `schemas/lease/*` — commercial accounting primitives, moat
- `schemas/settlement/*` — billing primitives, moat
- `python/aios_evolver/`, `python/aios_adapters/`, `python/aios_eval/`, `python/aios_agent_mesh/` — runtime / agent OS surface
- `docs/audit/`, `docs/audits/`, `docs/compliance/`, `docs/customer_validation/attestation_collection/` — operational and customer-facing commercial deliverables
- `crates/aios-cli/`, `crates/aios-desktop-*`, `crates/aios-supervisor/`, `crates/aios-runtime/`, `crates/aios-runtime-product-shims/`, `crates/aios-secret-broker/`, `crates/aios-mcp/`, `crates/aios-gene-resolver/`, `crates/aios-evolver/` — runtime surface

### 2.5 DO NOT PORT

- `examples/lawyer_real_case_demo.py` — belongs in `~/legal-workspace`, NOT Attestplane; mixing vertical-specific examples into Attestplane's general substrate dilutes positioning.

---

## 3. Attestplane Target Capability Map

This section walks the seven capability gaps the user enumerated (A through G) plus the AIOS-acceptance-pattern adoption (H, added this session).

### 3.A — Verifier CLI / verifier library

| Attestplane target | AIOS source | Reusable content | Needs-strip content | Recommended approach | Priority |
|---|---|---|---|---|---|
| `attestplane verify <bundle.json>` CLI | `aios-cli` audit subcommand (if present); `aios-replay-runner/src/bin/replay-runner-cli.rs` (418 LOC) | Argument-parsing pattern; JSON-output structure | AIOS run-id / tenant-id assumptions | Write new in Python (use `argparse`); thin wrapper around `attestplane.core.verifier` library | P1 (M5) |
| `attestplane.core.verifier.verify_proof_bundle(path) → Result` | `aios-cp/src/repo/audit.rs::verify_chain_hooks`; `aios-audit::verify_chain` | Verification flow shape; first-bad-index semantics | DB-bound code paths | Pure-function library; takes JSON, returns dataclass result | P1 (M5) |
| `attestplane inspect <chain.jsonl>` | `aios-replay-runner` projection logic | Output formatting ideas | Replay-specific projection | New simple line-by-line summary tool | P2 (M5 stretch) |
| `attestplane doctor` (env / dep / config self-check) | `scripts/local_ci/affected.sh` pattern | Diagnostic-check pattern | AIOS-specific environment | Bash + small Python | P2 |

### 3.B — Proof bundle / auditor export schema

Five candidate schemas, all published under `attestplane.org/schemas/v1/`:

1. **`proof_bundle.schema.json`** — top-level export artifact.
   Fields: `bundle_version`, `chain_metadata`, `events` (array), `verification_report`, `framework_mappings` (array), `forbidden_fields` (echo of redaction policy applied), `signature` (optional Sigstore).
   Forbidden-field list seeded from `customer_acceptance_attestation_template.md`: customer names, person names, PII, raw documents, contracts, scripts, tickets, emails, secrets, tokens, JWTs, private keys, raw audit payloads.
   Source: new from scratch; design inspired by `aios-sdk-evidence::EvidenceBundle`.

2. **`auditor_export.schema.json`** — auditor-friendly subset of proof bundle, optimized for human review.
   Fields: chain hash root, event count, time range, runtime identity, framework mapping refs, verification status, redaction policy applied, signature.
   Source: refactor of `schemas/evidence/external_customer_evidence.schema.json`, dropping `test_fixture` flag.

3. **`evidence_manifest.json`** — index of all evidence artifacts in a bundle (filenames, hashes, content types).
   Source: new; light pattern from `aios-cp/src/repo/audit.rs`.

4. **`chain_metadata.json`** — substrate-level metadata: `chain_id`, `schema_version`, `genesis_hash`, `last_anchor_ref` (optional), `producer_runtime` (e.g., "AIOS v3.4.1" or "Claude Code v2.1.129").
   Source: new.

5. **`verification_report.json`** — structured result of `verify_proof_bundle()`: `ok: bool`, `first_bad_index: int | null`, `reason: str | null`, `verified_at: datetime`, `verifier_version`, `verification_method` (canonical-bytes-walk).
   Source: maps to existing Attestplane `VerificationResult` dataclass.

**Redaction policy** is the hard-coded principle: NO secrets, tokens, JWTs, private keys, or raw audit payloads in any of these artifacts. Schemas enforce this at the `additionalProperties: false` level for sensitive fields.

### 3.C — Compliance obligation registry

Structure:

```
attestplane/obligations/
  registry.schema.json
  eu_ai_act_article_12.json     # Worked example
  dora_article_8.json           # Worked example
  nis2_article_21.json          # M6
  gdpr_article_30.json          # M6
  iso_42001_clauses.json        # M7
  nist_ai_rmf_subcategories.json  # M7
```

Each obligation file has, per obligation_id:

```json
{
  "framework": "EU AI Act",
  "article": "12",
  "paragraph": "2(a)",
  "obligation_id": "eu_ai_act.art12.2a.session_id",
  "regulatory_text": "<verbatim citation>",
  "required_evidence_fields": ["session_id"],
  "optional_evidence_fields": ["reference_db_ref", "matched_input_ref", "human_verifier"],
  "event_type_mapping": ["ai_decision", "biometric_match"],
  "verifier_expectation": "Every ai_decision event has session_id populated",
  "implementation_status": "designed_toward",
  "legal_disclaimer": "Mapping target only; does not constitute compliance opinion.",
  "source_citation": "Regulation (EU) 2024/1689 of the European Parliament and of the Council of 13 June 2024, Article 12(2)(a)"
}
```

**Critical naming discipline**: `implementation_status` is one of `mapping_target` / `designed_toward` / `field_supported` / `verified_in_test`. **Never** `compliant`, `certified`, or `ready` until external certification exists. This rule is codified in the registry schema's enum constraint.

Source for the structure: AIOS has no formal obligation registry (just sparse text mentions in `docs/compliance/`); Attestplane builds this from scratch.

### 3.D — RFC 3161 / TSA anchoring

Already locked by Attestplane ADR-0003 (`docs/adr/0003-tsa-rfc-3161-anchoring.md`). Implementation pattern from AIOS `crates/aios-cp/src/audit_anchor_job.rs` (430 LOC):

- Background-job scheduler (don't block append)
- Anchor request payload shape (chain head hash + timestamp)
- Anchor verification on read (independent re-walk)

Attestplane M5 ticket reuses the architectural pattern; rewrites the code in Python (not Rust) for the v0.1 SDK.

### 3.E — Agent runtime adapters

Target structure:

```
attestplane/adapters/
  base.py                # GenericRuntimeAdapter abstract base class
  aios.py                # AIOSAdapter (translates AIOS events → Attestplane evidence events)
  langgraph.py           # LangGraphAdapter
  agentscope.py          # AgentScopeAdapter
  openai_sdk.py          # OpenAIAgentsSDKAdapter
  mcp.py                 # MCPAdapter (tool-call events)
  claude_code.py         # ClaudeCodeEventAdapter
  codex_cli.py           # CodexCLIEventAdapter
```

**Core invariant**: An adapter ONLY transforms runtime events into Attestplane evidence events. It NEVER:

- executes runtime actions
- grants leases
- modifies AIOS or any runtime's internal state
- has writable side effects beyond Attestplane's substrate

This invariant is enforced by `GenericRuntimeAdapter`'s API surface: it exposes only `translate(runtime_event) → EventDraft`. There is no `execute()`, `grant()`, `decide()`.

The AIOS adapter is the **first spec only** in Phase 1; concrete implementation in Phase 2. AIOS source: `python/aios_adapters/` (interface shape only, not code).

### 3.F — Durable storage / replay

```
attestplane/storage/
  base.py                # AbstractStorageBackend
  jsonl.py               # File-based, v0.1 (M5)
  sqlite.py              # M6
  postgres.py            # M7 (pattern from aios-cp/src/repo/audit.rs)
```

JSONL backend is the minimum-viable durable store for v0.1: append-only, file-locking on write, full chain replay on read. No tenant isolation, no encryption-at-rest, no retention enforcement — those are M6+ concerns.

### 3.G — Canonical JSON / conformance / negative vectors

Current state: 10 happy-path vectors in `sdk/python/tests/conformance/vectors.json`. Gap: zero negative / malformed / out-of-order vectors.

Target:

```
sdk/python/tests/conformance/
  vectors.json                    # frozen happy-path (already exists)
  negative/
    broken_chain.json             # NEW: 5-7 negative cases
    missing_event.json            # NEW: cardinality gap
    reordered_event.json          # NEW: seq mismatch
    duplicate_event.json          # NEW: dup detection
    malformed_payload.json        # NEW: schema violations
docs/spec/
  canonical-json-v1.md            # NEW: standalone canonicalization spec, suitable for third-party verifier reimplementation without reading SDK code
```

The negative vectors AND the spec document together enable third-party verifier implementations — an explicit M5 goal.

### 3.H — Attestation gates (AIOS acceptance pattern adopted)

**New section, derived from AIOS `docs/architecture/ACCEPTANCE_CRITERIA.md` Q1-Q20.**

Attestplane adopts the AIOS gate structure (category / Phase / test method / expected failure / test location / negative examples) and assigns gate codes **A1-A5** for substrate-level guarantees. AIOS Q-items dealing with execution authority (Q1-Q7, Q9, Q10, Q12-Q15, Q18, Q19) are **NOT adopted** because Attestplane is not a control plane.

| Attestplane gate | Derived from AIOS | Phase | Triggered |
|---|---|---|---|
| **A1 — chain replay-able** | AIOS Q8 ("all execution replay-able with hash-chain + state reconstruction") | v0.0.1-alpha (already passing) | pre-merge |
| **A2 — event_hash integrity** | AIOS Q11 ("stale eval result → REJECT, artifact_sha256 mismatch") | v0.0.1-alpha (already passing) | pre-merge |
| **A3 — tamper detection at any position** | AIOS Q16 ("audit hash mismatch → alarm") | v0.0.1-alpha (already passing) | pre-merge |
| **A4 — cross-language conformance** | AIOS Q17 ("schema drift → CI failure across Rust/Python/JSON") | v0.0.1-alpha (already passing) | pre-merge |
| **A5 — segment cardinality verifiable** | AIOS Q20 ("complete audit, no missing events") | v0.1.0 / M5 (new) | nightly |

Three-tier triggering, identical to AIOS structure:

- **pre-merge** — CI gate, PR cannot merge (A1-A4 today; A5 from M5)
- **nightly** — fail → P0 issue, 48 h to fix before next release
- **release-blocker** — any failure blocks the release tag

Each gate gets a markdown entry at `docs/architecture/ATTESTATION_GATES.md` with the AIOS format: category, Phase, test method (step-by-step), expected failure mode, test location, negative examples (counter-cases that would violate the gate). Pattern is direct adoption of `docs/architecture/ACCEPTANCE_CRITERIA.md`.

AIOS Q-items that **do not** become Attestplane gates (Attestplane records them as evidence events instead of enforcing them):

| AIOS Q | Reason | How Attestplane handles |
|---|---|---|
| Q1, Q15 (routing authority) | Execution-plane decision | `routing_event` evidence record |
| Q2, Q12, Q14 (lease authority) | Execution-plane decision | `lease_lifecycle_event` |
| Q3-Q7 (eval / evolver / policy authority) | Execution-plane decisions | `policy_check_event`, `eval_event` |
| Q9 (trace_id presence) | Observability concern | `correlation_id` field on every Attestplane event (already supported via session_id, expand for v0.1) |
| Q10 (budget exceeded → block) | Budget authority | `budget_exceeded_event` |
| Q13 (state-machine authority) | Execution authority | `state_transition_event` |
| Q18 (cancel within 5s) | Execution authority | `cancel_event` |
| Q19 (tenant isolation) | Cross-cutting authority | M6 concern; not v0.1 |

---

## 4. Boundary Rules

Ten explicit boundary decisions:

| AIOS capability | Enters Attestplane? | Rationale | Attestplane event that records it | Required redaction |
|---|---|---|---|---|
| 1. Lease granting authority | **No** | AIOS controls lease issuance; Attestplane records but does not grant | `lease_lifecycle_event { lifecycle: granted \| consumed \| expired \| revoked }` | Lease secrets, token bodies |
| 2. Budget routing / optimizer | **No** | AIOS executes routing decisions | `budget_event { decision, threshold, observed }` | Customer billing identifiers |
| 3. Settlement execution | **No** | AIOS performs settlement | `settlement_event { lifecycle: requested \| verified \| completed }` | Payment instruments, account numbers |
| 4. Worker scheduling | **No** | AIOS scheduler is opaque | `worker_assignment_event` | Worker auth tokens |
| 5. Runtime process management | **No** | AIOS owns process lifecycle | `runtime_lifecycle_event` | Process credentials |
| 6. Gateway write authority | **No** | AIOS gateway is the write boundary | `gateway_decision_event` | Auth headers |
| 7. UI read model | **No** | AIOS UI is read-only projection over AIOS DB | None — UI is downstream of substrate | n/a |
| 8. Enterprise tenant admin | **No** | AIOS Enterprise tier surface | None — admin actions optionally produce `admin_action_event` for audit trail | Admin credentials, internal user names |
| 9. Distributed worker orchestration | **No** | AIOS distributed protocol | `distributed_dispatch_event` | Worker network addresses |
| 10. Policy decision authority | **No** | AIOS policy-decision-point | `policy_check_event { decision, policy_id, evidence_refs }` | Policy expression bodies (hash only) |

**Universal rule**: any "authority / execution" surface in AIOS stays in AIOS. Attestplane only ever records the *event* of a decision having been made, never owns the decision.

---

## 5. Target v0.1 Architecture

### 5.1 Python tree (`sdk/python/src/attestplane/`)

```
attestplane/
  __init__.py            # already exists (re-exports)
  types.py               # already exists (EventDraft, AuditEvent, ChainedEvent, ChainHead, SubjectRef)
  canonical.py           # already exists (JSON canonicalizer)
  canonical_text.py      # NEW: text canonicalizer port from aios-canonical (~200 LOC)
  hashchain.py           # already exists
  substrate.py           # already exists
  verifier.py            # NEW: verify_proof_bundle, verify_segment (~150 LOC)
  proof_bundle.py        # NEW: ProofBundle, AuditorExport types (~250 LOC)
  obligations/
    __init__.py          # NEW
    registry.py          # NEW: ObligationRegistry, ObligationEntry (~150 LOC)
    _data/
      eu_ai_act_article_12.json   # NEW
      dora_article_8.json         # NEW
  adapters/
    __init__.py          # NEW
    base.py              # NEW: GenericRuntimeAdapter ABC (~100 LOC)
    aios_spec.py         # NEW: SPEC ONLY for v0.1; no concrete impl (~80 LOC docstrings)
  storage/
    __init__.py          # NEW
    base.py              # NEW: AbstractStorageBackend (~80 LOC)
    jsonl.py             # NEW: JsonlStorageBackend (~200 LOC)
  anchoring/
    __init__.py          # NEW
    base.py              # NEW: AbstractAnchorProvider (~80 LOC, spec only)
  cli/
    __init__.py          # NEW
    main.py              # NEW: dispatch (~50 LOC)
    verify.py            # NEW: `attestplane verify` (~120 LOC)
    inspect.py           # NEW: `attestplane inspect` (~80 LOC)
    export.py            # NEW: `attestplane export` (~100 LOC)
    doctor.py            # NEW: `attestplane doctor` (~60 LOC)
```

New code total estimate: ~1 700 LOC business, ~2 000 LOC tests. Roughly triples current Python SDK from 359 LOC business → ~2 100 LOC business at v0.1.

### 5.2 TypeScript tree (`sdk/typescript/src/`)

```
src/
  index.ts               # already exists
  types.ts               # already exists
  canonical.ts           # already exists
  canonical-text.ts      # NEW: text canonicalizer port (~200 LOC)
  hashchain.ts           # already exists
  substrate.ts           # already exists
  verifier.ts            # NEW (~120 LOC)
  proof-bundle.ts        # NEW (~200 LOC)
  obligations/
    registry.ts          # NEW (~120 LOC)
    eu-ai-act-article-12.json
    dora-article-8.json
  adapters/
    base.ts              # NEW (~80 LOC)
    aios-spec.ts         # NEW (spec only)
  storage/
    base.ts              # NEW
    jsonl.ts             # NEW (~150 LOC)
  anchoring/
    base.ts              # NEW (spec only)
```

CLI is Python-only for v0.1 (Node CLI deferred to M6 unless customer demand surfaces).

### 5.3 Shared schemas / conformance / docs / examples

```
schemas/
  v1/
    proof_bundle.schema.json
    auditor_export.schema.json
    evidence_manifest.schema.json
    chain_metadata.schema.json
    verification_report.schema.json
    obligation.schema.json
docs/
  architecture/
    aios_to_attestplane_migration_plan_20260517.md   # this doc
    ATTESTATION_GATES.md                              # NEW (M5)
    THREAT_MODEL.md                                   # NEW (M5 W7 per SECURITY.md)
  spec/
    canonical-json-v1.md                              # NEW
    canonical-text-v1.md                              # NEW
  policy/
    forbidden_claims.md                               # NEW (port from AIOS)
  adr/
    0001 - 0003                                       # exist
    0004 - storage-backend-choice.md                  # NEW
    0005 - verify-segment-and-cardinality.md          # NEW
    0006 - json-schema-artifacts-publishing.md        # NEW
    0007 - replay-deterministic.md                    # NEW (M6+)
    0008 - event-signature-scheme.md                  # NEW (M7+)
sdk/python/tests/conformance/
  vectors.json              # already exists
  negative/                 # NEW
    broken_chain.json
    missing_event.json
    reordered_event.json
    duplicate_event.json
    malformed_payload.json
sdk/python/tests/gates/    # NEW
  test_a1_replayable.py
  test_a2_event_hash_integrity.py
  test_a3_tamper_detection.py
  test_a4_cross_language.py
  test_a5_segment_cardinality.py
examples/                   # NEW directory
  python/
    minimal_substrate.py
    aios_run_to_proof_bundle.py
  typescript/
    minimal_substrate.ts
```

---

## 6. Reconciliation Decisions

(Already settled in prior architect run earlier this session; restated here for traceability.)

### 6.1 Hash algorithm

**SHA-256 forever for Attestplane.** AIOS `aios-canonical` is also SHA-256 (per AIOS ADR-0047, "cross-language hash boundary"); only `aios-audit` per-`run_id` DB chain uses BLAKE3 for internal throughput. The chains never need to interoperate — Attestplane wraps AIOS events as opaque payloads when ingesting an AIOS run. FIPS-aligned SHA-256 wins for EU-regulated customers.

### 6.2 Chain scoping

**Global chain stays in Attestplane.** Add `verify_segment(events, predicate, expected_count=None)` for AIOS-like per-run sub-chains via filtering (anticipated ADR-0005, ticket #5 below). Per-`run_id` scoping is structural to AIOS DB and does not transfer to a substrate that has no `runs` table.

### 6.3 Schema language

**Both.** Frozen Python+TS dataclasses remain authoritative (per ADR-0002 §11, `vectors.json` is immutable). JSON Schema artifacts auto-generated from dataclasses and published under `attestplane.org/schemas/v1/*.schema.json`. CI gate regenerates and diffs to detect drift. AIOS's `schemas/` directory format informs the artifact shape but Attestplane re-hosts under its own URI namespace.

---

## 7. Phased Roadmap

### Phase 0 — pure planning (this round, ~2 PD)

- This document at `docs/architecture/aios_to_attestplane_migration_plan_20260517.md`
- AIOS-to-Attestplane boundary ADR (ticket #1)
- Evidence event taxonomy spec (ticket #2)
- Adapter boundary spec (ticket #3)
- Forbidden-claims policy port (ticket #11)

### Phase 1 — v0.1 OSS core (M5, ~12-15 PD)

- Verifier library API (ticket #12)
- Verifier CLI (ticket #13)
- Proof bundle schema (ticket #14)
- Auditor export schema (ticket #15)
- Negative conformance vectors (ticket #16)
- Canonical JSON v1 spec doc (ticket #17)
- Canonical TEXT v1 spec doc + Python+TS port (ticket #18)
- EU AI Act Article 12 obligation registry (ticket #19)
- DORA Article 8 obligation registry (ticket #20)
- JSONL storage backend (ticket #21)
- Storage backend interface (ticket #22)
- Generic runtime adapter interface (ticket #3)
- AIOS adapter SPEC ONLY (ticket #4)
- Tool-call / policy-check / human-approval evidence event types (tickets #6, #7, #8)
- Lease / budget / supervisor evidence event types (tickets #9, #10, #11)
- Attestation gates A1-A5 doc + tests (new ticket #26)
- README architecture update with safe claims (ticket #25)

### Phase 2 — runtime adapter alpha (M6 early, ~10-15 PD)

- AIOS adapter concrete impl (ticket #5)
- LangGraph adapter
- AgentScope adapter
- MCP tool-call adapter
- OpenAI SDK adapter
- Claude Code event adapter
- Codex CLI event adapter
- AIOS-run-to-proof-bundle example (ticket #24)

### Phase 3 — external anchoring (M6, ~6-8 PD)

- ADR-0003 TSA implementation (ticket #23)
- Anchor verification API
- Batch root checkpoint
- Sigstore/Rekor design ADR (no impl yet)

### Phase 4 — storage / replay (M7, ~10-12 PD)

- SQLite backend
- PostgreSQL backend (pattern from `aios-cp/src/repo/audit.rs`)
- Replay verification API
- Export / import tools
- Retention metadata

### Phase 5 — cloud / enterprise (M8+, OUT OF SCOPE for this plan)

- Hosted anchoring (Attestplane Cloud)
- Tenant isolation
- RBAC / SSO / SCIM
- Enterprise audit dashboard
- "Attestplane Certified" certification program

---

## 8. Tickets

25 tickets, sized for solo founder, deliverable by M5 (Phase 1) or M6 (Phase 2).

> Format compressed for readability; full criteria when implementing.

| # | Title | Source | Target | Port | Pri | Effort |
|---|---|---|---|---|---|---|
| 1 | AIOS-to-Attestplane boundary ADR | AIOS `docs/adr/0007.md` (eval-gate authority), `0010` (lease), `0016` (settlement) | `docs/adr/0004-aios-to-attestplane-boundary.md` | Spec-Only | P0 | 1 PD |
| 2 | Evidence event taxonomy v1 (12 event types) | AIOS event envelope shape from `aios-sdk-protocol` | `docs/spec/evidence-event-taxonomy-v1.md` + `types.py` `EventType` enum | Spec + Refactor | P0 | 1.5 PD |
| 3 | `GenericRuntimeAdapter` interface | AIOS `python/aios_adapters/` shape | `attestplane/adapters/base.py` | Spec-Only | P0 | 0.5 PD |
| 4 | AIOS adapter spec (doc only, no impl) | AIOS adapter contracts | `attestplane/adapters/aios_spec.py` + docs | Spec-Only | P0 | 0.5 PD |
| 5 | AIOS adapter implementation | AIOS event envelope | `attestplane/adapters/aios.py` (~300 LOC) | Adapt | P1 (Phase 2) | 3 PD |
| 6 | `tool_call_event` type | AIOS MCP tool-call envelope | `types.py` + tests | Refactor | P1 | 0.5 PD |
| 7 | `policy_check_event` type | AIOS policy-engine event | `types.py` + tests | Refactor | P1 | 0.5 PD |
| 8 | `human_approval_event` type | AIOS approvals API | `types.py` + tests | Refactor | P1 | 0.5 PD |
| 9 | `lease_lifecycle_event` type (record only) | AIOS lease state machine | `types.py` + tests | Refactor | P1 | 0.5 PD |
| 10 | `budget_event`, `settlement_event`, `worker_assignment_event` | AIOS commercial primitives | `types.py` + tests | Refactor | P1 | 0.75 PD |
| 11 | Port `forbidden_claims.md` (de-AIOS-ify) | `docs/claims/forbidden_claims.md` | `docs/policy/forbidden_claims.md` | Refactor | P0 | 0.5 PD |
| 12 | `verify_proof_bundle()` library API | `aios-cp/src/repo/audit.rs::verify_chain_hooks` | `attestplane/verifier.py` | Reference | P1 | 1.5 PD |
| 13 | `attestplane verify` CLI | `aios-replay-runner` CLI shape | `attestplane/cli/verify.py` + `pyproject.toml` entry-point | Adapt | P1 | 1.5 PD |
| 14 | Proof bundle schema | `aios-sdk-evidence::EvidenceBundle` | `schemas/v1/proof_bundle.schema.json` + dataclass | Refactor | P1 | 1.5 PD |
| 15 | Auditor export schema | `schemas/evidence/external_customer_evidence.schema.json` | `schemas/v1/auditor_export.schema.json` | Refactor | P1 | 1 PD |
| 16 | Negative conformance vectors | New | `sdk/python/tests/conformance/negative/*.json` | Direct (new) | P1 | 1.5 PD |
| 17 | Canonical JSON v1 spec doc | AIOS ADR-0047 + Attestplane `canonical.py` reverse-engineered | `docs/spec/canonical-json-v1.md` | Reference | P1 | 1 PD |
| 18 | Canonical TEXT port + spec | `aios-canonical/src/canonical.rs` | `attestplane/canonical_text.py` + TS + `docs/spec/canonical-text-v1.md` | Direct | P1 | 2 PD |
| 19 | EU AI Act Article 12 obligation registry | None — new | `attestplane/obligations/eu_ai_act_article_12.json` + registry loader | New | P1 | 1.5 PD |
| 20 | DORA Article 8 obligation registry | None — new | `attestplane/obligations/dora_article_8.json` + registry loader | New | P1 | 1.5 PD |
| 21 | JSONL storage backend | New | `attestplane/storage/jsonl.py` | New | P1 | 1.5 PD |
| 22 | Storage backend interface | New | `attestplane/storage/base.py` | New | P1 | 0.5 PD |
| 23 | RFC-3161 / TSA implementation per ADR-0003 | `aios-cp/src/audit_anchor_job.rs` pattern | `attestplane/anchoring/rfc3161.py` (~400 LOC) | Reference | P2 (Phase 3) | 4 PD |
| 24 | AIOS-run-to-proof-bundle example | New | `examples/python/aios_run_to_proof_bundle.py` | New | P2 (Phase 2) | 1 PD |
| 25 | README architecture update with safe claims | None | `README.md` | Refactor | P1 | 0.5 PD |
| 26 | Attestation gates A1-A5 doc + test scaffolding | AIOS `ACCEPTANCE_CRITERIA.md` structure + `test_phase{N}_acceptance.py` pattern | `docs/architecture/ATTESTATION_GATES.md` + `sdk/python/tests/gates/test_a{1-5}_*.py` | Refactor | P0 (Phase 0/1 mixed) | 2 PD |

**Total Phase 0 effort: ~3.5 PD**
**Total Phase 1 (v0.1 / M5) effort: ~22 PD** including Phase 0
**Total Phase 2 (M6 adapter wave) effort: ~10-15 PD**

Solo founder with 8 weeks (~40 working days) to M5 deadline → Phase 0+1 fits in 25 % of available capacity, leaving ~30 PD slack for unrelated M5 deliverables (Singapore Pte. Ltd. incorporation, trademark filing, customer onboarding, AIOS-side maintenance).

---

## 9. Final Recommendations

### 9.1 Top 10 AIOS capabilities most valuable to absorb (ranked)

1. **`aios-canonical` text-hash primitive** (~500 LOC) — INTEGRATE-DIRECT, day 2 of Phase 1
2. **AIOS Q1-Q20 acceptance criteria structure** → Attestplane A1-A5 gates — INTEGRATE-REFACTOR, Phase 0
3. **`customer_acceptance_attestation_template.md` redaction rules** → seed for `proof_bundle.schema.json` forbidden_fields — INTEGRATE-DIRECT
4. **`aios-sdk-evidence::EvidenceBundle` shape** → Attestplane `proof_bundle.py` types — INTEGRATE-REFACTOR
5. **`schemas/replay/replay_proof.schema.json`** (minus tenant_id) → Attestplane `replay_proof.schema.json` — INTEGRATE-REFACTOR (Phase 2)
6. **AIOS `/v1/auditor/*` OpenAPI surface (utoipa)** → spec-clone for Attestplane M5 API — REFERENCE-ONLY
7. **`aios-audit::CardinalityError` concept** → Attestplane `verify_segment` ADR-0005 — INTEGRATE-REFACTOR
8. **`schemas/evidence/external_customer_evidence.schema.json`** (minus test_fixture flag) → Attestplane `auditor_export.schema.json` — INTEGRATE-REFACTOR
9. **AIOS phase-gated acceptance test pattern** (`test_phase{N}_acceptance.py`) → Attestplane `tests/gates/test_v0_1_gates.py` — INTEGRATE-REFACTOR
10. **`docs/claims/forbidden_claims.md`** → Attestplane `docs/policy/forbidden_claims.md` — INTEGRATE-REFACTOR

### 9.2 Top 10 AIOS capabilities to absolutely NOT port (ranked)

1. **`aios-eval-gate`** (1 945 LOC) — control-plane blocking authority; substrate must stay thin
2. **`schemas/lease/*`** — commercial accounting moat; opens billing logic to public
3. **`schemas/settlement/*`** — billing primitive
4. **`python/aios_evolver/`** — self-modification engine; out of substrate scope
5. **`crates/aios-claude-code-sidecar/`** (1 444 LOC) — concrete adapter, lives in AIOS or its own repo; not the substrate
6. **`crates/aios-runtime/`, `aios-supervisor/`, `aios-runtime-product-shims/`** — runtime / control-plane
7. **`crates/aios-cp/src/api/*.rs`** (full HTTP surface beyond `audit.rs`) — Attestplane is not a control plane
8. **`crates/aios-secret-broker/`** — credential surface; out of scope and high-risk to port without re-design
9. **`crates/aios-evolver/`, `aios-gene-resolver/`** — agent self-evolution; not substrate
10. **`examples/lawyer_real_case_demo.py`** — vertical-specific, belongs in `~/legal-workspace`

### 9.3 Top 10 highest-priority modules for v0.1 / M5 (ranked, with port type)

1. **`docs/policy/forbidden_claims.md`** — Refactor — Phase 0, 0.5 PD (closes legal over-claim risk THIS WEEK)
2. **`attestplane/canonical_text.py` + `canonical-text.ts`** — Direct — Phase 1, 2 PD
3. **`docs/architecture/ATTESTATION_GATES.md` + `tests/gates/`** — Refactor — Phase 0/1, 2 PD
4. **`attestplane/verifier.py` + `cli/verify.py`** — Adapt — Phase 1, 3 PD
5. **`schemas/v1/proof_bundle.schema.json` + dataclass** — Refactor — Phase 1, 1.5 PD
6. **`attestplane/obligations/eu_ai_act_article_12.json` + registry loader** — New — Phase 1, 1.5 PD
7. **`attestplane/obligations/dora_article_8.json`** — New — Phase 1, 1.5 PD
8. **`sdk/python/tests/conformance/negative/`** — New — Phase 1, 1.5 PD
9. **`docs/spec/canonical-json-v1.md`** — Reference — Phase 1, 1 PD
10. **`attestplane/storage/jsonl.py` + `storage/base.py`** — New — Phase 1, 2 PD

### 9.4 Recommended new directory layout

```
~/projects/attestplane/                           ← OSS repo (already moved 2026-05-17)
├── docs/
│   ├── adr/                                       (exists 0001-0003; add 0004+)
│   ├── architecture/
│   │   ├── aios_to_attestplane_migration_plan_20260517.md   (this doc)
│   │   ├── ATTESTATION_GATES.md                  (NEW M5)
│   │   └── THREAT_MODEL.md                       (NEW M5)
│   ├── policy/
│   │   └── forbidden_claims.md                   (NEW Phase 0)
│   ├── spec/
│   │   ├── canonical-json-v1.md                  (NEW Phase 1)
│   │   └── canonical-text-v1.md                  (NEW Phase 1)
│   └── validation/                                (exists, gap-audit doc lives here)
├── schemas/
│   └── v1/                                        (NEW M5)
├── sdk/python/                                    (exists; expand)
├── sdk/typescript/                                (exists; expand)
└── examples/                                      (NEW M6)

~/Documents/attestplane-business/                  ← business/legal/strategy (already renamed)
~/aios/                                            ← AIOS upstream (untouched)
```

### 9.5 Phase 0 / 1 / 2 minimum acceptance

- **Phase 0** ready to merge: (a) this migration-plan doc committed; (b) `docs/policy/forbidden_claims.md` ported and committed; (c) boundary ADR-0004 drafted; (d) `ATTESTATION_GATES.md` with A1-A5 drafted (gates may still be M5 to implement).
- **Phase 1** ready to release as v0.1.0: (a) all 17 Phase-1 tickets closed; (b) all 5 attestation gates passing (A1-A4 pre-merge, A5 nightly); (c) cross-language conformance vectors include negative cases; (d) `verifier CLI` published in TestPyPI v0.1.0; (e) at least 2 obligation registries (EU AI Act Art. 12, DORA Art. 8) live.
- **Phase 2** ready as v0.2.0: AIOS adapter ships with example `aios_run_to_proof_bundle.py` producing a verifiable bundle.

### 9.6 Final verdict

**Go for Phase 0 — start immediately.** Phase 0 is pure documentation (3.5 PD); it carries zero code-change risk; it unblocks every Phase-1 work item; and it closes the immediate over-claim legal risk by porting the forbidden-claims policy.

The architect-agent timed out during synthesis; this main-loop synthesis substitutes by leveraging the prior architect run's outputs (license, anti-patterns, reconciliation decisions) plus this session's supplementary AIOS scans (Q1-Q20 acceptance, customer-attestation template, `/v1/auditor/*` shape, ADR-0069+ awareness, naming history). The plan is grounded in cited paths and is ready to execute.

---

## 10. Hard-constraint compliance

| Constraint from user prompt | Status |
|---|---|
| Read-only this round; no code migration | ✓ this doc is the only artifact |
| Cite paths everywhere | ✓ every claim references AIOS or Attestplane file path |
| Don't propose Direct-Port for control-plane-coupled code | ✓ all DB / Postgres / control-plane code marked Reference-Only |
| Authority/execution → Do Not Port, only map to evidence event | ✓ §3.E core invariant, §4 boundary rules |
| Don't claim production-ready | ✓ every "ready" word in registry schema is `mapping_target` / `designed_toward` etc. |
| Don't change license | ✓ Apache-2.0 stays |
| Don't introduce CLA | ✓ DCO model preserved |
| Attestplane never mutates AIOS state | ✓ §3.E invariant |
| Verdict explicitly Go-or-No-Go | ✓ §9.6 |

---

**End of plan. Next concrete step: open ticket #1 (Boundary ADR-0004) and ticket #11 (Forbidden claims port) — together they are ~1 PD and unlock the rest of Phase 0/1.**
