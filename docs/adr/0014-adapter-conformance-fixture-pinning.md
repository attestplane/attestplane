# 0014. Adapter conformance fixture-pinning — Attestplane owns the fixtures, external adapters reproduce the bytes

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer; self-signed acceptance per GOVERNANCE.md § 6.2)
- **Related**: [ADR-0004](0004-aios-to-attestplane-boundary.md) (§ 4 dependency direction), [ADR-0008](0008-evidence-event-taxonomy-v1.md), [ADR-0009](0009-aios-absorption-boundary.md) (§ 4 REDLINE C.18 + C.19, P3 deliverables), [ADR-0013](0013-generic-runtime-adapter-abc.md)

## Context

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

### 8. Out of scope

- Substrate does NOT ship `aios_v1.json`. AIOS authors author it in
  their own commercial repo.
- Substrate does NOT run AIOS-side adapter code in its CI. AIOS CI
  is responsible for replaying its own fixture against its own
  `AIOSAdapter`.
- Substrate does NOT host external adapters' source or binary
  artifacts.

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

Accepted 2026-05-17. The accompanying P2.2 commit ships:

- The fixture-format spec (this ADR § 1).
- The replayer (`adapter_conformance.py` + `.ts`) — pure functional,
  loads fixture file, calls `adapter.translate()`, asserts byte
  equal.
- Two substrate-side fixtures (LangSmith v1 + LangFuse v1).
- Tests that exercise the replayer against the two reference
  adapters.
- A documentation note in `docs/architecture/aios_absorption_map.md`
  pointing AIOS authors at the protocol.

The protocol is the foundational contract for any future runtime
adapter (AIOS, LangGraph, OpenAI Agents, Claude Code SDK, etc.) to
prove conformance without their code entering the substrate repo.

## Follow-up

- **A future ADR** may add `negative-case fixtures` that assert
  certain runtime inputs MUST cause `AdapterTranslationError`.
- **A future ADR** may add a `fixture_version_compatibility` matrix
  spec so external CIs can pin to a specific fixture version
  without breaking on substrate updates.
- **AIOS authors** SHOULD author an `aios_v1.json` in the AIOS repo
  following this ADR's format. The substrate does NOT track that
  fixture; it's AIOS's responsibility.
