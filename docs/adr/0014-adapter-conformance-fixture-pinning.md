# 0014. AP Evidence Protocol (`AP-EVD/1.0`) — Conformance specification for two-sided AI evidence interchange

- **Date**: 2026-05-17 (v1 Accepted) / 2026-05-18 (v2 reframed as public protocol spec, Accepted)
- **Status**: Accepted (v2)
- **Deciders**: @merchloubna70-dot (founder, sole maintainer; self-signed acceptance per GOVERNANCE.md § 6.2)
- **Related**: [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md) (canonicalize), [ADR-0004](0004-aios-to-attestplane-boundary.md) (§ 4 dependency direction), [ADR-0005](0005-event-signing-scheme.md) (signing), [ADR-0008](0008-evidence-event-taxonomy-v1.md), [ADR-0009](0009-aios-absorption-boundary.md) (§ 4 REDLINE C.18 + C.19), [ADR-0013](0013-generic-runtime-adapter-abc.md)
- **Protocol artefact ID**: `AP-EVD/1.0`
- **Protocol version**: `1.0.0` (semver, independent of `chain.schema_version` / `anchor_schema_version` / `signature_schema_version` / fixture `$schema_version`)

## Context

### v1 — Original framing (Accepted 2026-05-17)

ADR-0013 ships the `GenericRuntimeAdapter` ABC. Concrete adapters
(AIOS, LangGraph, …) live outside the substrate repo per ADR-0009
§ 4 REDLINE C.18 (migration-plan ticket #5). A natural question
follows: **how does an external adapter prove it produces Attestplane-
compatible `EventDraft`s?**

Two failure modes the protocol must prevent:

1. **AIOS code creep into Attestplane** — if AIOS authors land an
   `AIOSAdapter` class in the substrate repo to "prove conformance",
   that erodes the open-core boundary (ADR-0009 R-NEW-1).
2. **Silent adapter drift** — if AIOS authors maintain their own
   conformance harness in their own repo, and that harness diverges
   from the substrate's expectations, downstream
   `verify_proof_bundle()` callers can produce mismatched results
   without anyone noticing until an auditor questions a bundle.

The protocol locked in this ADR makes one side authoritative: the
**substrate owns the fixtures**. External adapters demonstrate
conformance by reproducing the substrate-defined byte outputs from
their own runtime-shaped input.

### v2 — Reframing as public protocol specification (Accepted 2026-05-18)

The v1 framing focused on a single defensive use case (preventing AIOS
scope creep). Subsequent product-positioning work (see
`~/Documents/attestplane-business/COMMERCIAL_STRATEGY_2026-05-17_v2.0.md`
and `memory/project_attestplane_strategic_narrative_v2.md`) clarified
that Attestplane targets a **two-sided market** in which v1's
fixture-pinning mechanism plays a much larger role:

| | Side A (CONSUMES evidence) | Side B (PRODUCES evidence) |
|---|---|---|
| Who | Law firms / Big 4 AI assurance / Notified Bodies / regulators | Banks / insurers / hospitals / governments / HR platforms |
| Need | Verify supplier-supplied evidence is byte-faithful | Emit byte-faithful evidence from their runtime |
| Without a shared protocol | Cannot audit; cannot issue legal opinion | Cannot prove compliance to auditor |

**The mechanism v1 designed is, in fact, the missing shared protocol**:
each adapter author (Side B) ships a `<runtime>_v<N>.json`
fixture declaring runtime-event-input → expected-`EventDraft` pairs;
each verifier (Side A) runs the Attestplane replayer against that
fixture to confirm byte-faithfulness.

This ADR's v2 reframing:

1. Promotes the v1 fixture format from "internal scope-creep prevention
   discipline" to **public protocol specification** that any external
   implementer (Side B adapter authors in any language; Side A audit
   tool authors; third-party SDK ports in Rust/Go/Java) can target.
2. Assigns a stable **protocol artefact ID**: `AP-EVD/1.0`
   (Attestplane Evidence Protocol, version 1.0). Independent of all
   substrate internal schema versions.
3. Locks an explicit **non-goals** list (§ 4 below) so the protocol
   does NOT over-claim. This is load-bearing for AP's lawyer-founder
   positioning: making claims the substrate cannot prove would expose
   the founder to cross-border misrepresentation risk.
4. Defines minimal **governance** (founder + 14-day RFC) suitable for
   P1 phase (2026-2028 international-credibility-building stage),
   with explicit upgrade path to advisory board in P2 (≥3 independent
   production deployments OR ≥1 notified body adoption).
5. Reserves an extension slot (`conformance_level`) for future tiered
   conformance (L1/L2/L3 analogous to SLSA) without breaking v1.0.

The v2 reframing changes **no shipped code or fixture**. It is a
documentation-and-governance promotion of the existing mechanism
into a public protocol contract suitable for the two-sided market the
project now targets.

## Decision

### 1. Fixtures live in the Attestplane repo

A new directory `sdk/python/tests/fixtures/adapter_conformance/` (and
its TypeScript-side resolution path) holds adapter-conformance
fixtures. Each fixture is a JSON file declaring:

```json
{
  "$schema_version": 1,
  "fixture_kind": "adapter_conformance",
  "runtime_kind": "<opaque label, e.g., 'aios' | 'langsmith' | 'langfuse' | 'custom-runtime-v3'>",
  "fixture_version": 1,
  "description": "human-readable purpose",
  "cases": [
    {
      "name": "<unique-within-fixture>",
      "runtime_event_input": { /* the runtime-shaped event */ },
      "expected_event_draft": {
        "event_type": "...",
        "actor": "...",
        "payload": { ... },
        "subject_ref": null | { "scheme": "...", "value": "..." },
        "session_id": null | "...",
        "reference_db_ref": null | "...",
        "matched_input_ref": null | "...",
        "human_verifier": null | { ... }
      }
    }
  ]
}
```

Each `expected_event_draft` is the **byte-equal** result an
ADR-0013-conforming adapter MUST produce from the
`runtime_event_input`.

### 2. Substrate ships at least one canonical fixture per supported

   runtime

The substrate's adapters (`LangSmithAdapter` / `LangFuseAdapter`)
ship with adapter-conformance fixtures **in the same commit** as the
adapter code. Today's substrate has reference implementations for
LangSmith + LangFuse; their conformance fixtures land as part of P2.2.

The substrate does NOT ship an AIOS conformance fixture (per ADR-0009
§ 4 REDLINE C.18 — AIOSAdapter concrete code is commercial). It
provides the **fixture-format spec** in this ADR so that AIOS authors
in their commercial repo can author their own `aios_adapter_conformance.json`
that follows this schema. The AIOS-authored fixture lives in the AIOS
repo, not here.

### 3. External adapters reproduce the bytes

An adapter author (in any repo, any company) demonstrates conformance
by:

1. Subclassing `GenericRuntimeAdapter` (passes the 14-verb gate).
2. Implementing `translate(runtime_event_input) -> EventDraft`.
3. Running their adapter against each `case.runtime_event_input` in
   their authored fixture file.
4. Comparing each returned `EventDraft` byte-equal against the
   `case.expected_event_draft`.

The substrate's `tests/test_adapter_conformance.py` file ships a
**replayer** that iterates `cases` in any fixture file matching the
locked shape and asserts the byte equality. Substrate-shipped adapters
(LangSmith / LangFuse) consume their own fixtures via this replayer
inside the substrate's CI. External adapter authors consume the same
replayer in their own CI (by depending on the substrate's
`adapter_conformance.replay_fixture(fixture_path, adapter)` helper).

### 4. The substrate-side replayer is the canonical conformance gate

The substrate ships:

- A pure-functional Python function `attestplane.adapter_conformance.replay_fixture(fixture_path, adapter)` that:
  - Loads + validates the fixture against the shape locked in § 1.
  - For each case, calls `adapter.translate(case.runtime_event_input)`.
  - Asserts byte-equal `EventDraft` (canonical-JSON of the result
    equals canonical-JSON of `case.expected_event_draft`).
  - Returns a structured `AdapterConformanceReport` listing
    pass/fail per case.
- The TypeScript mirror `replayAdapterFixture(fixturePath, adapter)`.

External adapters import this helper rather than rolling their own.
This makes the substrate the single source of truth for what
"adapter conformance" means.

### 5. CI grep gate enforces "no concrete AIOS adapter in substrate"

`scripts/check-policy.sh` already enforces INV-NEW-3b (no AIOS-named
file under `sdk/` or `examples/`). This ADR's protocol does NOT
violate that gate because:

- The fixture file format spec is in this ADR (documentation, not
  code).
- The substrate's own fixture files are for LangSmith / LangFuse,
  not AIOS.
- An AIOS-conformance fixture authored by AIOS in the AIOS repo
  never enters the substrate file tree.

### 6. Fixture file naming convention

`tests/fixtures/adapter_conformance/<runtime_kind>_v<fixture_version>.json`

Examples:

- `langsmith_v1.json` — substrate-shipped for the LangSmith reference adapter.
- `langfuse_v1.json` — substrate-shipped for the LangFuse reference adapter.
- `<your_runtime>_v1.json` — authored by adapter authors in their own repo.

The `<runtime_kind>` token MUST match the `runtime_kind` field
inside the fixture JSON (sanity cross-check). The token MUST NOT
contain `aios` for substrate-shipped files (INV-NEW-3b CI gate
enforces this).

### 7. Versioning the fixture

`fixture_version` starts at 1 and increments when the runtime's
event shape evolves in a backward-incompatible way. Adding a new
`case` to an existing fixture is additive and does NOT bump
`fixture_version`. Modifying or removing a case requires bumping
`fixture_version` and shipping the old fixture file at its old
version path (e.g., `langsmith_v1.json` stays; `langsmith_v2.json`
is new).

### 8. Out of scope (v1 — operational scope)

- Substrate does NOT ship `aios_v1.json`. AIOS authors author it in
  their own commercial repo.
- Substrate does NOT run AIOS-side adapter code in its CI. AIOS CI
  is responsible for replaying its own fixture against its own
  `AIOSAdapter`.
- Substrate does NOT host external adapters' source or binary
  artifacts.

### 9. Protocol artefact ID and version scheme (v2)

The protocol is identified as **`AP-EVD/1.0`** (Attestplane Evidence
Protocol). The version follows independent semver `MAJOR.MINOR.PATCH`,
**decoupled** from:

- `chain.schema_version` (ADR-0002)
- `anchor_schema_version` (ADR-0003)
- `signature_schema_version` (ADR-0005)
- `reason_code_schema_version` (ADR-0010)
- `lease_event_schema_version` / `policy_event_schema_version` /
  `replay_event_schema_version` / `claim_schema_version`
- Fixture `$schema_version` (which is itself a byte-layout version
  of one protocol artefact, not the protocol).

External implementers (Side B adapter authors / Side A audit tool
authors / third-party SDK ports) target a stated protocol version
(e.g. "this adapter implements `AP-EVD/1.0` conformance"); they MUST
NOT need to track substrate internal schema iteration.

**Reversibility: LOW** — once `AP-EVD/1.0` is publicly declared, the
name and version triple is bound by external SDK references and
cannot be renamed without breaking external integrations.

**Rename path reserved**: a future OpenSSF / CNCF donation may
re-brand the protocol to a vendor-neutral name (e.g. `OAEP — Open
Attestation Evidence Protocol`). The `protocol_id` field is therefore
enum-typed for future alias entry. v1.0 implementations may alias
both `AP-EVD/1.0` and a future neutral name when that ADR amendment
lands.

### 10. Conformance levels (v2 — extension slot)

`AP-EVD/1.0` defines a **single binary conformance level (L0 — Pass
or Fail)** for v1.0. The fixture replayer returns `report.ok =
true/false`; no graded levels.

A reserved `conformance_level` field (currently always `"L0"`) is
declared in the fixture schema as an enum extension point. A future
ADR-0014.v3 (or successor) may introduce tiered L1/L2/L3 (analogous
to SLSA Build Levels) without breaking `AP-EVD/1.0` implementations:
any subsequent level is additive, and L0 implementations remain
conformant to their stated level.

**Rationale for L0-only at v1.0**: only 2 reference fixtures exist
today (langsmith + langfuse). SLSA itself took ~3 years to stabilise
L1–L4 conformance criteria; pre-locking levels with insufficient
field experience risks freezing the wrong axis. The extension slot
preserves the ability to grade later without breaking v1.0.

**Reversibility: HIGH** — adding levels is additive; removing the
slot would require a major version bump.

### 11. Explicit NON-GOALS (v2 — protocol scope honesty)

`AP-EVD/1.0` makes ONLY the following positive claim:

> **The conforming adapter implementation produces the byte-equal
> `EventDraft` declared in the corresponding fixture's
> `expected_event_draft` for every input in the fixture's `cases`,
> as measured by canonical-JSON serialisation per ADR-0002
> `canonicalize()`.**

The protocol explicitly **does NOT** make any of the following
claims. Implementers and verifiers MUST NOT advertise the following
on the basis of AP-EVD/1.0 conformance alone:

1. **Legal compliance** — `AP-EVD/1.0` does not guarantee, suggest,
   or certify that an AI system's output is lawful, compliant with
   any specific jurisdiction's regulation (including EU AI Act, DORA,
   NIS2, GDPR, US state laws, China CAC / 算法备案 / 生成式 AI
   暂行办法, ISO/IEC 42001, NIST AI RMF, SOC 2, or any other
   framework). Conformance attestation is a **technical statement
   about evidence byte-faithfulness**, not a legal opinion.
2. **Runtime event semantics** — the protocol does NOT verify that
   the adapter's choice of `event_type`, `actor`, or payload field
   values correctly describes the runtime's actual behaviour. It
   only verifies that the adapter's transformation is byte-faithful
   for declared cases.
3. **PII / secret redaction** — `AP-EVD/1.0` provides the byte-
   faithfulness substrate; it does NOT enforce that adapter output
   omits PII, secrets, or other forbidden payload content. Adapter
   authors and verifiers are independently responsible (per ADR-0004
   § 2 redaction policy + INV-NEW-3 enforcement in caller's CI).
4. **AI output factuality** — the protocol records evidence that
   an event happened; it does NOT claim the event's content is
   factually correct (e.g., that an LLM's answer was right, that a
   recommendation was unbiased, that a decision was fair).
5. **LLM provider endorsement** — `AP-EVD/1.0` is provider-neutral.
   No claim is made about any specific runtime, LLM, or commercial
   platform's safety, accuracy, or compliance.
6. **Legal-opinion or audit-opinion replacement** — `AP-EVD/1.0`
   conformance does NOT replace legal advice, conformity assessment
   under EU AI Act Annex VII, ISAE 3000 AI assurance, SOC 2 audit
   findings, or any other professional opinion. It is **input
   evidence** for such opinions, not a substitute.

These six non-goals are **load-bearing** for:

- (a) Attestplane's lawyer-founder positioning (over-claim would
  create cross-border misrepresentation risk).
- (b) Side A trust (auditors and notified bodies must be able to
  cite `AP-EVD/1.0` without inheriting unbounded liability).
- (c) Side B trust (adopters must understand they are not
  outsourcing legal compliance to a protocol).

**Reversibility: MEDIUM** — tightening the NON-GOALS (adding new
exclusions) is safe and additive. Loosening (removing exclusions to
make positive claims) breaks Side A trust and is unsupported.

### 12. Protocol governance (v2)

**Phase 1 (current, 2026-2028 — OSS international-credibility-building)**:
Founder is the sole maintainer. Protocol version changes follow a
**14-day public RFC** process:

1. Maintainer (or external contributor) opens a GitHub Discussion in
   `attestplane/attestplane` titled `[AP-EVD RFC] <change summary>`.
2. Discussion remains open for ≥14 calendar days.
3. Comments are public; any objection by a known implementer
   (Side A or Side B with a public conformance fixture or public
   verification deployment) requires explicit resolution.
4. After 14 days + objection resolution, the maintainer merges the
   ADR amendment.

**Phase 2 trigger (advisory board upgrade)**: when EITHER

- ≥3 independent production deployments emit `AP-EVD` conformance
  attestations publicly, OR
- ≥1 EU notified body, US audit firm (Big 4), or equivalent
  professional body adopts `AP-EVD/1.0` as input evidence for its
  attestation workflow,

the maintainer convenes a 5-member advisory board (founder +
1 EU compliance/notified-body representative + 1 Big 4 AI assurance
representative + 1 EU/US enterprise Side B representative + 1
academic/standards body representative). Subsequent protocol
versions require advisory-board supermajority approval.

**Phase 3 (OpenSSF/CNCF donation, anticipated P2 end ~ 2029)**:
governance transfers to OpenSSF AI/ML WG or CNCF, protocol may be
renamed (see § 9). Founder retains maintainer seat by donor agreement.

**Reversibility: HIGH** — governance escalation is additive; each
phase adds participants without removing rights.

## Consequences

### Positive

- One source of truth for adapter conformance: the substrate's
  fixture schema + the substrate's replayer.
- External adapter authors gain a clear contract: subclass the ABC,
  reproduce the fixture bytes, you're conformant.
- AIOS authors (per the open-core posture) can ship their own
  `aios_v1.json` in the AIOS repo and run the substrate's replayer
  against their own `AIOSAdapter` — Attestplane never sees their
  code, just the replayer-imports.
- The substrate's reference-adapter fixtures (LangSmith / LangFuse)
  double as living documentation for adapter authors.

### Negative

- Two fixture files per supported runtime (positive cases + negative
  cases would mean four; v1 ships only positive cases). Future
  iteration may add negative-case fixtures.
- Adapter authors who don't run the substrate's replayer in their
  CI can drift undetected. Mitigated by the fixture being machine-
  consumable: any third party (an auditor, a regulator) can run the
  replayer against a claimed-conformant adapter binary and verify.

### Risks accepted

- A malicious external adapter could pass the fixture-pinning test
  but mistranslate runtime events outside the fixture's coverage.
  Mitigated by the substrate maintainers expanding the fixture
  cases over time and by the substrate's downstream consumers
  exercising the adapter on their own data.
- The fixture format itself (v1) may need a v2 if a future
  EventDraft shape change forces it. v2 would require this ADR's
  amendment.

### Reversibility

- The fixture schema can grow additively (new optional fields, new
  case fields). Removing fields requires a new ADR.
- The replayer's pass/fail rules are codified in code; changing
  them is a code change with its own review cycle.

## Alternatives considered

### Alt-A. External adapters self-host their fixtures with no substrate-side schema

Rejected. Without a substrate-defined schema, fixtures from
different adapter authors would diverge in shape, defeating the
"one source of truth" goal.

### Alt-B. Substrate hosts all adapter fixtures, including AIOS-side

Rejected. AIOS-authored fixture in the substrate repo would create
the same boundary problem ADR-0009 § 4 REDLINE C.18 + C.19 prevent.
AIOS fixture lives in AIOS repo.

### Alt-C. Use JSON Schema validation as the conformance check (no byte-equal comparison)

Rejected. JSON Schema validation accepts any payload that satisfies
the schema, but does not enforce that the adapter produced the
*specific* `EventDraft` an external auditor would expect from the
*specific* runtime event. Byte equality is the stronger guarantee.

### Alt-D. In-process golden-master testing (no fixture file)

Rejected. Without a serialised fixture, external CI can't replay
against the substrate's expectations without sharing test code.
Files are the portable contract.

## Compatibility with existing conformance vectors

This ADR is **fully additive**. No existing files change.

- `vectors.json` (10) / `text_vectors.json` (12) / `signature_vectors.json`
  (5) / lease / policy / replay / reason_codes / policy_trace
  vectors — all unchanged.

New artefacts under this ADR:

- `sdk/python/src/attestplane/adapter_conformance.py` — the replayer.
- `sdk/typescript/src/adapter_conformance.ts` — TypeScript mirror.
- `sdk/python/tests/fixtures/adapter_conformance/langsmith_v1.json` —
  substrate-shipped reference fixture.
- `sdk/python/tests/fixtures/adapter_conformance/langfuse_v1.json` —
  substrate-shipped reference fixture.
- `sdk/python/tests/test_adapter_conformance.py` — replayer tests +
  the two reference fixtures' replay.

## Implementation status

**v1 Accepted 2026-05-17** (Mechanism only — internal scope-creep
prevention framing). The accompanying P2.2 commit shipped:

- The fixture-format spec (this ADR § 1).
- The replayer (`adapter_conformance.py` + `.ts`) — pure functional,
  loads fixture file, calls `adapter.translate()`, asserts byte
  equal.
- Two substrate-side fixtures (LangSmith v1 + LangFuse v1).
- Tests that exercise the replayer against the two reference
  adapters.
- A documentation note in `docs/architecture/aios_absorption_map.md`.

**v2 Accepted 2026-05-18** (Reframing as public `AP-EVD/1.0`
protocol specification). The v2 reframing is **doc-only**; no shipped
code or fixture changes. v2 adds:

- Protocol artefact ID `AP-EVD/1.0` (§ 9)
- Protocol-version semver decoupled from substrate internal schemas (§ 9)
- L0-binary conformance with reserved `conformance_level` extension slot (§ 10)
- 6 explicit NON-GOALS protecting Side A trust + lawyer-founder positioning (§ 11)
- Founder + 14-day public RFC governance with Phase 2 advisory-board trigger (§ 12)

The mechanism v1 shipped is now publicly **the foundational contract
for any external runtime adapter (Side B) AND any external verifier
(Side A) to interoperate** without their code entering the substrate
repo. Side B adapter authors target `AP-EVD/1.0` conformance; Side A
auditors / law firms / notified bodies cite `AP-EVD/1.0` conformance
in their attestation outputs.

## Follow-up

- **ADR-0014.1** may add **negative-case fixtures** that assert
  certain runtime inputs MUST cause `AdapterTranslationError`.
- **ADR-0014.2** may add a **`fixture_version_compatibility` matrix**
  spec so external CIs can pin to a specific fixture version
  without breaking on substrate updates.
- **ADR-0014.3** may introduce **L1/L2/L3 tiered conformance levels**
  (analogous to SLSA) once ≥10 independent reference fixtures and
  ≥3 production verifier deployments exist (§ 10 rationale).
- **External fixture authoring** (per § 8 v1): AIOS, LangGraph,
  Claude Code SDK, OpenAI Agents authors SHOULD ship
  `<runtime>_v1.json` in their own repos targeting `AP-EVD/1.0`.
  The substrate does NOT track external fixtures; it tracks the
  *protocol contract* they must satisfy.
- **OpenSSF / CNCF donation path** (§ 9 rename path + § 12 Phase 3):
  anticipated 2029+ once Phase 2 trigger conditions met. Protocol may
  be renamed to vendor-neutral form (e.g. `OAEP — Open Attestation
  Evidence Protocol`) at that time.
