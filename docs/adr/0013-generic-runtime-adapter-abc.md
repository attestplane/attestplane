# 0013. `GenericRuntimeAdapter` abstract base — single-method adapter ABC + 14-verb forbidden gate

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer; self-signed acceptance per GOVERNANCE.md § 6.2)
- **Related**: [ADR-0004](0004-aios-to-attestplane-boundary.md) (§ 1 universal rule + § 4 dependency direction), [ADR-0008](0008-evidence-event-taxonomy-v1.md), [ADR-0009](0009-aios-absorption-boundary.md) (P3.1), [migration plan ticket #3](../architecture/aios_to_attestplane_migration_plan_20260517.md)

## Context

[ADR-0004 § 1](0004-aios-to-attestplane-boundary.md) locks the
universal rule: *any AIOS surface whose primary semantic is authority
or execution stays in AIOS. Attestplane only ever records the event
of a decision having been made, never owns the decision.*

The substrate needs **one** adapter abstraction so external runtimes
(AIOS, LangGraph, OpenAI Agents, Claude Code SDK, custom runtimes)
can translate their native event shapes into Attestplane
`EventDraft`s. Without that abstraction, every runtime would need a
bespoke integration path; with it, runtime authors implement a single
method and inherit substrate-level guarantees.

The implementation has shipped since the v0.0.2-alpha release
candidate at:

- `sdk/python/src/attestplane/adapters/base.py` — `GenericRuntimeAdapter` ABC with `__init_subclass__` forbidden-verb gate
- `sdk/typescript/src/adapters.ts` — TypeScript mirror with constructor-time forbidden-verb check

**No ADR has formally accepted the ABC into the substrate contract
surface.** That ADR is this one. It also locks the **exact list of
forbidden verbs** so future contributors cannot quietly add new
methods that erode the boundary.

## Decision

### 1. Single-method ABC — `translate()` only

```python
# Python
class GenericRuntimeAdapter(ABC, Generic[RuntimeEvent]):
    @abstractmethod
    def translate(self, runtime_event: RuntimeEvent) -> EventDraft:
        """Translate one runtime-specific event into one EventDraft."""
```

```typescript
// TypeScript
export abstract class GenericRuntimeAdapter<RuntimeEvent> {
  abstract translate(runtimeEvent: RuntimeEvent): EventDraft;
}
```

`translate()` is the ABC's **only** public method. There is no
`execute()`, no `grant()`, no `decide()`, no lifecycle method, no
"validate then translate" two-step API. One method, one
responsibility: take a runtime event, produce an `EventDraft`. Per
ADR-0004 § 1, anything more is execution-plane authority.

### 2. Forbidden-verb gate — 14 reserved names

The ABC's `__init_subclass__` (Python) / constructor (TypeScript)
rejects subclasses that declare any of these 14 method names at the
public level:

| Category | Verbs |
|---|---|
| **Execution** | `execute`, `run`, `dispatch` |
| **Authority grant/revoke** | `grant`, `revoke`, `issue` |
| **Decision** | `decide`, `approve`, `reject` |
| **Settlement** | `settle`, `charge`, `credit` |
| **Scheduling** | `schedule`, `allocate` |

The gate is **structural** (matches method name regardless of
arguments). A subclass declaring `def execute(self, ...)` fails at
class-creation time with a `TypeError`. Private methods
(`_execute`) are not rejected — the gate enforces the *public
boundary*.

### 3. Adapter error hierarchy

```python
AdapterError(Exception)
  └── AdapterTranslationError(AdapterError)
```

Adapters MUST raise `AdapterTranslationError` (or a subclass) rather
than:

- Returning a partially-populated `EventDraft` (silently dropping
  fields would obscure compliance evidence).
- Silently dropping the event (substrate is append-only; missing
  events are forensically equivalent to "this never happened",
  which is a wrong claim).

If a runtime event cannot be cleanly translated — malformed input,
unknown event type, GDPR Art. 4(5) subject-ref pseudonymisation
failure — the adapter MUST raise. The caller (substrate user code)
decides whether to log + skip or to abort.

### 4. Concrete adapters live OUTSIDE the substrate

Per ADR-0004 § 4 (dependency direction) + ADR-0009 § 4 REDLINE C.18:

- The substrate ships ONLY the ABC + the docstring-only spec stub
  (`aios_spec.py` — no executable adapter logic).
- Concrete adapters (e.g., `AIOSAdapter` per migration-plan ticket
  #5) live in their respective execution-plane repositories.
- `LangSmithAdapter` and `LangFuseAdapter` in the substrate's
  `adapters/` directory are exceptions because they target SaaS
  observability platforms (not authority/execution runtimes) and
  serve as **reference implementations** showing other adapter
  authors how to use the ABC.

The substrate does NOT ship `AIOSAdapter` concrete code. It does NOT
ship `LangGraphAdapter` concrete code (yet — that may come as a
Phase 3 reference implementation if a customer engagement justifies
it).

### 5. RuntimeEvent generic parameter

The ABC is generic over the runtime event type the adapter consumes:

```python
RuntimeEvent = TypeVar("RuntimeEvent")
class GenericRuntimeAdapter(ABC, Generic[RuntimeEvent]):
```

A LangSmith adapter is `GenericRuntimeAdapter[LangSmithRun]`; an
AIOS adapter (if one were authored externally) would be
`GenericRuntimeAdapter[AIOSEvent]`. The generic parameter makes
adapter authoring type-safe without enlarging the substrate's
contract surface.

## Consequences

### Positive

- One method to learn = lowest possible adapter-authoring friction.
- The 14-verb gate is enforced at class-creation time; a contributor
  cannot quietly add execution-plane methods even by accident.
- Reference implementations (LangSmith, LangFuse) prove the ABC
  works in practice without forcing authority surface into the
  substrate.
- The ABC + forbidden-verb gate is one of the four substrate gates
  named in ADR-0009 invariant 6:
  > KeyProvider 4 verbs / TSAProvider 4 verbs /
  > AbstractStorageBackend 9 verbs / GenericRuntimeAdapter 14 verbs.

### Negative

- 14 reserved names is a non-trivial discipline burden. Adapter
  authors writing custom helpers must avoid those names even for
  private use cases. Mitigated by underscoring (`_run` is
  permitted — gate only checks public names).
- A single-method ABC limits expressiveness. Adapters that need
  multi-step pipelines (e.g., enrichment → pseudonymise → translate)
  must encapsulate the pipeline inside `translate()` rather than
  exposing intermediate methods. This is by design — intermediate
  methods would tempt callers to invoke them in isolation, breaking
  the substrate's single-verb posture.

### Risks accepted

- ABC growth in the future requires this ADR's amendment + GOVERNANCE
  supermajority. The current single-method posture may be too
  restrictive for some future runtime; that future ADR can argue for
  expansion under the same scope-discipline rules.

### Reversibility

- Removing a verb from the forbidden list requires a new ADR
  amending this one — same level of friction as amending ADR-0004's
  universal rule.
- Adding new verbs to the list is straightforward; just amend the
  table in § 2 and update the `forbidden = {...}` set in code.

## Alternatives considered

### Alt-A. Two-method ABC (`validate()` + `translate()`)

Rejected. `validate()` would let callers invoke validation without
translation, which suggests an authority-style "veto" semantics.
Folding validation into `translate()` (which raises on failure)
preserves the single-verb posture.

### Alt-B. No forbidden-verb gate; rely on code review

Rejected. Code-review-only enforcement is too easily defeated by a
contributor who doesn't know the boundary. The structural gate
fails fast at class-creation time.

### Alt-C. Per-runtime ABC (e.g., `AIOSAdapter` ABC, `LangGraphAdapter` ABC)

Rejected. Multiple ABCs would create N×M coupling (N runtimes ×
M version of each ABC) and force the substrate to track every
runtime's evolution. The generic `GenericRuntimeAdapter[RuntimeEvent]`
delegates that complexity to the runtime's own type definition,
keeping the substrate runtime-neutral.

### Alt-D. Ship `AIOSAdapter` concrete implementation in substrate

Rejected. ADR-0009 § 4 REDLINE C.18 (migration-plan ticket #5):
AIOSAdapter concrete code is the commercial differentiator and
stays in AIOS commercial repo. The substrate provides only the ABC.

## Compatibility with existing conformance vectors

This ADR is **fully additive**. No code or fixture changes.
All existing tests continue to pass (`adapters` test suite covers
the ABC + the two reference implementations; the 14-verb gate is
already exercised by negative tests).

- `vectors.json` (10) — unchanged.
- `text_vectors.json` (12) — unchanged.
- `signature_vectors.json` (5) — unchanged.
- All payload-vectors files (P0/P1) — unchanged.
- All ProofBundle conformance — unchanged.

## Implementation status

Accepted 2026-05-17. The implementation has been live since
v0.0.2-alpha release-candidate stage:

- `sdk/python/src/attestplane/adapters/base.py` — 162 LOC, with
  `__init_subclass__` 14-verb gate.
- `sdk/typescript/src/adapters.ts` — 126 LOC, with constructor-time gate.
- `sdk/python/src/attestplane/adapters/{langsmith,langfuse,aios_spec}.py`
  — reference implementations.
- `sdk/typescript/src/adapters/{langsmith,langfuse}.ts` — TS
  reference implementations.
- 19 + 16 + 16 = 51 adapter tests across both languages.

This ADR formally locks:

1. The single-method ABC contract.
2. The exact 14-verb forbidden list (canonical text of § 2 table).
3. The `Adapter*Error` hierarchy.
4. The "concrete adapters live outside the substrate" posture
   (except for SaaS-observability reference implementations).

## Follow-up

ADR-0014 (next, P2.2) ships the **fixture-pinning protocol** —
how external adapter authors (especially AIOS, per ADR-0009 § 4
REDLINE C.18 + C.19) prove their adapters produce Attestplane-byte-
identical `EventDraft`s without their code entering the substrate
repo.
