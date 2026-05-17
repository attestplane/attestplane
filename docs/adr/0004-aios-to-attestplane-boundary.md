# 0004. AIOS-to-Attestplane scope boundary (substrate vs. execution plane)

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer at decision time)
- **Related**: [ADR-0001](0001-use-apache-2-0-license.md), [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0003](0003-tsa-rfc-3161-anchoring.md), [`aios_to_attestplane_migration_plan_20260517.md`](../architecture/aios_to_attestplane_migration_plan_20260517.md), [`ATTESTATION_GATES.md`](../architecture/ATTESTATION_GATES.md), AIOS upstream `docs/adr/0007.md` (eval-gate authority), AIOS upstream `docs/adr/0010.md` (lease), AIOS upstream `docs/adr/0016.md` (settlement)

## Context

Attestplane is spun off from AIOS (a closed-source AI Agent Operating System maintained in a separate repository at `~/aios/`). Both projects share the same founder, the same hash-chain primitive, and the same regulatory positioning (EU AI Act Art. 12, DORA Art. 8/11/12, NIS2 Art. 21, GDPR Art. 4(5)). Without an explicit boundary the two codebases will drift into one of two failure modes:

- **Capture mode** — Attestplane's OSS surface absorbs AIOS execution-plane semantics (lease authority, eval-gate decisions, settlement execution, budget enforcement). Downstream OSS users inherit AIOS-specific assumptions they cannot operate without the closed-source counterpart, and Apache 2.0 compliance becomes a fiction.
- **Drift mode** — Attestplane re-implements its own scheduler, lease manager, and policy engine, fragmenting the founder's effort and producing two competing partial systems.

The aios-to-attestplane migration plan (committed `43676fd`) classifies every AIOS surface into five buckets (INTEGRATE-DIRECT / INTEGRATE-REFACTOR / REFERENCE-ONLY / KEEP-IN-AIOS-COMMERCIAL / DO-NOT-PORT) and enumerates ten boundary cases in § 4. This ADR locks those boundary rules into project policy and resolves the recurring "where does this capability belong?" question for every future feature, ADR, ticket, and PR.

The ADR is also the load-bearing document for an external claim the founder makes publicly: that Attestplane is **substrate** (records-only, verifiable, opaque to the workload) and is **not** an AI Agent Operating System (does not own routing, lease issuance, policy execution, settlement, or scheduling). If that boundary is not crisp, the claim is false; if the claim is false the lawyer-founder positioning collapses. Hence the ADR is `Status: Accepted` from inception rather than `Proposed`.

## Decision

### 1. Universal rule

> Any AIOS surface whose primary semantic is **authority** or **execution** stays in AIOS.
> Attestplane only ever records the **event** of a decision having been made, never owns the decision.

"Authority" = the act of granting, denying, allocating, scheduling, dispatching, or terminating.
"Execution" = the act of running, dispatching to a worker, calling a tool, mutating remote state, performing settlement, or holding session lifecycle.

Attestplane verbs are exclusively: `append(event)`, `verify_chain(events)`, `anchor(segment)`, `export(bundle)`. Any verb outside that set that appears to belong on the substrate is a boundary violation and must be reviewed against this ADR before implementation.

### 2. Ten enumerated boundary cases

The following ten AIOS surfaces are **out of scope** for Attestplane in perpetuity. Attestplane only records the corresponding evidence event with the redactions noted.

| # | AIOS capability | Attestplane records as | Required redaction |
|---|------------------|--------------------------------------------|----------------------------------------------|
| 1 | Lease granting authority | `lease_lifecycle_event { lifecycle: granted \| consumed \| expired \| revoked }` | Lease secrets, token bodies |
| 2 | Budget routing / optimizer | `budget_event { decision, threshold, observed }` | Customer billing identifiers |
| 3 | Settlement execution | `settlement_event { lifecycle: requested \| verified \| completed }` | Payment instruments, account numbers |
| 4 | Worker scheduling | `worker_assignment_event` | Worker auth tokens |
| 5 | Runtime process management | `runtime_lifecycle_event` | Process credentials |
| 6 | Gateway write authority | `gateway_decision_event` | Auth headers |
| 7 | UI read model | None — UI is downstream of substrate | n/a |
| 8 | Enterprise tenant admin | `admin_action_event` (optional) | Admin credentials, internal user names |
| 9 | Distributed worker orchestration | `distributed_dispatch_event` | Worker network addresses |
| 10 | Policy decision authority | `policy_check_event { decision, policy_id, evidence_refs }` | Policy expression bodies (hash only) |

These ten are illustrative of the universal rule, not exhaustive. New AIOS capabilities are evaluated by the rule, not by extending the table.

### 3. AIOS Q-items that do NOT become Attestplane gates

The AIOS upstream `ACCEPTANCE_CRITERIA.md` enumerates Q1–Q20. Of those, only the substrate-level subset (hash-chain integrity, canonical-JSON byte determinism, schema-drift detection, cross-language conformance, audit coverage) maps to Attestplane gates A1–A5 (locked in [`ATTESTATION_GATES.md`](../architecture/ATTESTATION_GATES.md)).

The remaining AIOS Q-items stay in AIOS. Attestplane records them as evidence events without enforcing them:

| AIOS Q | Reason it stays in AIOS | Attestplane event |
|--------|--------------------------|------------------------|
| Q1, Q15 (routing authority) | Execution-plane decision | `routing_event` |
| Q2, Q12, Q14 (lease lifecycle) | Execution-plane authority | `lease_lifecycle_event` |
| Q3–Q7 (eval / evolver / policy) | Execution-plane authority | `policy_check_event`, `eval_event` |
| Q9 (trace_id presence) | Observability concern of the runtime | `correlation_id` field on every Attestplane event |
| Q10 (budget exceeded → block) | Budget enforcement is authority | `budget_exceeded_event` |
| Q13 (state-machine authority) | Execution-plane authority | `state_transition_event` |
| Q18 (cancel within 5 s) | Execution-plane authority | `cancel_event` |
| Q19 (tenant isolation) | Cross-cutting authority; M6+ concern | (deferred; not v0.1) |

A regulator who asks "did the AI Agent system honour its lease budget?" gets the answer from AIOS (or from another adopter's execution plane), with the Attestplane event chain as the evidence trail. Attestplane never answers that question on its own authority.

### 4. Dependency direction

> Attestplane does not depend on AIOS — ever. AIOS depends on Attestplane.

- **Attestplane OSS tree** contains zero AIOS-specific imports, zero AIOS schema references, and zero adapters for AIOS runtimes that are concretely coupled. The only acknowledgment of AIOS inside Attestplane is `sdk/python/src/attestplane/adapters/aios_spec.py` (a docstring-only spec stub, no implementation; M5 deliverable per migration plan ticket #4).
- **AIOS depends on Attestplane** by pinning `attestplane>=0.0.1-alpha` (Python) and `@attestplane/attestplane@^0.0.1-alpha` (TypeScript) in its commercial repository. AIOS adapters live inside the AIOS repo, never inside Attestplane.
- **Third-party runtime adapters** (e.g. LangGraph, CrewAI, Claude Code SDK) live in their respective repositories or in `attestplane-contrib` if a vendor contributes one, never in the substrate tree.

The `GenericRuntimeAdapter` ABC (migration plan ticket #3, M5) is the only adapter surface that ships in the Attestplane substrate. It is an abstract interface that any execution plane (AIOS or third-party) can satisfy without inverting the dependency direction.

### 5. Naming and trademark separation

- The brand "**Attestplane**" and the certification mark "**Attestplane Certified**" are held by Attestplane Pte. Ltd. (in formation 2026-05-17, Singapore). Their use is governed by [TRADEMARK.md](../../TRADEMARK.md), not by the Apache 2.0 grant in [ADR-0001](0001-use-apache-2-0-license.md).
- The brand "**AIOS**" is held by the AIOS commercial entity (same founder, separate corporate vehicle). AIOS is never named as a first-class concept inside the Attestplane substrate tree — every reference is via the abstract `GenericRuntimeAdapter` or via documentation cross-links.
- An Attestplane release MUST NOT depend on, ship with, or transitively pull in any AIOS-licensed artifact. If a future Attestplane feature requires a capability that exists in AIOS, that capability is either (a) re-implemented under Apache 2.0 inside Attestplane, or (b) deferred until a third-party Apache 2.0 implementation exists.

### 6. Migration-plan classification is binding

The migration plan's five buckets — INTEGRATE-DIRECT, INTEGRATE-REFACTOR, REFERENCE-ONLY, KEEP-IN-AIOS-COMMERCIAL, DO-NOT-PORT — are the operational form of this boundary. Any future PR that moves an AIOS surface across a bucket boundary requires a new ADR amending this one.

Bucket re-classification triggers:

- INTEGRATE-DIRECT → KEEP-IN-AIOS-COMMERCIAL retraction: requires a deprecation ADR with a 2-minor-version sunset window.
- REFERENCE-ONLY → INTEGRATE-REFACTOR escalation: requires an ADR demonstrating the surface is purely record-level.
- KEEP-IN-AIOS-COMMERCIAL → INTEGRATE-REFACTOR escalation: **explicitly forbidden** without supermajority maintainer consent per [GOVERNANCE.md](../../GOVERNANCE.md). This is the strongest boundary — admitting an execution-plane surface into the substrate is the failure mode this ADR exists to prevent.

## Consequences

### Positive

- A regulator, auditor, or customer counsel reading the OSS repo can determine in one place what Attestplane is and is not. The asymmetric lawyer-founder claim risk identified in [SECURITY.md AT-08](../../SECURITY.md) is closed at the architecture level, not just the prose level.
- The five-bucket classification gives every Phase 0/1 ticket a deterministic answer to "does this belong in Attestplane?" without re-litigating the question.
- Apache 2.0 compliance is structurally protected: Attestplane never absorbs AIOS-specific assumptions, so downstream OSS users can deploy the substrate against any execution plane (AIOS, third-party, or their own) without inheriting commercial dependencies.
- The founder's parallel maintenance of two projects is sustainable: shared primitives flow OSS-first (AIOS pulls from Attestplane), not the other way around. There is exactly one upstream and exactly one downstream.

### Negative

- Some AIOS capabilities that would be useful in Attestplane (richer lease analytics, multi-tenant isolation primitives, policy-decision-point integration) cannot be added to the substrate without violating the boundary. They must instead be exposed via the `GenericRuntimeAdapter` interface and implemented in each adopter's execution plane.
- The substrate is intentionally smaller in capability than a full audit + governance product. Customers who need a turnkey "AI compliance system" will find Attestplane alone insufficient — they need an execution plane bundled with it. This is the intended commercial wedge between OSS substrate and commercial integrators, but it slows v0.0.x adoption.
- Cross-boundary feature requests from the community ("can Attestplane block on policy failure?") must be politely refused with a pointer to this ADR. That refusal pattern needs documentation in CONTRIBUTING.md.

### Risks accepted

- **AIOS as default reference adapter** creates the perception that Attestplane is "the AIOS audit module" rather than a general substrate. Mitigated by: (a) `aios_spec.py` is docstring-only and never the only adapter documented; (b) the README's tier-1 examples (per `allowed_claims.md`) avoid AIOS-specific phrasing; (c) at least one non-AIOS adapter (LangGraph or Claude Code SDK) must ship in `attestplane-contrib` by M6 or this ADR is reviewed for amendment.
- A future founder change-of-position on the OSS/commercial split could re-pressure this boundary. Mitigated by GOVERNANCE.md §6.2 (boundary changes require supermajority maintainer consent once team > 1) and by the irreversible-by-design Apache 2.0 commitment in ADR-0001.

### Reversibility

- Boundary tightening (moving a capability from in-scope to out-of-scope): reversible via deprecation ADR with sunset window. No retroactive impact on already-published chains or vectors.
- Boundary loosening (admitting an AIOS execution-plane surface into the substrate): **effectively irreversible**. Once an execution-plane semantic is in the OSS surface under Apache 2.0, the founder loses the option to gate it behind the commercial wedge. The two-key check (this ADR + GOVERNANCE.md supermajority rule) is the explicit gate.

## Alternatives considered

### A. No formal boundary; "best-effort separation"

Rejected. Without an explicit ADR, every ticket re-litigates "should this be in Attestplane?" and the founder's claim that Attestplane is *not* an AI Agent OS becomes unprovable. The asymmetric lawyer-founder claim risk (an inflated claim cited months later in a dispute) is precisely the failure mode this ADR closes; a "best-effort" boundary cannot.

### B. Permissive boundary — Attestplane absorbs AIOS authority surfaces under a feature flag

Rejected. Feature-flagged execution-plane semantics in an Apache 2.0 substrate are how OSS substrates become "lite versions" of their commercial counterpart, which (a) makes the commercial wedge transparent and reduces willingness-to-pay, (b) makes the regulatory claim unstable because the feature flag's default state determines whether the substrate is or is not the system of authority, and (c) creates an audit trail problem — events that were recorded with the flag enabled now have substantively different semantic content than events recorded with it disabled, breaking conformance.

### C. Strict boundary by license — relicense the execution-plane parts of AIOS to AGPL inside Attestplane

Rejected. Mixing Apache 2.0 and AGPL inside a single repository creates a procurement-review obstacle for exactly the EU regulated entities (DORA, BaFin, NIS2 scope) Attestplane is built to serve. ADR-0001 deliberately chose Apache 2.0 for procurement neutrality; an AGPL section would void that gain.

### D. Bidirectional namespace — Attestplane substrate as a sub-namespace of AIOS

Rejected. This is "capture mode" with a different label. Putting Attestplane under `aios.attestplane.*` would tie the OSS substrate to the AIOS brand and prevent third-party execution planes from adopting Attestplane without naming AIOS in their stack.

## Compliance and audit notes

- **EU AI Act Art. 12(1)/(2)(a)** — "automatic recording of events". The boundary clarifies that Attestplane is the *recording* substrate. The *event-producing system* is the execution plane (AIOS or other). An auditor evaluating an Attestplane-anchored chain receives the substrate-level guarantees (A1–A5 gates), not execution-plane guarantees. This separation is the regulator-defensible position.
- **DORA Art. 8** (ICT-related incident detection / response / recovery) — Attestplane records the incident events; the execution plane decides and acts. The boundary ADR is the document a DORA-aligned ICT third-party-service-provider reference can cite when describing the role split.
- **GDPR Art. 4(5) pseudonymization** — Attestplane's `SubjectRef` strong type forbids raw PII at the substrate level. The execution plane is responsible for upstream redaction before producing events. The boundary makes that responsibility explicit and unambiguous.
- **Existing audit chains remain valid after this ADR** — this ADR is a documentation and policy commitment. It does not change `canonicalize(ChainedEvent)`, `event_hash`, `prev_hash`, or any field in `vectors.json`. v0.0.1-alpha consumers and conformance vectors are unaffected.
- **Prior evidence bundles do not need regeneration** — the boundary clarifies but does not alter the substrate's recorded content.

## Follow-up ADRs anticipated

Numbering note: ADR-0003's "Follow-up ADRs anticipated" section originally reserved 0004/0005/0006 for the event-signing scheme, Sigstore/Rekor, and retention. Because the boundary ADR is more load-bearing (it gates Phase 1 implementation work in the migration plan) and was deemed urgent the same day, the boundary takes the 0004 slot and the previously anticipated ADRs renumber by +1.

- **ADR-0005 — Event signing scheme.** Ed25519 per-substrate keypair signs the chain tip alongside TSA anchoring. Closes the "who appended this" gap that TSA alone does not address.
- **ADR-0006 — Sigstore / Rekor transparency-log integration.** v0.2 redundant anchor with public verifiability.
- **ADR-0007 — Retention, re-anchoring cadence, archival format.** 12-month re-anchor policy, `AttestBundle` long-term archival schema, GDPR Art. 17 erasure vs. AI Act Art. 12 retention conflict resolution.
- **ADR-0008 — Evidence event taxonomy v1.** Concrete schemas for the ten event types enumerated in § 2 (migration plan ticket #2).
- **ADR-0009 — `GenericRuntimeAdapter` interface.** Abstract adapter API; the only adapter surface in the substrate (migration plan ticket #3).
