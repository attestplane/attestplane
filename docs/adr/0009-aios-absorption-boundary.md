# 0009. AIOS-to-Attestplane extraction protocol — open-core strategic boundary; schema-shape re-issue is the discipline pattern

- **Date**: 2026-05-17 (Proposed) / 2026-05-17 (Accepted)
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer at decision time; self-signed acceptance per GOVERNANCE.md § 6.2 with single-maintainer fallback clause)
- **Related**: [ADR-0001](0001-use-apache-2-0-license.md), [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0003](0003-tsa-rfc-3161-anchoring.md), [ADR-0004](0004-aios-to-attestplane-boundary.md), [ADR-0005](0005-event-signing-scheme.md), [ADR-0006](0006-sigstore-rekor-redundant-anchor.md), [ADR-0008](0008-evidence-event-taxonomy-v1.md), [`docs/validation/aios_to_attestplane_absorption_audit_20260517.md`](../validation/aios_to_attestplane_absorption_audit_20260517.md), [`docs/architecture/aios_absorption_map.md`](../architecture/aios_absorption_map.md), [`docs/architecture/aios_to_attestplane_migration_plan_20260517.md`](../architecture/aios_to_attestplane_migration_plan_20260517.md)

## Context

[ADR-0004](0004-aios-to-attestplane-boundary.md) drew the load-bearing
*scope* boundary between AIOS (closed-source commercial product) and
Attestplane (Apache-2.0 substrate). It did so before the AIOS source
was visible to the Attestplane work-tree. The 2026-05-17 absorption
audit (`opus-architect`, 2-pass) closed that visibility gap: AIOS at
`~/aios/` is ~225 K Rust LOC, dominated by `aios-cp` (108 K LOC) +
`aios-runtime` (67 K LOC).

### Relationship between Attestplane and AIOS (founder-authoritative)

**Attestplane was extracted from AIOS.** Attestplane is the
open-source compliance / substrate / proof-substrate module carved out
of the AIOS codebase and relicensed under Apache-2.0 for public OSS
release. AIOS itself remains a proprietary commercial product. The
founder owns the copyright to both repositories.

This relationship is an **open-core split**, not an independent-party
licence question:

| Concern | AIOS (commercial, parent) | Attestplane (Apache-2.0, extracted) |
|---|---|---|
| Copyright holder | founder | founder |
| Licence status | proprietary / closed-source | Apache-2.0 |
| Role | full Control Plane + execution + authority + commercial differentiator | substrate primitives + evidence layers + verifier surface |
| Code provenance | original development | already-extracted from AIOS, OR independently authored, OR shape-absorbed under this ADR |

Because the founder owns both copyrights, **relicensing any AIOS file
to Apache-2.0 as part of an extraction into Attestplane is legally
available at any time**. The audit's earlier framing ("Apache-2.0 →
Apache-2.0, so copy is fine" vs. "copy is forbidden by licence") was
incorrect on both sides: there is no third-party licence question.
The real question is a **strategic one** — which parts of AIOS *should*
be extracted into the OSS substrate, and which *should* remain in the
commercial parent as differentiators.

### The strategic boundary (what this ADR codifies)

The founder has chosen to keep specific AIOS capabilities in the
commercial parent because they are the commercial differentiator:
Control Plane authority, runtime orchestration, scheduling, billing,
multi-tenant authz, gateway command execution, key-lifecycle
authority, etc. (See § 4 Redlines for the full list.)

The founder has also chosen to extract specific AIOS capabilities into
the OSS substrate as Attestplane primitives: canonical hashing,
audit-event sidecar shape, hash-chain primitives, proof-bundle
builders, signing / anchoring providers, evidence event shapes
(lease lifecycle, policy decisions, replay outcomes, etc.).

Without an explicit ADR codifying the **extraction protocol**, future
contributors / future maintainers will erode the boundary one PR at a
time — either by extracting too aggressively (dragging authority
surface into the OSS substrate, which is irreversible per ADR-0004 §
Reversibility) or by treating AIOS-shaped data structures as opaque
external systems requiring full adapter translation (re-inventing the
wheel for shapes the founder already designed).

R-NEW-1 in the audit's risk matrix names the failure mode: the
**extraction-line-drift illusion** — contributors reasoning either
"the founder already extracted X, so Y will follow" (creep toward too
much) or "AIOS is external, every shape must be re-invented" (creep
toward unnecessary divergence). HIGH severity.

### Three absorption modes formalised

A third concern surfaced during the audit: the original ADR-0004
typology (10 extractable event types) did not specify *how* an AIOS
shape becomes an Attestplane primitive. Three distinct modes exist in
practice, and conflating them produces scope drift even when the
strategic line is clear. This ADR formalises them as
**scope-discipline patterns**, not legal requirements.

### Strategic context — why compliance-first, why now, why open-core

This ADR records architectural decisions; the strategic context that
*drives* the extraction sequencing is captured here so future
contributors understand the priority ordering. The founder is a
practising AI-compliance lawyer (see README "About the founder" + the
project's public positioning). Three forces shape the extraction
sequence:

1. **Compliance-first ordering**. AI compliance is the founder's
   highest-credibility business surface (legal expertise + AI
   substrate engineering + Apache-2.0 OSS = unique combination in the
   current market). The first AIOS modules extracted are therefore
   the compliance-substrate primitives (canonical hashing, hash
   chain, sidecar evidence records, signing, anchoring, proof
   bundles) — not orchestration, not authority, not billing. The
   resulting OSS substrate is what compliance, audit, and regulator
   workflows can cite and verify without trusting the closed AIOS
   parent.
2. **EU AI Act timing (August 2026)**. EU Regulation 2024/1689
   ("AI Act") obligations on high-risk AI systems take operational
   effect starting August 2026 — eight weeks from this ADR's
   2026-05-17 date. Article 12 ("Record-keeping") explicitly
   requires automatic recording of events that is "auditable" by a
   notified body. A cryptographic-evidence substrate published
   *before* the obligation date materially improves OSS uptake
   ahead of compliance procurement cycles. The ADR-0008 evidence
   taxonomy + ADR-0005 signing + ADR-0003/0006 anchoring + this
   ADR's extraction protocol are the substrate of that material
   improvement.
3. **Open-source market capture ahead of commercial competitors**.
   The OSS AI-compliance market is currently sparse (see the
   `competitive_positioning_upgrade_plan_20260517.md` 20-agent
   research output: no direct competitor occupies the 5-dimensional
   intersection of AI-agent SDK + cryptographic hash chain +
   RFC-3161/OCSP + EU AI Act/DORA + Apache-2.0 + lawyer-founder).
   Publishing the substrate as Apache-2.0 OSS *before* commercial
   players notice the gap is a one-time opportunity. Apache-2.0 is
   the strategic licence choice (per ADR-0001) precisely because it
   maximises adoption ahead of commercial market formation.

These three forces together explain the extraction priority and the
acceptance speed of this ADR. They are not legal constraints; they
are the founder's strategic ordering, captured here so future
contributors understand why compliance shape extraction (Modes A.7 /
A.8 / A.9 / A.10) is sequenced before deeper extractions.

### Claim / Evidence / Verification / Decision four-quadrant model (Gap D.7)

For future readers, the substrate's mental model is:

| Quadrant | Who emits | Who consumes | Attestplane role |
|---|---|---|---|
| **Claim** | substrate operator | auditor / verifier | record claim as `event_payload` in chain |
| **Evidence** | producing runtime (e.g. AIOS) | verifier | record observation; never produce |
| **Verification** | external verifier (auditor / regulator / SDK consumer) | claim-maker | **substrate provides verifier primitives, never the verdict** |
| **Decision** | external authority (regulator / court / governance body) | n/a | **substrate emits no decisions; ADR-0004 § 1 redline** |

Attestplane occupies the top two quadrants (Claim recording + Evidence
recording) and provides *primitives* for the Verification quadrant
(verifier walkers, byte-stable canonical forms, machine-readable
reason codes). It **never** enters the Decision quadrant.

## Decision

### 1. The three absorption modes

For any AIOS module under consideration, the audit classifies the
candidate into exactly one of three modes. The mode determines what
artefacts may enter the Attestplane repo.

#### Mode A.1/A.2 — Independent convergence (preferred where applicable)

The Attestplane primitive and the AIOS primitive arrive at the same
algorithm independently. Neither side imports the other; neither side
copies code or schema. The absorption map MD labels the pair as
"independent convergence, no code/schema flow." Examples: `canonical-json`
(both sides implement RFC-8785-style ordered JSON canonicalization),
`canonical-text` (NFC + casefold + ZW-strip + SHA-256 — straightforward
unicode primitive).

Allowed artefacts in Attestplane: full Apache-2.0 Attestplane-authored
implementation; spec doc citing RFC / algorithm sources (not AIOS).
**Forbidden**: any code comment of the form `// ported from aios-canonical`
or any commit message referencing AIOS commit hashes.

#### Mode A.3 — Taxonomy / glossary re-use (with authority redaction)

A string-set / enum value taxonomy from AIOS is re-used in Attestplane,
with explicit authority-bearing values dropped at the point of
re-use. Example: the `ProofType` enum in `~/aios/crates/aios-sdk-evidence/src/proof.rs`
has 11 variants; Attestplane keeps the substrate-meaningful subset
(`SchemaBacked`, `FixtureBacked`, `Replay`, `DeterministicReplay`,
`DryRun`) and explicitly drops authority-flavoured variants
(`LiveRuntimeInvariant`, `ProductionLive`).

Allowed: Python `Literal[...]` / TS `union` literal re-issue of the
filtered string set, with the drop-list documented in the absorption
map. **Forbidden**: importing AIOS Rust enum directly; re-exporting
the dropped values; accepting them at adapter ingress (INV-NEW-4).

#### Mode A.6 — Schema-shape re-issue (new category formalised here)

The audit's pass-2 created this category. An AIOS-side declarative
artefact (a `.rs` `serde` DTO or a `.schema.json` file) is examined
for its *field shape* (names, types, required/optional, enum sets).
Attestplane **re-issues** an equivalent schema under its own `$id`,
applying ADR-0004 § 2 column-3 redaction policy. The new schema is
*not* a copy — it is an independently authored shape-compatible
companion.

Mandatory invariants for any A.6 absorption:

1. Schema `$id` MUST start with `https://attestplane.io/schemas/v1/`.
   Never `https://aios.dev/`. (CI-enforced: INV-NEW-1.)
2. Schema MUST NOT `$ref` any AIOS `$id`. (Would couple substrate to
   AIOS schema authority — violates ADR-0004 § 4.)
3. Every field whose source counterpart bears authority signal
   (`signature` / `capability_required` / `budget_cap` / `expression`
   body / `secret` / `token` / `private_key`) MUST be replaced by a
   hash field or dropped entirely.
4. The absorption map MD MUST carry three columns for the row:
   *source path*, *shape absorbed*, *fields explicitly dropped*.
   Missing drop-list = documentation bug. (CI-enforced: INV-NEW-2.)
5. The schema MUST receive its own `<event_kind>_schema_version = 1`
   counter, independent of `chain.schema_version` / `anchor_schema_version`
   / `signature_schema_version` / `reason_code_schema_version`.

### 2. The extraction protocol (R-NEW-1 mitigation)

The founder owns both repositories' copyrights, so the constraint on
what may move from commercial AIOS into OSS Attestplane is
**strategic, not legal**. This section codifies the strategic line so
contributors do not re-litigate it case-by-case.

> **What stays in commercial AIOS** (the differentiator surface):
> Control Plane authority, runtime orchestration, worker scheduling,
> budget allocation, lease issuance, settlement execution, gateway
> command execution, multi-tenant authz, secret store, evolver /
> self-modification, eval-gate, replay execution runtime, SaaS product
> logic. These are listed in detail in § 4 Redlines.
>
> **What is already extracted into Attestplane** (the substrate
> surface, Apache-2.0): canonical hashing primitives (canonical-JSON,
> canonical-text), hash-chain primitives, audit-event sidecar shape,
> proof-bundle builders, signing scheme (`KeyProvider` ABC + four
> concrete providers), anchoring providers (RFC-3161 + Sigstore Rekor),
> storage backends (JSONL), verifier surface (`verify_chain*`).
>
> **What is eligible for future extraction** (governed by this ADR's
> Mode A.6): evidence-event payload schemas for `lease_lifecycle_event`,
> `policy_check_event`, `replay_event`, `worker_observation_event`,
> `gateway_decision_event`, `runtime_action_record`. Each requires a row
> in the absorption map MD with source path + dropped-field list, an
> Attestplane-owned `$id`, and an Attestplane-local `<event>_schema_version`.
>
> **Why the discipline pattern exists even though the founder could
> legally copy more**: scope discipline. The substrate's value depends
> on staying a *substrate* — not absorbing authority surface that would
> be irreversible per ADR-0004 § Reversibility. Mode A.6 (schema-shape
> re-issue under Attestplane `$id` with redaction) forces every absorbed
> shape to explicitly enumerate what was deliberately dropped, which is
> the load-bearing signal that prevents scope creep.

A future ADR may move the strategic line in either direction (more or
less extraction). The founder controls both repositories' copyrights,
so the amendment is a project-strategy decision.

### 3. Invariants (paste verbatim from audit § F.2; CI-enforced where marked)

1. **`canonicalize(ChainedEvent)` byte stability is absolute.** No absorption touches `canonical.py` / `canonical.ts`. *(repo-wide grep gate on `canonical.py` line count + `vectors.json` hash check)*
2. **`ChainedEvent` field set is frozen.** New evidence types live as payload schemas; payload sits in the existing `payload` slot of `ChainedEvent`. *(types.py / types.ts diff gate)*
3. **`vectors.json` is immutable.** All new conformance fixtures live in topic-segregated files (`<topic>_vectors.json`). *(read-only check on frozen file)*
4. **`substrate.append()` never touches network / KMS / TSA / external I/O.** Anchoring is the `anchor()` verb; Phase 1/2/3 never introduce append-time I/O. *(append() body grep gate)*
5. **The four `schema_version` counters are independent**: `chain.schema_version = 1`, `anchor_schema_version = 1`, `signature_schema_version = 1`, `reason_code_schema_version = 1` (new in ADR-0010).
6. **The four forbidden-verb gates are not weakened**: `KeyProvider` 4 verbs / `TSAProvider` 4 verbs / `AbstractStorageBackend` 9 verbs / `GenericRuntimeAdapter` 15 verbs. `GenericRuntimeAdapter`'s only effective public method remains `translate()`.
7. **Attestplane stays substrate.** Not Control Plane / orchestration / scheduler. No absorption introduces decision / dispatch / execute semantics.
8. **AIOS commercial source does not enter the Attestplane repo as a verbatim copy** (founder MEMORY rule + ADR-0004 § 4 dependency direction). Because the founder owns both copyrights, the constraint is strategic, not legal. All A-class deliverables are independent convergence (A.1/A.2), taxonomy re-use with redaction (A.3), or schema-shape re-issue (A.6/A.7/A.8/A.9/A.10) — each enforces scope discipline regardless of whether a verbatim copy would be legally available.
9. **Every new `event_type` ships with an anti-scope-creep invariant text** in the absorption map MD.
10. **Every new schema ships Py + TS dual-replay fixture.**
11. **`release_claims` / obligation `status` fields** accept only `mapping_target / designed_toward / field_supported / verified_in_test`. CI rejects `compliant / certified / ready`.
12. **Reversibility constraint**: promoting any Section B item to Section A, or moving any Section C item into A/B, requires a new ADR amending ADR-0004 with GOVERNANCE.md § 6.2 supermajority approval.
13. **INV-NEW-1 (`$id` discipline, CI-enforced)**: every file under `schemas/v1/*.schema.json` MUST have `$id` starting with `https://attestplane.io/schemas/v1/`. Never `https://aios.dev/`. Enforced via `jq '.["$id"]' schemas/v1/*.json | grep -vE '^"https://attestplane.io/'` must return zero hits.
14. **INV-NEW-2 (absorption-map provenance)**: every A-class entry in `docs/architecture/aios_absorption_map.md` MUST include three rows — *source path*, *shape absorbed*, *fields explicitly dropped*. An entry without an "explicitly NOT absorbed" list is a documentation bug.
15. **INV-NEW-3 (no AIOS Rust crate names in Attestplane sources, CI-enforced)**: `rg '\baios_(sdk_evidence|sdk_protocol|canonical|audit|cp|runtime|protocol)\b'` under `sdk/` (excluding `docs/` and the docstring-only stub `sdk/python/src/attestplane/adapters/aios_spec.py`) MUST return zero hits.
16. **INV-NEW-4 (proof-type allowlist on adapter ingress)**: any adapter ingesting AIOS-side `ProofType` values MUST drop `LiveRuntimeInvariant` and `ProductionLive` at the adapter boundary, via Python `Literal[...]` or restricted pydantic enum membership.
17. **INV-NEW-5 (dedup primitive forbidden in substrate)**: the C6+C7 dedup matrix from `~/aios/crates/aios-canonical/src/dedup.rs` is REDLINE. Substrate code MUST NOT include semantic-similarity-based dedup, mutable `ACTIVE / CANDIDATE / RAW` memory state, or any equivalent. Append-only event chain per ADR-0002 is the substrate's only mutation mode.

### 4. Redlines (codify from audit § C)

In addition to the 17-row REDLINE table in the absorption audit, this
ADR codifies the four source-grounded REDLINE additions discovered
in pass-2:

- **C.new-1**: `~/aios/crates/aios-canonical/src/dedup.rs` — semantic-similarity dedup against `ACTIVE` memory state. State-keeping ≠ substrate posture.
- **C.new-2**: `~/aios/crates/aios-audit/src/lib.rs` cardinality / orphan-proof layer (473 LOC) — hardwired to AIOS relational schema (`audit_events`, `runs`, `tasks`, `replay_proofs`).
- **C.new-3**: `~/aios/crates/aios-sdk-protocol/src/envelope.rs` `RequestEnvelope<T>` (lines 47–108) — transport semantics with protocol-version negotiation + idempotency + causation. The *audit* half (`aios-sdk-evidence/src/audit.rs`) is A.10; the *transport* half is REDLINE.
- **C.new-4**: `~/aios/crates/aios-canonical/src/canonical.rs` (218 LOC, NEEDS-VERIFY) — default REDLINE pending source-line evidence that it is pure unicode normalisation without state hooks.
- **C.18 (migration-plan ticket #5)**: `AIOSAdapter` concrete implementation — the AIOS-runtime-to-Attestplane-event translator. This is the *commercial differentiator* of the open-core split: the substrate ABC (`GenericRuntimeAdapter`) is OSS; the concrete AIOS-side translator is commercial AIOS code and stays in the AIOS repo. Per `memory/feedback_attestplane_aios_boundary.md`, ticket #5 is permanently out of scope for the Attestplane OSS repo. The only AIOS-adjacent file permitted in this repo is `sdk/python/src/attestplane/adapters/aios_spec.py`, which is a docstring-only stub.
- **C.19 (migration-plan ticket #24)**: AIOS-run-to-proof-bundle end-to-end example. Depends on ticket #5 (the concrete adapter). Even a "synthetic AIOS-shaped" example carrying `aios` in its filename or framing crosses into ticket #5 territory by intent and erodes the open-core boundary. Permanently out of scope. A *generic* "any-runtime → proof_bundle" example may exist in `examples/` but must not be AIOS-named, AIOS-shaped, or AIOS-positioned.

These six REDLINE additions (C.new-1 through C.new-4, plus C.18 + C.19) explicitly close the
audit's pass-2 findings and the migration-plan #5 / #24 carve-outs so
future contributors do not re-evaluate them on a PR-by-PR basis.

## Consequences

### Positive

- Future absorption PRs have a precise three-mode classification
  (A.1/A.2 / A.3 / A.6) plus a documented MEMORY-ceiling rationale.
  The license-MEMORY illusion (R-NEW-1) is mitigated by an explicit
  Context section reviewers can cite.
- The absorption map MD becomes a load-bearing artefact: any A-class
  item without a row + three columns is provably a documentation bug.
  This is the first ADR-Attestplane artefact that requires a
  companion provenance log (INV-NEW-2).
- The four-quadrant Claim / Evidence / Verification / Decision model
  is codified once and can be cited by all downstream ADRs (0008
  taxonomy, 0010 reason codes, 0013 adapter ABC) without re-deriving.
- The schema-shape re-issue category (A.6) makes Phase 2's eight
  payload schemas (A.7 / A.8 / A.9 / and others to follow) procedurally
  reviewable rather than case-by-case-debated.

### Negative

- Each new `event_type` from AIOS now carries documentation cost: a
  row in the map, a `<topic>_vectors.json` fixture, Py + TS payload
  schemas, an anti-scope-creep invariant text. This is intended
  friction — it prevents scope creep at the cost of slower absorption
  velocity.
- Reviewers must read ADR-0004 + ADR-0009 together to understand the
  absorption gate. ADR-0004 alone is insufficient.
- The `$id` discipline (INV-NEW-1) creates a one-way coupling: if
  AIOS ever splits its schema repo, Attestplane will not auto-discover
  the new location. Acceptable — INV-NEW-1's whole purpose is to make
  Attestplane *not* depend on AIOS-side schema authority.

### Risks accepted

- Some absorption candidates that are borderline A.6 vs B-class will be
  classified B-class (concept-only) by default. This is a deliberate
  asymmetry: the cost of mis-classifying an authority-bearing module
  as A.6 is high (irreversible per ADR-0004 § Reversibility); the
  cost of mis-classifying an A.6-eligible module as B-class is low
  (a future ADR can promote it).
- Algorithm convergence (A.1/A.2) is identified by audit prose, not
  by automated provenance check. A motivated contributor could in
  principle copy AIOS algorithmic implementation and claim
  convergence. Mitigation is R-NEW-4 in the risk matrix: review
  scrutiny on `canonical.py` / `canonical.ts` PRs.

### Reversibility

- The three-mode classification can be amended by a new ADR. The
  Mode A.6 category, once established, is not removable without
  retiring the schemas already issued under it (A.7 / A.8 / A.9). This
  is the same reversibility posture as ADR-0004 itself.
- The strategic extraction line can be moved (in either direction)
  by the founder, who owns both repositories' copyrights. Moving the
  line toward more extraction requires a new ADR amending ADR-0004
  with the additions documented in this ADR's Mode A.6 format
  (source path + dropped-field list + Attestplane `$id` + own
  `<event>_schema_version`). Moving the line toward less extraction
  is not currently anticipated but is also legally available to the
  founder.

## Compatibility with existing conformance vectors

This ADR is **fully additive**:

- `sdk/python/tests/conformance/vectors.json` (10 v0.0.1-alpha
  chain vectors) — unchanged. Hash-byte-stable.
- `sdk/python/tests/conformance/text_vectors.json` (12 canonical-text
  vectors) — unchanged. Hash-byte-stable.
- `sdk/python/tests/conformance/signature_vectors.json` (5 signing
  vectors, ADR-0005 T7) — unchanged. Hash-byte-stable.

New fixtures introduced under this ADR (Phase 2):

- `lease_lifecycle_event_vectors.json` (A.7)
- `policy_check_event_vectors.json` (A.8)
- `replay_event_vectors.json` (A.9)
- `worker_observation_event_vectors.json` (B.7, if promoted later)

All new fixtures are in topic-segregated files. The three frozen
files remain immutable per Invariant 3.

## Alternatives considered

### Alt-A. Verbatim AIOS schema copy under founder's relicensing authority

Rejected on scope-discipline grounds (not legal grounds — the founder
owns both copyrights and could legally relicense any AIOS schema file
to Apache-2.0 as part of an extraction). The strategic costs are:
(a) directional dependency (Attestplane consumers fetching schema by
`$id` would land on AIOS-side schema authority — ADR-0004 § 4
violation); (b) no audit trail of *what was deliberately dropped*
when authority-bearing fields ride along; (c) future AIOS schema
evolution would silently leak into Attestplane bundle semantics.
The audit's R-NEW-3 risk (`$id` collision via reuse) becomes
material the moment the first verbatim copy happens.

### Alt-B. Forbid all AIOS shape absorption; require independent re-derivation

Rejected as too conservative. Mode A.6 (schema-shape re-issue with
redaction) yields **exactly the same final artefact** as independent
re-derivation, with the additional benefit that the absorption map
MD records *what was deliberately dropped* — a provenance signal
that pure re-derivation cannot produce. The audit's redaction policy
(every authority-bearing field gets hash-only or dropped) is itself
a substrate-level discipline that benefits from being expressed
against a known source shape.

### Alt-C. Combine MEMORY rule into ADR-0004 instead of a new ADR

Rejected. ADR-0004 is the scope-boundary ADR; ADR-0009 is the
licence-versus-MEMORY-posture ADR. The two interact but address
different concerns. Folding ADR-0009 into ADR-0004 would obscure
the licence-MEMORY distinction and make INV-NEW-1...5 less
discoverable.

### Alt-D. Defer ADR-0009 until Phase 2 actually lands schemas

Rejected. The audit identified R-NEW-1 (license-MEMORY illusion) as
HIGH severity *now*: the most likely failure mode is a contributor
opening a PR with verbatim schema copy on the reasoning "Apache-2.0
→ Apache-2.0 fine." ADR-0009 must exist before the first A.6
absorption PR lands.

## Compliance and audit notes

For an auditor / external reviewer assessing the Attestplane substrate's
posture toward AIOS:

1. **Licence + provenance**: Attestplane is Apache-2.0. AIOS is the
   commercial parent product (proprietary). The founder owns copyright
   to both repositories, so any Attestplane file that originated by
   extraction from AIOS has been legitimately relicensed to Apache-2.0
   by the copyright holder. Attestplane does not contain third-party
   proprietary code.
2. **Code provenance discipline**: even though the founder may
   legally extract more AIOS code at any time, no AIOS Rust source
   appears as a verbatim copy in `sdk/` (INV-NEW-3 CI-enforced). The
   Python adapter spec stub `sdk/python/src/attestplane/adapters/aios_spec.py`
   is docstring-only (no executable adapter logic). Future extractions
   proceed via this ADR's Modes A.1/A.2/A.3/A.6 — independent
   convergence, taxonomy re-use with redaction, or schema-shape
   re-issue.
3. **Schema provenance**: schemas under `schemas/v1/` issued under
   `https://attestplane.io/` `$id` (INV-NEW-1 CI-enforced). No
   `$ref` to AIOS schema URLs — this prevents directional dependency
   (ADR-0004 § 4).
4. **Authority surface**: substrate has no `grant / deny / allocate /
   schedule / dispatch` verbs; absorbed events drop authority-bearing
   fields per Mode A.3 / Mode A.6 redaction policy. Authority surface
   stays in commercial AIOS.
5. **Reversibility**: promoting any Section B item to Section A, or
   moving any Section C item into A/B, requires an ADR amending
   ADR-0004 with GOVERNANCE.md § 6.2 supermajority approval.

The library does **not** make legal claims about the AIOS commercial
product's compliance posture. The boundary is strategic (open-core
extraction line), not a third-party licensing boundary.

## Follow-up ADRs anticipated

- **ADR-0010** — Verification `reason_code` enum + independent
  `reason_code_schema_version = 1` (Phase 2 D.3 blocking).
- **ADR-0011** — `canonical-text-v1` formal spec (Phase 2 P2.1;
  documents Attestplane-as-source-of-truth posture).
- **ADR-0012** — `policy_decision_trace` field in `ProofBundle`
  metadata (Phase 2 D.2 blocking for M5).
- **ADR-0013** — `GenericRuntimeAdapter` ABC interface (Phase 3 P3.1).
- **ADR-0014** — AIOS-to-Attestplane fixture-pinning protocol
  (fixture lives in Attestplane repo; AIOS CI reproduces fixture
  bytes; **no AIOS source enters Attestplane** — INV-NEW-3 enforced
  end-to-end).

## Implementation status

**Accepted 2026-05-17** by founder self-sign (solo maintainer at decision time). Three companion artefacts shipped under the original PR:

- `docs/validation/aios_to_attestplane_absorption_audit_20260517.md` — full audit (A through F).
- `docs/architecture/aios_absorption_map.md` — eight-row absorption map + Mermaid layer / redaction / bundle diagrams + add-a-row procedure.
- This ADR.

No code changes. No `canonicalize()` modification. No `ChainedEvent`
modification. No `substrate.append()` modification. Zero AIOS source
copied into Attestplane.

Phase 1 deliverables (P1.1–P1.6 in the audit's roadmap) are doc-only.
Phase 2 schema drafts (P2.* — A.7 / A.8 / A.9 / B.7 payload schemas
plus the four CI grep gates from INV-NEW-1/3/4/3b) are **unblocked**
as of 2026-05-17 Accept and proceed under this ADR's three-mode
discipline (A.1/A.2 independent convergence; A.3 taxonomy with
redaction; A.6 schema-shape re-issue).
