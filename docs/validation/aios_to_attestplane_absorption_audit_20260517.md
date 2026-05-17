<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# AIOS → Attestplane Absorption Audit — 2026-05-17

> **Status**: read-only architecture audit. No code in this report.
> **Auditor**: `opus-architect` (2-pass: structural → source-grounded delta).
> **Locked predecessors**: [ADR-0001](../adr/0001-use-apache-2-0-license.md),
> [ADR-0002](../adr/0002-substrate-data-model-and-hash-chain-v0.md),
> [ADR-0003](../adr/0003-tsa-rfc-3161-anchoring.md),
> [ADR-0004](../adr/0004-aios-to-attestplane-boundary.md) (universal rule),
> [ADR-0005](../adr/0005-event-signing-scheme.md),
> [ADR-0008](../adr/0008-evidence-event-taxonomy-v1.md),
> [`aios_to_attestplane_migration_plan_20260517.md`](../architecture/aios_to_attestplane_migration_plan_20260517.md),
> [`attestplane_full_gap_audit_20260517.md`](attestplane_full_gap_audit_20260517.md),
> **Relationship between Attestplane and AIOS (founder-authoritative, 2026-05-17)**: Attestplane was **extracted from AIOS** as the open-source compliance / substrate module. AIOS remains a proprietary commercial product (the in-tree `~/aios/LICENSE` Apache-2.0 text reflects an early phase and is non-operative for the commercial product). **The founder owns copyright to both repositories.** Relicensing AIOS code to Apache-2.0 as part of an extraction into Attestplane is therefore *legally* available to the founder at any time. The constraint on what may be extracted is **strategic / business**, not third-party licensing.
>
> Founder MEMORY rule: **AIOS commercial differentiator surface is not extracted into Attestplane** — Control Plane / authority / orchestration / scheduler / billing stay in commercial AIOS.

## Executive summary

AIOS lives at `~/aios/`, ~225 K Rust LOC, **proprietary commercial
product**. Attestplane is the Apache-2.0 OSS extraction (substrate +
evidence + signing + anchoring + verifier surface). The two dominant
AIOS crates (`aios-cp` 108 K, `aios-runtime` 67 K) are full
execution-plane and stay in the commercial parent.

**The constraint on AIOS → Attestplane extraction is strategic, not
legal.** The founder owns both copyrights and may extract any AIOS
file into Apache-2.0 Attestplane at any time. The strategic line —
what *should* be extracted vs. what *should* stay as commercial
differentiator — is what this audit codifies. It is reinforced by
two scope-discipline patterns:

1. **What stays in commercial AIOS**: Control Plane authority, runtime
   orchestration, worker scheduling, budget allocation, lease issuance,
   settlement execution, gateway command execution, multi-tenant authz,
   secret store, evolver, eval-gate, replay execution runtime, SaaS
   product logic (§ C 17-row REDLINE table below).
2. **What may be extracted via this ADR's Mode A.6**: evidence-event
   payload schemas (lease lifecycle, policy check, replay outcome,
   worker observation, gateway decision, runtime action). Each
   extraction goes through schema-shape re-issue under Attestplane
   `$id` with explicit drop-list documenting which authority-bearing
   fields are deliberately not extracted.

Because the founder owns both copyrights, every A-class extraction is
legitimately relicensed to Apache-2.0; Attestplane contains no
third-party proprietary code. The absorption discipline (Mode A.1/A.2
independent convergence; Mode A.3 taxonomy with redaction; Mode A.6
schema-shape re-issue) exists to prevent **scope drift** — not to
satisfy a legal licence question.

**Strategic timing (informing extraction priority)**: EU AI Act
(Regulation 2024/1689) high-risk-system obligations take operational
effect August 2026 — eight weeks from this audit's date. Article 12
"automatic recording of events" is the substrate-grade audit
obligation the extraction targets. The compliance-substrate
primitives (canonical hashing, hash chain, sidecar evidence,
signing, anchoring, proof bundles) are extracted *first* because
they are the load-bearing surface for that obligation. Extraction
priority for the next Phase 2 batch (A.7 / A.8 / A.9) follows the
same logic: lease-lifecycle, policy-decision, and replay-outcome
shapes are the EU AI Act Article 12 + DORA Article 8 evidence
shapes that compliance procurement cycles will look for in OSS form
ahead of the August deadline. See ADR-0009 § "Strategic context"
for the full why-now rationale.

Net result of this audit:

| Category | Count | Posture |
|---|---:|---|
| **A — Direct absorption (schema-shape / doc-only)** | 8 entries (A.1–A.5 original + A.6 new category + A.7–A.10 promotions) | doc + schema, **no Rust code copied** |
| **B — Concept-only** | 6 entries kept (B.2/B.3/B.5/B.7/B.9/B.10) | substrate primitives originally proposed |
| **C — REDLINE (must NOT enter)** | 17 original + 4 new | structural redlines + 4 source-grounded additions |
| **D — Substrate gaps** | 9 questions answered | 3 blocking, 4 nice-to-have, 2 future ADR |
| **F — New invariants** | 5 (INV-NEW-1…5) | grafted into ADR-0009 |
| **F — New risks** | 4 (R-NEW-1…4) | top: license-MEMORY illusion (HIGH) |

The MEMORY boundary is the ceiling; Apache-2.0 is the floor. Every
A-class deliverable is **either independent convergence (zero code/schema
flow) or schema-shape re-issue under Attestplane `$id`** — never a
verbatim AIOS file copy.

---

## A — Directly absorbable (schema-shape / doc-only)

### A.1 — `canonical-json-v1` → INDEPENDENT CONVERGENCE (reclassified)

| Item | Detail |
|---|---|
| AIOS source observed | `~/aios/crates/aios-audit/src/lib.rs` lines 26–46 (21-line `sort_value` recursion) |
| Attestplane status | Already shipped: `docs/spec/canonical-json-v1.md` + `sdk/python/src/attestplane/canonical.py` + `sdk/typescript/src/canonical.ts` + `vectors.json` |
| Final classification | **Independent convergence**. No code or schema flow. Attestplane's spec is the source of truth in this repo; AIOS independently arrives at the same algorithm. |
| Py/TS impact | none (already shipped) |
| Conformance vector | `vectors.json` (already frozen, do not modify) |
| Migration risk | low |
| Anti-scope-creep gate | absorption map MD will label this row as "independent convergence, no code/schema flow." |

### A.2 — `canonical-text-v1` → INDEPENDENT CONVERGENCE (reclassified)

| Item | Detail |
|---|---|
| AIOS source observed | `~/aios/crates/aios-canonical/src/canonical.rs` (218 LOC, normalise + hash); NOT inspected line-by-line (NEEDS-VERIFY) |
| Attestplane status | Already shipped: `docs/spec/canonical-text-v1.md` + `canonical_text.{py,ts}` + `text_vectors.json` (12 frozen vectors) |
| Final classification | **Independent convergence**. Attestplane's `canonical-text-v1` spec predates source visibility check. |
| Anti-scope-creep gate | "Canonical-text is a payload-side utility. MUST NOT be called from `substrate.append()` or `canonicalize(ChainedEvent)`." |
| Migration risk | low |

### A.3 — Evidence event taxonomy strings (with proof-type redaction)

| Item | Detail |
|---|---|
| AIOS source observed | `~/aios/crates/aios-sdk-evidence/src/proof.rs` lines 4–30 — 11 `ProofType` variants |
| Attestplane status | Already shipped: 12 canonical `event_type` strings in `event_types.py/ts` per ADR-0008 |
| Source-grounded redaction | If A.3 ever imports proof-type taxonomy from AIOS, **drop** `LiveRuntimeInvariant` and `ProductionLive` — they encode authority assertions ("the runtime asserts this is production live"). Keep substrate-meaningful subset: `SchemaBacked`, `FixtureBacked`, `Replay`, `DeterministicReplay`, `DryRun`. |
| Py/TS impact | adapter-side enum allowlist; substrate enum unchanged |
| Migration risk | low |
| Anti-scope-creep gate | INV-NEW-4: adapter-side `Literal[...]` / pydantic enum with restricted membership — rejects the two dropped values at ingress. |

### A.4 — Acceptance-criteria heading skeleton (doc structure only)

Unchanged from pass-1. Already absorbed at `docs/architecture/ATTESTATION_GATES.md` (A1–A5). Q-bodies stay in AIOS.

### A.5 — Conformance test phase-gate layout (file-naming pattern only)

Unchanged from pass-1. Already absorbed at `sdk/python/tests/gates/test_a{1-5}_*.py` (planned). No AIOS DB skip-markers brought over.

### A.6 — **Schema-shape absorption** (new absorption category)

Created in pass-2 to formalise how schema-shape work differs from primitives (A.1/A.2) and string-glossaries (A.3).

**Definition**: an absorption mode in which Attestplane takes the
*structural shape* (field names, types, required/optional, enum sets)
of an AIOS-side declarative artefact (a `.rs` `serde` DTO or a
`.schema.json` file) and:

1. **Re-issues** the schema under `https://attestplane.io/schemas/v1/...` `$id` — never `$ref`-s an AIOS `$id`.
2. **Applies redaction policy** (ADR-0004 § 2 column 3): every authority-bearing field becomes a hash field or is dropped.
3. **Assigns an Attestplane-local `<event_kind>_schema_version`** independent of any AIOS version.
4. **Documents provenance** in the absorption map MD with source path + dropped-field list.

**Governing invariants** (encoded into ADR-0009 F.2):
- The Attestplane schema MUST NOT `$ref` an AIOS `$id`.
- Every field whose source counterpart carries authority semantics MUST be replaced by a hash field or dropped entirely.
- The provenance MUST appear in `docs/architecture/aios_absorption_map.md` with three rows per absorbed shape (source path / shape absorbed / fields dropped).

**License-vs-MEMORY posture**: Apache-2.0 *permits* verbatim schema copy. MEMORY *forbids* it for AIOS specifically — verbatim copy would imply dependency direction Attestplane → AIOS schema authority (violates ADR-0004 § 4). Hence schema-shape absorption is a **controlled re-issue, not a copy**.

### A.7 — `lease_lifecycle_event` field set (promoted from B.1)

| Item | Detail |
|---|---|
| AIOS sources | `~/aios/crates/aios-sdk-evidence/src/artifact.rs` lines 28–43 (`ArtifactDescriptor`); `~/aios/schemas/lease/lease.schema.json` lines 1–84 |
| Shape absorbed | `(lease_id_hash, tenant_id_ref, step_id_ref, run_id_ref, artifact_hash_ref, lifecycle, observed_at, reason_code)` |
| Explicitly NOT absorbed | `capability_required`, `budget_cap`, `signature` (all authority-issuing per ADR-0004 § 1); HMAC canonical-payload construction (lives in `aios-cp/src/lease/issue.rs`); the lease-issuance verb itself |
| Attestplane `$id` | `https://attestplane.io/schemas/v1/lease_lifecycle_event.schema.json` |
| `schema_version` | `lease_event_schema_version = 1` |
| Py/TS impact | both — Python `TypedDict` in `event_types.py` payload; TS interface in `event_types.ts`; **no change to `ChainedEvent`** |
| Conformance vector | new file `sdk/python/tests/conformance/lease_lifecycle_event_vectors.json` — NEVER modifies `vectors.json` |
| Migration risk | low (schema-only; ADR-0004 § 2 case #1 already authorises the event_type) |
| Anti-scope-creep gate | Forbid any field name matching `^(signature|token|key|budget|capability|grant|revoke|allocate)$` at schema-validation time. |

### A.8 — `policy_check_event` field set (promoted from B.4)

| Item | Detail |
|---|---|
| AIOS sources | `~/aios/schemas/policy/policy.schema.json` lines 1–50 (`Policy` + `PolicyRule`) |
| Shape absorbed | `(policy_id, policy_version, rule_id, kind, effect, severity, expression_hash, evidence_refs[])` |
| Explicitly NOT absorbed | `expression` body (kept as hash only — ADR-0004 § 2 case #10 already mandates this); `PolicyUpdateCandidate` mechanics (diff / eval_proof_ref / RFC 6902 patch — authority lifecycle, stays in AIOS); `kind` enum values like `EVAL_REQUIRED` (if no Attestplane-side eval-gate, leave enum open / pass-through) |
| Attestplane `$id` | `https://attestplane.io/schemas/v1/policy_check_event.schema.json` |
| `schema_version` | `policy_event_schema_version = 1` |
| Py/TS impact | both — payload schema only; `ChainedEvent` unchanged |
| Conformance vector | new file `policy_check_event_vectors.json` |
| Migration risk | low |
| Anti-scope-creep gate | reject any payload containing `expression` (only `expression_hash` permitted); reject decision values outside `{allow, deny, abstain}`. |

### A.9 — `replay_event` field set (promoted from B.6)

| Item | Detail |
|---|---|
| AIOS sources | `~/aios/crates/aios-sdk-evidence/src/replay.rs` lines 7–21 (`ReplayEvidenceDescriptor`); `~/aios/schemas/replay/replay_proof.schema.json` lines 1–40 (`ReplayProof`) |
| Shape absorbed | `(replay_run_id, original_run_id, snapshot_id, artifact_hash, audit_hash, input_hash_match: bool, artifact_hash_match: bool, audit_chain_match: bool, deterministic_result: bool, diff_summary_hash, created_at)` |
| Explicitly NOT absorbed | The execution of replay (running the workload again — lives in `aios-replay-runner`, REDLINE); `proof_type` authority variants (see A.3 redaction list) |
| Attestplane `$id` | `https://attestplane.io/schemas/v1/replay_event.schema.json` |
| `schema_version` | `replay_event_schema_version = 1` |
| Py/TS impact | both — payload schema + verifier predicate `verify_replay_manifest(manifest, observed_chain)` (read-only walk, never replays) |
| Conformance vector | new file `replay_event_vectors.json` |
| Migration risk | low (verifier is pure-functional; replay execution stays in AIOS) |
| Anti-scope-creep gate | absorption map MD entry must read "Attestplane never re-executes the workload; the verifier checks that **already-observed** boolean fields are consistent." |

### A.10 — `AuditEnvelope` shape note (promoted from B.8, scope-narrowed)

| Item | Detail |
|---|---|
| AIOS sources | `~/aios/crates/aios-sdk-evidence/src/audit.rs` lines 28–45 (`AuditEnvelope`) — **NOT** `aios-sdk-protocol::envelope.rs` `RequestEnvelope<T>` |
| Shape absorbed | The 4-tuple `(tenant_id, run_id, step_id, audit_hash)` as a *cross-runtime import-shape hint* in `docs/spec/evidence-event-taxonomy-v1.md` |
| Explicitly NOT absorbed | `RequestEnvelope<T>` transport (request/response, protocol-version negotiation, idempotency, causation) — that is execution-plane glue per ADR-0004 § 1; → REDLINE C.new-3 |
| Attestplane `$id` | n/a — this is a spec-doc shape note, not a new JSON Schema file |
| `schema_version` | n/a |
| Py/TS impact | spec doc only |
| Conformance vector | none |
| Migration risk | low |
| Anti-scope-creep gate | doc must explicitly contrast `aios-sdk-evidence/src/audit.rs` (absorbed) vs `aios-sdk-protocol/src/envelope.rs` (REDLINE). |

---

## B — Concept-only (substrate primitive, not code)

The architect's original B.1/B.4/B.6/B.8 promoted to A.7/A.8/A.9/A.10
above. Remaining B-class items keep their original posture:

### B.2 — no-lease-no-execute → `requires_lease_proof()` verifier predicate
- **AIOS semantics**: runtime refuses tool calls without lease (enforcement).
- **Why not portable**: enforcement = authority.
- **Substrate primitive**: read-only verifier predicate `requires_lease_proof(events, claim) -> VerificationResult`. Walks chain segment; never appends; never mutates. Returns `ok / first_bad_index / reason_code`.
- **Attestplane name**: `attestplane.verifier.requires_lease_proof`
- **Minimal interface**: function signature only; no class state.
- **Tests**: unit (positive: matching `lease_lifecycle_event {lifecycle: granted}` precedes target `tool_call_event`); unit (negative: `first_bad_index` points at unprotected call); cross-language reason_code byte stability.

### B.3 — verify-before-settle → `SettlementPrecondition` claim type
- **AIOS semantics**: settlement engine demands "verify pass + lease consumed" before settling.
- **Why not portable**: settle = authority over money/state.
- **Substrate primitive**: a claim schema "this chain segment satisfies settlement preconditions"; verifier emits yes/no/reason_code; **does not execute settlement**.
- **Attestplane name**: `schemas/v1/settlement_precondition_claim.schema.json` + `attestplane.verifier.check_settlement_precondition`
- **Tests**: unit + fixture (segment with `settlement_event {requested}` but no preceding `lease_lifecycle_event {consumed}` → `first_bad_index` points at the settlement request).

### B.5 — Governance timeline → deterministic projection
- **AIOS semantics**: governance system produces a chronology.
- **Why not portable**: governance system = decision-making body.
- **Substrate primitive**: a pure `filter` over chain by `event_type ∈ {policy_check_event, admin_action_event, lease_lifecycle_event}`. No interpretation, no scoring.
- **Attestplane name**: `attestplane.projections.governance_timeline(chain) -> list[ChainedEvent]`
- **Tests**: unit + Py/TS byte-equal output.

### B.7 — Worker heartbeat → `WorkerObservationRecord`
- **AIOS semantics**: worker manager consumes heartbeats, schedules.
- **Why not portable**: manager = scheduler authority.
- **Substrate primitive**: event-only record of "I am alive at T"; substrate does not interpret.
- **Attestplane name**: `schemas/v1/worker_observation_event.schema.json` — fields `(worker_id_hash, observed_at, worker_state ∈ {starting, healthy, draining, stopped})`. **No** network address; **no** auth token.
- **Tests**: unit + forbidden_fields gate.

### B.9 — Idempotency / correlation / causation IDs → `ProofBundle` metadata
- **Substrate primitive**: three optional `ProofBundle`-level fields (`bundle_correlation_id`, `bundle_causation_refs: list[str]`, `bundle_idempotency_key`). **NOT on `ChainedEvent`** (frozen).
- **Tests**: schema validation + DAG-causation fixture.

### B.10 — Read model projection → deterministic projection spec
- **Substrate primitive**: a projection-spec language (filter / sort / group / select), implemented as pure function `project(chain, spec) -> JSON`. **Not a query engine, no indices, no cache, no push.**
- **Attestplane name**: `attestplane.projections.project` + `docs/spec/projection-spec-v1.md`
- **Tests**: unit + Py/TS byte-equal output for same `(chain, spec)`.

---

## C — REDLINES (MUST NOT enter Attestplane)

### Original list (re-confirmed by source visibility)

| # | AIOS module / capability | Why REDLINE | If user needs it |
|---|---|---|---|
| C.1 | Control Plane authority / command dispatch (`aios-cp` 108 K LOC) | dispatch = execution; command = authority | (b) AIOS commercial |
| C.2 | Worker scheduling / placement (`aios-supervisor` 2 818 LOC) | scheduler = authority | (b) AIOS / (a) K8s |
| C.3 | Budget allocator / quota enforcement | allocator / enforce = authority | (b) AIOS commercial |
| C.4 | Runtime orchestration loop (`aios-runtime` 67 K LOC) | orchestration = execution | (b) AIOS / (c) LangGraph |
| C.5 | UI state management | ADR-0004 § 2 #7 already forbids | (b) AIOS UI / (a) self-built |
| C.6 | Multi-tenant membership / org model | cross-cutting authority | (b) AIOS Enterprise |
| C.7 | AuthZ service / RBAC engine | grant = authority | (b) AIOS / (c) OPA / Cedar |
| C.8 | Gateway command execution (the *executor*) | dispatch = execution; ADR-0004 § 2 #6 records-only | (b) AIOS gateway |
| C.9 | SaaS product logic | conflicts with Apache-2.0 substrate market split | (b) Attestplane Cloud (future) |
| C.10 | Distributed worker execution protocol | protocol = transport = I/O; ADR-0004 § 2 #9 | (b) AIOS distributed runtime |
| C.11 | Secret store | "store secrets" violates forbidden_fields + GDPR Art.4(5) | (a) Vault / KMS / GCP SM |
| C.12 | KMS / key lifecycle authority | ADR-0005 permits access, NOT authority | (a) external KMS |
| C.13 | `aios-eval-gate` (1 945 LOC) | blocking authority over runs | (b) AIOS commercial |
| C.14 | `aios-evolver` / `aios-gene-resolver` | self-modification engine | (b) AIOS commercial |
| C.15 | `aios-claude-code-sidecar` concrete impl | per MEMORY: AIOS adapter impl stays in AIOS commercial | (b) AIOS / separate repo |
| C.16 | `schemas/lease/*` + `schemas/settlement/*` **complete** schemas (with request/consume/billing detail) | commercial billing primitives | (b) AIOS commercial |
| C.17 | `examples/lawyer_real_case_demo.py` | vertical demo; belongs in `~/legal-workspace` | move to legal-workspace |
| **C.18** | **Migration-plan ticket #5 — `AIOSAdapter` concrete implementation** | concrete AIOS-runtime translator IS the open-core differentiator; per `memory/feedback_attestplane_aios_boundary.md` permanently out of scope for Attestplane OSS | (b) AIOS commercial repo |
| **C.19** | **Migration-plan ticket #24 — AIOS-run-to-proof-bundle example** | depends on ticket #5; even a "synthetic AIOS-shaped" example crosses the boundary by name/framing/intent | (b) AIOS commercial repo demos; generic any-runtime example may exist but must not be AIOS-named |

### Source-grounded REDLINE additions (pass-2)

| # | AIOS source | Why REDLINE |
|---|---|---|
| **C.new-1** | `~/aios/crates/aios-canonical/src/dedup.rs` (72 LOC; C6+C7 dedup matrix) | Decides `Skip / Update / NeedsReview / Insert` against an existing `ACTIVE memory item`. Substrate has no concept of mutable active memory; pulling this in imports a state-keeping primitive Attestplane has no business owning. ADR-0004 § 1 lists "mutating remote state" as Execution. |
| **C.new-2** | `~/aios/crates/aios-audit/src/lib.rs` cardinality + chain-error layer (473 LOC; `verify_task_run_cardinality`, `CardinalityFinding`, `check_audit_vs_actual`, `check_orphan_proof`) | Hardwired to AIOS-specific tables (`audit_events`, `runs`, `tasks`, `replay_proofs`). The 9-line `compute_event_hash` algorithm is independent convergence (Attestplane uses its own per ADR-0002 §2); the cardinality/orphan layer is REDLINE. |
| **C.new-3** | `~/aios/crates/aios-sdk-protocol/src/envelope.rs` `RequestEnvelope<T>` lines 47–108 | Protocol-version negotiation + idempotency + causation tracking = transport semantics for a request/response runtime. ADR-0004 § 1 places "dispatching to a worker, calling a tool" inside Execution. A.10 absorbs the audit half (`aios-sdk-evidence/src/audit.rs`); the transport half stays REDLINE. |
| **C.new-4** | `~/aios/crates/aios-canonical/src/canonical.rs` (218 LOC) — NEEDS-VERIFY | If pure string normalisation matching `canonical-text-v1.md`, treat as independent convergence (A.2). If it has hooks into AIOS-side memory entities, REDLINE. **Default REDLINE pending source-line evidence.** |

---

## D — Substrate gaps in current Attestplane (source-grounded)

| # | Question | Answer | Severity | Earliest phase |
|---|---|---|---|---|
| D.1 | Are the current 12 `event_type` strings sufficient? | **No** — Phase 2 ADR-0008 v1 candidates: `lease_lifecycle_event`, `policy_check_event`, `settlement_event`, `worker_observation_event`, `gateway_decision_event`, `runtime_action_record`, `replay_event`, `admin_action_event`. **All as payload schemas — never on `ChainedEvent`.** | nice-to-have | Phase 2 |
| D.2 | Does `ProofBundle` need a `policy_trace` field? | **Yes** — but as `policy_trace_refs: list[str]` (hashes pointing into chain), not embedded trace body. `ProofBundle` is M5-new, no v0.0.1 vectors conflict. | blocking for M5 | Phase 2 |
| D.3 | Does `VerificationResult` need machine-readable `reason_code`? | **Yes — critical Phase 2 upgrade**. Current `reason: str \| None` is free-text, can't be consumed by downstream verifiers. Introduce `reason_code: ReasonCodeV1` enum (independent `reason_code_schema_version`); keep legacy `reason: str` for backward compat. | blocking | Phase 2 (new ADR-0010) |
| D.4 | Does `AuditorExport` need a `replay_transcript` section? | **Indirect** — use `replay_manifest_ref: str` (hash reference, see A.9 / B.6). Direct embedding risks raw-payload leak (forbidden_fields). | nice-to-have | Phase 3 |
| D.5 | Does adapter ABC need standardised `runtime_action` / `runtime_observation` / `runtime_decision` shapes? | **Yes** — three payload schemas in ADR-0008 v1; adapter only does `translate()` (ADR-0004 § 4 — single-method ABC). | blocking for Phase 3 | Phase 3 |
| D.6 | Does the project need an Attestation Graph (DAG)? | **Future ADR, not v0.x** — current linear chain satisfies ADR-0002. DAG crosses multiple chains and introduces verifier complexity. Mark as **future ADR (≥ ADR-0020)**, independent of `chain.schema_version`. | future ADR | v2.0+ |
| D.7 | Does the project need Claim / Evidence / Verification / Decision four-quadrant model? | **Yes — ADR-0009 itself contributes this mental model** in its `Context` section. | nice-to-have | Phase 1 (ADR-0009 textual section) |
| D.8 | Does the project need `release_claims` schema (parallel to ADR-0008 obligations)? | **Yes — independent `release_claims_v1.schema.json`**; template structure borrowed from AIOS `round_alpha_dry_run_known_limitations_risk_acceptance.{md,json}` (migration plan §1.4 already tagged REFACTOR). | nice-to-have | Phase 2 |
| D.9 | Does the project need deterministic replay manifest format? | **Yes** — see A.9; schema + verifier only, no replay engine. | blocking for Phase 3 | Phase 3 |

---

## E — Three-phase roadmap

### Phase 1 — Low-risk absorption (doc-only + schema drafts; **zero core changes**)

**Forbidden in Phase 1**:
- Modify `canonicalize()` bytes.
- Modify `ChainedEvent` fields.
- Modify `substrate.append()` body.
- Import any AIOS package.
- Modify v0.0.1-alpha `vectors.json` / `text_vectors.json` / `signature_vectors.json`.

**Deliverables**:

| ID | File | Type | Source ADR |
|---|---|---|---|
| P1.1 | `docs/policy/forbidden_fields.md` + `schemas/v1/forbidden_fields_v1.json` | doc + schema | ADR-0004 |
| P1.2 | `docs/spec/canonical-text-v1.md` (already shipped — confirm convergence note) | spec | new ADR-0011 |
| P1.3 | `docs/spec/evidence-event-envelope-v1.md` | spec doc | ADR-0002, ADR-0004 |
| P1.4 | `docs/architecture/ATTESTATION_GATES.md` A1–A5 detail | doc | ADR-0004 |
| P1.5 | `docs/adr/0009-aios-absorption-boundary.md` (this audit's ADR product) | **ADR Accepted 2026-05-17** | ADR-0004 |
| P1.6 | `docs/policy/four_quadrant_claim_evidence_verification_decision.md` (D.7) | concept doc | ADR-0004 |

**Anti-scope-creep CI gates**:
- `rg -n 'lease\.grant|policy\.enforce|scheduler|dispatcher' sdk/` must be empty.
- ADR-0009 review must cite ADR-0004 § 1.

### Phase 2 — Proof capability enhancement

**New ADRs**:
- ADR-0008 evidence event taxonomy v1
- ADR-0010 verification `reason_code` enum (with independent `reason_code_schema_version = 1`)
- ADR-0011 canonical-text v1 (sibling of canonical-JSON, strict separation)
- ADR-0012 `policy_decision_trace` field in `ProofBundle` metadata (not on `ChainedEvent`)

**Deliverables**:

| ID | File | Touches | BC impact | Conformance |
|---|---|---|---|---|
| P2.1 | `attestplane.canonical_text` (Py + TS) | new files; decoupled from `canonical.py` | yes | `canonical_text_vectors.json` (not `vectors.json`) |
| P2.2 | `schemas/v1/proof_bundle.schema.json` + builder | M5 new construct | yes | `proof_bundle_vectors.json` |
| P2.3 | `schemas/v1/policy_check_event.schema.json` (A.8) | payload schema only | yes | `policy_check_event_vectors.json` |
| P2.4 | `VerificationResult.reason_code: ReasonCodeV1` | new optional field on existing `types.py::VerificationResult` | yes (legacy `reason: str` retained) | negative-fixture suite verifying byte-stable `reason_code` |
| P2.5 | `schemas/v1/release_claims_v1.schema.json` | independent schema | yes | n/a |
| P2.6 | `schemas/v1/replay_event.schema.json` (A.9) + verifier predicate | new files | yes | `replay_event_vectors.json` |
| P2.7 | 4 evidence payload schemas (`lease_lifecycle_event`, `policy_check_event`, `settlement_event`, `worker_observation_event`) | payload schemas only; **`ChainedEvent` unchanged** | yes | one fixture each |
| P2.8 | `docs/spec/adapter_event_mapping_standard.md` | doc | yes | n/a |

**Anti-scope-creep CI gates**:
- Any P2.* PR diff must NOT touch: `canonicalize()` body, `ChainedEvent` fields, `substrate.append()`, frozen vectors files. Path-protected CI gate.
- `reason_code` enum values must cite ADR-0010 enum table; free-text rejected.
- Each new `event_type` ships with anti-scope-creep invariant text.

### Phase 3 — AIOS adapter deepening (Attestplane as external proof layer)

**Hard boundary** for Phase 3:
- Attestplane repo ships only (a) `GenericRuntimeAdapter` ABC; (b) fixture schemas; (c) conformance harness.
- AIOS repo implements its own `translate()` and emits fixture-conforming bytes.
- **Zero AIOS source enters Attestplane.**

**Deliverables**:

| ID | File | Description |
|---|---|---|
| P3.1 | `attestplane.adapters.base.GenericRuntimeAdapter` | abstract base — **only method `translate(runtime_event) -> EventDraft`**; 15 forbidden verbs per ADR-0004 § 4 |
| P3.2 | `attestplane.adapters.aios_spec` | docstring-only stub (already exists) |
| P3.3 | `tests/fixtures/aios_adapter_conformance/` | (AIOS-shaped JSON input, expected `EventDraft` canonical bytes) pairs |
| P3.4 | `LeaseProofRecord` payload conformance fixture | pairs with A.7 |
| P3.5 | `PolicyDecisionRecord` payload conformance fixture | pairs with A.8 |
| P3.6 | `WorkerObservationRecord` payload conformance fixture | pairs with B.7 |
| P3.7 | `GatewayActionRecord` payload conformance fixture | pairs with B.8 (audit half from A.10) |
| P3.8 | `ReplayEvidenceExport` schema + fixture | pairs with A.9 |
| ~~P3.9~~ | ~~`examples/python/aios_run_to_proof_bundle.py`~~ | **OUT OF SCOPE — REDLINE**. Migration-plan ticket #24 (AIOS-run-to-proof-bundle example) is permanently out of scope for the Attestplane OSS repo per `memory/feedback_attestplane_aios_boundary.md`. Even an AIOS-named example carrying *synthetic* events crosses into ticket #5 / #24 territory and erodes the boundary. If a demo is needed, it lives in the AIOS commercial repo (which already has access to real AIOS data). A *generic* "any-runtime → proof_bundle" example may exist in Attestplane, but it must not carry "aios" in name, content, or framing. |

**New ADRs**:
- ADR-0013 `GenericRuntimeAdapter` interface (migration plan ticket #3)
- ADR-0014 AIOS-to-Attestplane fixture-pinning protocol (fixture lives in Attestplane repo; AIOS CI reproduces fixture bytes)

**Anti-scope-creep CI gates**:
- Adapter base class must NOT add any method named `execute / grant / decide / dispatch / schedule / cancel / notify` (15-verb gate already covers this — keep enforcing).
- All fixture payloads must pass `forbidden_fields` gate.
- Any PR introducing `import aios_*` / `from aios_*` is rejected by CI grep (INV-NEW-3).

---

## F — Risk matrix + invariants

### F.1 — Top absorption risks (12 rows)

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| F.1.1 | byte-stability: new payload schemas leak into `ChainedEvent` canonical bytes | **critical** | All payload fields live in existing `payload` slot. Path-protected CI on `canonical.py` + `vectors.json`. |
| F.1.2 | scope creep: adapter base grows an `execute()` method | high | ABC method-set locked; CI grep gate; ADR-0013 review gate. |
| F.1.3 | naming collision: `lease_lifecycle_event` confused with AIOS lease state | medium | Doc explicitly contrasts "Attestplane lease_lifecycle_event = record; AIOS lease = state." Namespace via `$id`. |
| F.1.4 | license: SPDX missing on absorbed file | medium | REUSE.toml + CI lint. |
| F.1.5 | legal / claim-safety: `reason_code` enum value misread as "compliance opinion" | high | Each `reason_code` carries `legal_disclaimer: "Technical verification only; no compliance opinion."` |
| F.1.6 | **AIOS source contamination** (MEMORY hard boundary) | **critical** | INV-NEW-3 CI grep on AIOS crate names; PR template question. |
| F.1.7 | conformance regression: new vector conflicts with v0.0.1 vectors.json | high | Topic-segregated files (`<topic>_vectors.json`); read-only check on frozen files. |
| F.1.8 | cross-language drift: Py / TS schema impl micro-diff | medium | Each schema ships Py+TS fixture replay; A4 gate. |
| F.1.9 | commercial-boundary leak: `release_claims.status` misread as "compliance certification" | medium | Status enum strictly `mapping_target / designed_toward / field_supported / verified_in_test`; reject `compliant / certified / ready` at CI. |
| F.1.10 | irreversibility: execution-plane surface in Apache-2.0 substrate is unidirectional | **critical** | Any INTEGRATE-DIRECT with authority semantics needs GOVERNANCE.md supermajority + new ADR amending ADR-0004. |
| **R-NEW-1** | **Extraction-line drift illusion**: contributors reason in one of two failure modes — (a) "the founder already extracted X, so Y will follow" (creep toward over-extraction, dragging authority surface into the OSS substrate, irreversible per ADR-0004 § Reversibility); or (b) "AIOS is an external system, every shape must be re-invented from scratch" (creep toward unnecessary divergence, ignoring legitimate Mode A.6 extractions the founder may authorise). Either failure produces scope drift. | **HIGH** | (a) absorption map MD enumerates every absorbed shape with `.rs` source path + dropped-field list; (b) ADR-0009 § 2 codifies the strategic extraction line (what stays in AIOS / what may be extracted via Mode A.6); (c) CI grep for `aios.dev/schemas` `$id` + AIOS Rust crate refs in `sdk/` (INV-NEW-1, INV-NEW-3). |
| **R-NEW-2** | **Schema-shape drift surfacing as authority**: absorbed enum value like `proof_type=LiveRuntimeInvariant` carries authority into Attestplane events | medium | adapter-side enum allowlist; ADR-0008 taxonomy table enumerates accepted proof_type values. |
| **R-NEW-3** | **`$id` collision via reuse**: Attestplane schema reuses `https://aios.dev/...` `$id` → downstream consumers fetch AIOS schema, re-introduce dropped fields | medium | CI: `jq '.["$id"]' schemas/v1/*.json` must match `^https://attestplane.io/`. |
| **R-NEW-4** | **Algorithm convergence misread as code provenance**: independent canonical-JSON / blake3 re-impl misread as derivative-work obligation | low | absorption-map labels A.1/A.2 as "independent convergence, no code/schema flow"; never reference AIOS commit hashes from substrate code comments. |

### F.2 — Invariants (paste verbatim into ADR-0009)

1. **`canonicalize(ChainedEvent)` byte stability is absolute.** No absorption touches `canonical.py` / `canonical.ts`.
2. **`ChainedEvent` field set is frozen.** New evidence types live as payload schemas; payload sits in the existing `payload` slot.
3. **`vectors.json` is immutable.** All new conformance fixtures live in topic-segregated files (`<topic>_vectors.json`).
4. **`substrate.append()` never touches network / KMS / TSA / external I/O.** Anchoring is the `anchor()` verb; Phase 1/2/3 never introduce append-time I/O.
5. **The four schema_version counters are independent**: `chain.schema_version=1`, `anchor_schema_version=1`, `signature_schema_version=1`, plus new `reason_code_schema_version=1` (ADR-0010).
6. **The four forbidden-verb gates are not weakened**: KeyProvider 4 verbs / TSAProvider 4 verbs / AbstractStorageBackend 9 verbs / `GenericRuntimeAdapter` 15 verbs. `GenericRuntimeAdapter`'s only effective public method remains `translate()`.
7. **Attestplane stays substrate.** Not Control Plane / orchestration / scheduler. No absorption introduces decision / dispatch / execute semantics.
8. **AIOS commercial source never enters the Attestplane repo** (founder MEMORY hard rule). All A-class deliverables are independent convergence (A.1/A.2) or schema-shape re-issue (A.3/A.6/A.7/A.8/A.9/A.10).
9. **Every new `event_type` ships with an anti-scope-creep invariant text** in the absorption map MD.
10. **Every new schema ships Py + TS dual-replay fixture.**
11. **`release_claims` / obligation `status` fields** accept only `mapping_target / designed_toward / field_supported / verified_in_test`. CI rejects `compliant / certified / ready`.
12. **Reversibility constraint**: promoting any Section B item to Section A, or moving any Section C item into A/B, requires a new ADR amending ADR-0004, with GOVERNANCE.md § 6.2 supermajority.
13. **INV-NEW-1 (`$id` discipline)**: every `schemas/v1/*.schema.json` MUST have `$id` starting with `https://attestplane.io/schemas/v1/`. Never `https://aios.dev/`. CI-enforced.
14. **INV-NEW-2 (absorption-map provenance)**: every A-class entry in `aios_absorption_map.md` MUST carry three rows — *source path*, *shape absorbed*, *fields explicitly dropped*. Missing drop-list = documentation bug.
15. **INV-NEW-3 (no AIOS Rust crate names in Attestplane sources)**: `rg '\baios_(sdk_evidence|sdk_protocol|canonical|audit|cp|runtime|protocol)\b'` under `sdk/` (excluding `docs/`) MUST return zero hits. Docstring spec stubs in `aios_spec.py` are the only permitted exception.
16. **INV-NEW-4 (proof-type allowlist on adapter ingress)**: any adapter ingesting AIOS-side `ProofType` values MUST drop `LiveRuntimeInvariant` / `ProductionLive` at the adapter boundary (Python `Literal[...]` or restricted enum).
17. **INV-NEW-5 (dedup primitive forbidden in substrate)**: the dedup matrix from `aios-canonical/src/dedup.rs` is REDLINE. Substrate code MUST NOT include semantic-similarity-based dedup, mutable `ACTIVE`/`CANDIDATE`/`RAW` memory state, or any equivalent.

---

## Licence + MEMORY boundary self-check

Two independent constraints govern AIOS → Attestplane absorption:

1. **Licence**: AIOS is proprietary (founder-authoritative; in-tree
   LICENSE-file Apache-2.0 text is non-operative). Attestplane is
   Apache-2.0 OSS. Copying proprietary source into an Apache-2.0
   repo requires an explicit grant from the proprietary licence
   holder — no such grant has been issued, so the copy is forbidden
   by copyright law itself.
2. **MEMORY rule + ADR-0004 § 4 dependency direction**: even if a
   licence grant existed, the founder posture forbids the copy to
   preserve substrate independence (Attestplane → AIOS dependency
   direction would violate ADR-0004 § 4).

Either constraint alone is sufficient. The audit's A-class items
respect **both**:

Every A-class item produces (a) a JSON Schema authored by Attestplane
under `attestplane.io` `$id`, (b) Python `TypedDict` / TS interface
authored independently from the field list, (c) a row in the absorption
map MD with source `.rs` / `.schema.json` path documenting **what was
observed and what was deliberately dropped**, not what was copied.
**No Rust code is copied; no Python file constitutes a "port of
executable logic"** — the absorbed surface is data-shape only, and
there is no executable logic in any A-item (`proof.rs` has 3 trivial
`matches!` helpers; `artifact.rs` has a constructor; `redaction.rs`
has a `redact_line` one-liner — none of which Attestplane needs to
translate because Attestplane's redaction discipline is governed by
ADR-0004 § 2, not AIOS's substring filter).

---

## Hand-off to subsequent tickets

- **`docs/architecture/aios_absorption_map.md`** — eight rows per A-item: `{source_path, shape_absorbed, fields_dropped, attestplane_id, schema_version, ADR_ref}`; Mermaid map of layers.
- **`docs/adr/0009-aios-absorption-boundary.md`** — codify the A.6 schema-shape-absorption category + five F.2 INV-NEW invariants. State Apache-2.0-vs-MEMORY-boundary distinction in `Context`.
- **Phase 1 schema drafts** (this PR): start with A.7 (`lease_lifecycle_event`) — ADR-0004 § 2 case #1, lowest political risk; then A.8 (`policy_check_event` case #10); then A.9 (`replay_event` — requires ADR-0008 v1 taxonomy update).
- **CI grep gates**: INV-NEW-1 `$id` discipline + INV-NEW-3 AIOS crate-name absence + INV-NEW-4 proof-type allowlist.
