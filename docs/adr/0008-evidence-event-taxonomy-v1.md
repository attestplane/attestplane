# 0008. Evidence event taxonomy v1 — twelve event types

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer at decision time)
- **Related**: [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0004](0004-aios-to-attestplane-boundary.md), [`evidence-event-taxonomy-v1.md`](../spec/evidence-event-taxonomy-v1.md), [`ATTESTATION_GATES.md`](../architecture/ATTESTATION_GATES.md), EU AI Act Art. 12(2)(a), DORA Art. 8, GDPR Art. 4(5)

## Context

[ADR-0004](0004-aios-to-attestplane-boundary.md) § 2 enumerated ten AIOS authority/execution surfaces and named the Attestplane evidence event that records each. That table answered "is this allowed inside Attestplane?" but did not answer "what fields does each event carry, what must be redacted, and what does it look like on the wire?"

Without a fixed taxonomy:

- Adapters drift. Two adapters for the same conceptual event (e.g., a tool call) end up writing different `event_type` strings, different `payload` shapes, and inconsistent redactions. The proof bundle that a verifier reads becomes runtime-specific, and the substrate's claim of being "runtime-agnostic" collapses.
- The obligation registry (`docs/policy/` for v0.0.1; M5-shipped `attestplane.obligations` module) cannot map regulatory articles to concrete events without a stable enumeration to map against.
- Public-claim discipline ([claims_policy.md](../policy/claims_policy.md)) cannot point at "the twelve recorded event types" if there is no canonical list to point at. The lawyer-founder claim-safety triad needs a fixed referent.
- Cross-language conformance (Python ↔ TypeScript ↔ future Rust) is currently locked at the substrate primitive level (canonical JSON, hash chain, vectors.json). Without a frozen event-type list, application-level conformance is undefined and adapters in different SDKs would diverge.

The migration-plan ticket #2 specified twelve event types as the v1 set — large enough to cover the AIOS authority-surface table plus the orthogonal substrate-level events (tool calls, policy checks, human approvals, evaluations, routing, state transitions) without ballooning into a "kitchen-sink" taxonomy that imposes specific runtime models on adopters.

## Decision

Accept the twelve event types defined in [`docs/spec/evidence-event-taxonomy-v1.md`](../spec/evidence-event-taxonomy-v1.md):

1. `tool_call_event`
2. `policy_check_event`
3. `human_approval_event`
4. `lease_lifecycle_event`
5. `budget_event`
6. `settlement_event`
7. `worker_assignment_event`
8. `runtime_lifecycle_event`
9. `gateway_decision_event`
10. `state_transition_event`
11. `eval_event`
12. `routing_event`

The taxonomy is `evidence_taxonomy_version = 1`, independent of `chain.schema_version` and `anchor_schema_version` (both at `1` from earlier ADRs but versioned separately).

**Identifier-level enforcement.** The twelve strings ship as constants in `sdk/python/src/attestplane/event_types.py` and `sdk/typescript/src/event_types.ts`. Adapters MUST import the constants; raw string literals are a code-review red flag because they bypass the rename-detection that constants give us.

**Substrate stays neutral.** The substrate's canonical-JSON layer ([ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md)) does NOT validate `event_type` against this list. The taxonomy is an application-level contract, not a substrate-level one. Reasons:

- The frozen `vectors.json` (10 conformance vectors) contains arbitrary `event_type` strings for testing; making them canonical inputs would freeze the v1 taxonomy into the v0.0.1-alpha published artifacts and prevent v2 evolution.
- Verifiers running on future-taxonomy chains must remain able to read the chain even if some events use future event types they don't recognize. Strict substrate-level validation would brick this.

**Redaction is binding.** Each entry in the spec lists "Required redactions" — fields that MUST NOT appear in `payload`. PR review and (when M5 ships) `attestplane verify --strict` enforce these. Adapters that include forbidden fields are rejected.

**Boundary anti-requirements are binding.** Each entry lists a "Boundary anti-requirement" — payload fields that would re-introduce authority/execution semantics into the substrate. These are mechanically equivalent to the ADR-0004 § 1 forbidden method names on `GenericRuntimeAdapter`: any adapter or PR that introduces them is a boundary violation.

**Versioning rules:**

| Change | Allowed in v1? | Requires |
|---|---|---|
| Add a new optional `payload` field to an existing type | Yes | PR + release note |
| Add a new required `payload` field to an existing type | **No** | New taxonomy version (v2) + deprecation window |
| Rename a `payload` field | **No** | New taxonomy version + deprecation window |
| Add a thirteenth event type | Yes | ADR amendment or superseding ADR; PR + release note |
| Remove an event type | **No (within v1)** | New taxonomy version + 1-minor-version deprecation window; old strings remain readable |
| Add a value to a `decision` enum | Yes | PR + release note (verifiers must tolerate unknown values) |
| Remove / rename a `decision` enum value | **No** | New taxonomy version |

## Consequences

### Positive

- Adapters in every language emit the same wire-level shape for the same conceptual event. Cross-runtime proof bundles are uniformly readable.
- The obligation registry (M5) has a stable enumeration to map articles against. EU AI Act Art. 12(2)(a) population (`session_id`, `reference_db_ref`, `matched_input_ref`, `human_verifier`) is documented per event type.
- Public-claim discipline gains a concrete referent: "Attestplane v0.1 records the twelve evidence event types listed in `docs/spec/evidence-event-taxonomy-v1.md`" is precise, falsifiable, and citable.
- The taxonomy externalises the boundary discipline: an adapter author reading the spec sees the boundary anti-requirements for each event type explicitly, not just as an abstract rule in ADR-0004.
- Twelve is a manageable surface to teach, document, and verify. Larger taxonomies historically rot.

### Negative

- Adopters whose runtimes have an event concept that does not map cleanly to one of the twelve must either (a) widen one of the twelve via an optional field, (b) propose a thirteenth via an ADR amendment, or (c) skip the event. The "or skip" path is acceptable for v1 — the substrate is intentionally lossy.
- The taxonomy version is a third independent version number alongside `chain.schema_version` and `anchor_schema_version`. The verifier must track all three.
- A `v2` migration (renaming an event type or adding a required field) requires a 1-minor-version window and dual-emission from adapters during the window. This is real maintenance cost paid in exchange for breakage discipline.

### Risks accepted

- **Twelve is the wrong number.** Either too few (adopters force-fit) or too many (taxonomy bloat). The ADR amendment / superseding mechanism handles both; the bigger risk is that twelve becomes "feels canonical" and we resist legitimate additions. Mitigated by explicit "Add a thirteenth event type — Yes, ADR amendment" in the versioning rules.
- **`policy_check_event` is broad.** It conflates policy gates, OPA-style ABAC decisions, and Cedar-style authorization. v1 keeps the single broad type rather than splitting into `policy_authz_event` / `policy_obligation_event` / etc. because field-level distinguishability is sufficient. A future v2 may split.
- **Naming clashes.** `state_transition_event` and `lease_lifecycle_event` both transition state. The naming follows AIOS upstream usage to make adapter porting straightforward; if the naming proves confusing in practice we'll address it in a v2.

### Reversibility

- Adding event types or optional fields: trivially reversible (next release removes them; verifiers must already tolerate unknown values).
- Renaming or removing event types: requires v2 taxonomy; the old strings stay readable for at least one minor version; chain bytes already on disk remain valid because the substrate never validated the strings.
- Renaming or removing required `payload` fields: requires v2; existing chains continue to verify under v1 because their bytes are unaffected.

## Alternatives considered

### A. Open-vocabulary `event_type` with no enumeration

Rejected. This is the status quo before this ADR. Adapters diverge, the obligation registry has nothing to map against, and public claims cannot be made precise. Open vocabularies are appropriate for telemetry / observability substrates; Attestplane is an evidence substrate whose value depends on cross-runtime semantic agreement.

### B. Substrate-level validation of `event_type` against the enumeration

Rejected. Would force a taxonomy version bump into a substrate version bump and freeze taxonomy v1 into v0.0.1-alpha's published `vectors.json` (those vectors use throwaway event_type strings for testing). Also bricks forward-compatibility: a v1 verifier reading a v2 chain would refuse to parse perfectly valid events.

### C. Tiered taxonomy (core 5 + extensible 7)

Considered. The argument: lock the five most-load-bearing (`tool_call`, `policy_check`, `human_approval`, `eval`, `state_transition`) at substrate-level and leave the seven AIOS-mirror types (`lease`, `budget`, `settlement`, `worker`, `runtime`, `gateway`, `routing`) as optional / pluggable. Rejected for v1 because the seven AIOS-mirror types are exactly the ones that drove the ADR-0004 boundary case enumeration; demoting them to optional weakens the boundary discipline.

### D. Schema-first (JSON Schema files) instead of markdown spec

Considered. JSON Schema files (`schemas/v1/events/*.schema.json`) would be machine-validatable. The spec doc instead is markdown for v1 because: (a) the substrate doesn't enforce shapes anyway (see Decision § "Substrate stays neutral"), (b) the obligation registry (M5) will ship JSON Schema files for the four bundle / export / manifest / verification-report shapes, and the per-event-type schemas can come at M6 alongside the verifier `--strict` flag, (c) writing JSON Schema for twelve types up-front before any adapter ships is premature and likely to be rewritten once real adapter data informs the field choices.

## Compliance and audit notes

- **EU AI Act Art. 12(2)(a)** — the four substrate-level fields (`session_id`, `reference_db_ref`, `matched_input_ref`, `human_verifier`) carry Art. 12(2)(a) context. The spec doc indicates which to populate per event type. Auditors reading a proof bundle can verify that Art. 12 fields are populated where required.
- **DORA Art. 8** — `runtime_lifecycle_event`, `gateway_decision_event`, and `state_transition_event` together cover ICT-related incident recording. The obligation registry (M5) will provide the formal article-to-event mapping.
- **GDPR Art. 4(5) pseudonymization** — each event type's "Required redactions" list enforces that direct identifiers are either absent or wrapped in `SubjectRef`. The spec doc and code reviews are the operative enforcement; the substrate's `SubjectRef` type enforces the top-level `subject_ref` and `human_verifier` fields but cannot enforce nested fields inside `payload` — that responsibility sits with the adapter.
- **GDPR Art. 5(1)(c) data minimization** — every event type's "Required redactions" + "Boundary anti-requirement" lists are minimization rules. The taxonomy is intentionally lossy.
- **Existing audit chains remain valid after this ADR.** This ADR is a documentation and constants commitment; it changes no canonicalization or hashing behaviour. `vectors.json`, `event_hash` computation, `prev_hash` linkage, and the v0.0.1-alpha published artifacts are unaffected.

## Follow-up ADRs anticipated

- **ADR-0009 — `GenericRuntimeAdapter` interface formal acceptance.** The ABC shipped ahead of its ADR via migration plan ticket #3; ADR-0009 will retroactively accept the design and reconcile against the ten reserved authority/execution verb names.
- **ADR-0010 — Segment cardinality (`verify_segment`).** Per-subset chain verification.
- **ADR-0011 — Deterministic replay.** Whether and how to define replay semantics on top of the taxonomy.
- **Per-event-type JSON Schema files (M6, alongside verifier `--strict`).** Machine-validatable shapes for each of the twelve types; until then the spec is the contract.
- **Taxonomy v2 (timing unknown).** Likely driver: third-party adapter ships a runtime concept that does not fit any of the twelve.
