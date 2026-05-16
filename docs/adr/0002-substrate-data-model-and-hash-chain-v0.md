# 0002. Substrate core data model and hash chain (v0.0.1)
- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer at decision time)
- **Related**: [ADR-0001](0001-use-apache-2-0-license.md), [GOVERNANCE.md §6.1](../../GOVERNANCE.md), EU AI Act Art. 12, GDPR Art. 4(5), 5(1)(c)/(e), 32, RFC 8785 (JCS), RFC 9562 (UUIDv7)

## Context

This is the first technical ADR for the Attestplane substrate. It locks the public API shape, data model, and hash-chain semantics of the Python SDK at v0.0.1 — the foundation that every later ADR (TSA anchoring in M6, signatures in M7, multi-writer concurrency, cross-language SDKs) will reference.

The substrate is intended for adoption by EU-regulated entities under the AI Act, DORA, and NIS2 — all of which place legal weight on the integrity and auditability of the recorded events. Three constraints follow:

1. **Cross-language byte-identical hashes.** Python, TypeScript, and Rust SDKs must compute the same `event_hash` for the same input, otherwise cross-SDK audit verification is impossible. This forces a restricted JSON profile, not raw JCS.

2. **Auditor-independent verification.** External auditors must be able to re-compute the hash chain from a published spec without using the SDK. This forces pure functions and an explicit canonicalization contract.

3. **EU AI Act Art. 12 field coverage.** Art. 12(2)(a) enumerates four specific log fields (use period, reference database, matched input, human verifier). Omitting them at v0.0.1 means early-customer logs lose compliance value when they are retro-fitted later.

This ADR is load-bearing: once `vectors.json` ships with v0.0.1, the golden hashes are a permanent external contract.

## Decision

### 1. Three-layer type model (envelope pattern)

- `EventDraft` — caller-provided business fields only. No chain fields.
- `AuditEvent` — `EventDraft` plus substrate-assigned `event_id` (UUIDv7) and `timestamp` (UTC). Still no chain fields.
- `ChainedEvent` — `AuditEvent` plus `seq` (monotonic), `prev_hash` (bytes), `event_hash` (bytes). Chain fields live here, not in `AuditEvent`.

Rationale: storing `event_hash` inside the value it hashes is a self-reference footgun ("hash of fields excluding event_hash itself"). The envelope split makes the hashed surface unambiguous — `event_hash = H(canonicalize(AuditEvent))` — and auditor explanation collapses to one sentence.

### 2. Restricted JSON canonicalization profile

Canonicalization extends RFC 8785 (JCS) with a restricted JSON profile that all SDKs must honor:

| Type | Allowed | Forbidden |
|---|---|---|
| string | UTF-8, **NFC-normalized** | other Unicode normalization forms |
| integer | full `int64` range | values outside `[-2^63, 2^63 - 1]` |
| boolean | `true`, `false` | — |
| null | `null` | — |
| object | sorted keys (JCS), no whitespace | duplicate keys |
| array | preserved order | — |
| float | — | **forbidden in payload** (NaN, ±Inf, ±0 ambiguity across languages) |
| datetime | RFC 3339 UTC string, microsecond precision, `Z` suffix | `+00:00` suffix, local time, nanoseconds |
| bytes | base64url (no padding) string | raw bytes in payload |

Payloads containing forbidden types MUST be rejected at `append()` with `CanonicalizationError`. This contract is the conformance target for the TypeScript and Rust SDKs.

### 3. Pure hash-chain functions

`hashchain.py` exposes pure functions with no I/O and no global state:

```python
def genesis_head() -> ChainHead: ...
def chain_extend(tip: ChainHead, draft: EventDraft, *, now: datetime, rng: Random) -> ChainedEvent: ...
def hash_event(event: AuditEvent) -> bytes: ...
def verify_chain(events: Sequence[ChainedEvent]) -> VerificationResult: ...
```

`AttestSubstrate` is a thin container around these functions plus a `threading.Lock`. Replacing the container with a multi-writer backend (PostgreSQL advisory lock, Redis CAS) in M6 leaves chain semantics untouched.

### 4. `ChainHead` as the public concurrency contract

`AttestSubstrate.tip() -> ChainHead` returns `(seq, event_hash)` atomically. Future multi-writer backends must implement an atomic compare-and-swap on this pair. Locking this shape now prevents an M6 API break.

### 5. Strongly-typed subject reference (GDPR pseudonymization at the type level)

```python
@dataclass(frozen=True, slots=True)
class SubjectRef:
    scheme: Literal["sha256_salted", "opaque", "none"]
    value: str  # empty when scheme == "none"
```

`AuditEvent.subject_ref` is `SubjectRef | None`, never a free `str`. Callers cannot accidentally write raw PII into the subject field at the type level. GDPR Art. 4(5) pseudonymization compliance evidence is type-system-backed, not policy-only.

The SDK cannot prevent raw PII inside `payload`; that remains the caller's responsibility, called out explicitly in README.

### 6. EU AI Act Art. 12 field coverage at v0.0.1

`EventDraft` includes these four fields from Art. 12(2)(a), each `None`-able in v0.0.1:

| Field | Art. 12(2)(a) subitem |
|---|---|
| `session_id: str \| None` | "period of each use of the system" |
| `reference_db_ref: str \| None` | "reference database against which input data has been checked" |
| `matched_input_ref: str \| None` | "input data for which search has resulted in a match" |
| `human_verifier: SubjectRef \| None` | "natural persons involved in verification of the results" |

These are **references**, not the data itself. A real reference database or input payload must not be inlined into the audit log — that would defeat data minimization (GDPR Art. 5(1)(c)).

### 7. Schema versioning

`AuditEvent.schema_version: int = 1` is part of the canonicalized hash input. Future ADRs that add fields increment this. Old logs remain verifiable forever because the v1 canonicalization is frozen by `vectors.json`.

### 8. Identifier choices

- `event_id`: UUIDv7 (RFC 9562). Time-ordered prefix improves B-tree index locality for the eventual PostgreSQL backend (M6); the 62 random bits provide collision resistance well past Art. 12 retention horizons.
- `event_hash` is the canonical primary key. `event_id` is a debugging convenience. Auditors verify by hash, not by UUID.

### 9. Retention is out of scope

The substrate is append-only and provides no truncation API. Retention period management (Art. 12(1) "appropriate period", GDPR Art. 5(1)(e)) is the deployer's responsibility at a higher layer. This boundary will be re-stated in deployment documentation and in SECURITY.md when M6 ships.

### 10. Local clock disclosure

`AuditEvent.timestamp` records the substrate process's local clock at append time. v0.0.1 makes no claim about clock trustworthiness. M6 will introduce RFC 3161 TSA anchoring; once TSA timestamps are present, `AuditEvent.timestamp` is downgraded to "claimed time" semantics and the TSA timestamp becomes the authoritative time. This downgrade is non-breaking because `timestamp` remains a field, only its trust level changes.

### 11. Conformance vectors as external contract

`sdk/python/tests/conformance/vectors.json` ships with v0.0.1 as ten golden `(EventDraft, expected_event_hash_hex)` pairs. These hex values are a **permanent external contract**. Adding fields requires a new `schema_version` and a new vector set; existing vectors are immutable forever.

## Consequences

### Positive
- External auditors can re-compute the hash chain from this ADR plus `vectors.json` alone, without depending on Attestplane code.
- TypeScript and Rust SDKs in M6 will have a precise conformance target (the vectors file) rather than a prose spec.
- The pure-function chain primitives compose cleanly with M6 multi-writer backends and M7 signature schemes without API breaks.
- GDPR Art. 4(5) pseudonymization and Art. 5(1)(c) data minimization have type-system evidence rather than policy-only evidence.
- EU AI Act Art. 12(2)(a) field coverage is present from day one; early customers' logs remain valid through M5+.

### Negative
- Three Python types (`EventDraft`, `AuditEvent`, `ChainedEvent`) instead of one. Mitigated by `EventDraft` being constructable with kwargs.
- Forbidding `float` in payloads is a surface friction; callers must round to integers (e.g., basis points, microseconds) or use base64 bytes. Documented in README.
- The restricted JSON profile is stricter than JCS; some JCS test corpora won't apply. Mitigated by `vectors.json` becoming the authoritative conformance suite.
- `vectors.json` is a permanent contract. A bug discovered in v0.0.1's canonicalization that changes any hex value would force a `schema_version = 2` migration and dual-verification logic forever.

### Risks accepted
- The `jcs` Python library and the eventual TypeScript/Rust JCS libraries may have subtle differences in surrogate handling. We accept this risk by requiring `vectors.json` to pass in all three languages before each release; cross-language CI is a release blocker.
- `uuid_utils` (PyO3-backed) is a binary dependency. We accept this for performance; a pure-Python fallback will be added if it becomes a packaging burden.

### Reversibility
- API shape changes before v0.0.1 release: trivial, no published artifacts.
- API shape changes after v0.0.1 release: a breaking 0.x bump, requires migration documentation; `vectors.json` hex values remain frozen.
- Canonicalization profile changes after v0.0.1 release: requires `schema_version` increment; old vectors stay valid; never retroactive.

## Compliance notes

- **EU AI Act Art. 12(1)/(2)(a)**: addressed by `session_id`, `reference_db_ref`, `matched_input_ref`, `human_verifier`. Mapping table will appear in `sdk/python/README.md`.
- **GDPR Art. 4(5)**: addressed by `SubjectRef` strong type.
- **GDPR Art. 5(1)(c) (data minimization)**: addressed by storing references, not data, in the Art. 12 fields.
- **GDPR Art. 5(1)(e) (storage limitation)**: explicitly out of scope at substrate level; deployer responsibility documented.
- **GDPR Art. 32 (integrity)**: addressed by hash chain + `verify_chain()`. Cryptographic signatures are deferred to M7 per ADR roadmap.
- **DORA Art. 11/12**: append-only audit record with verifiable integrity satisfies ICT-related incident logging baseline; deployer adds incident-specific event types.
- **CRA Art. 13**: orthogonal — SBOM obligations are met at the release artifact level (ADR-0001 §6.1), not the substrate API level.

## Follow-up ADRs anticipated

- ADR-0003: TSA / RFC 3161 anchoring strategy (M6).
- ADR-0004: Multi-writer backend choice (PostgreSQL advisory lock vs. Redis CAS, M6).
- ADR-0005: Signature scheme for `ChainedEvent` (Ed25519 baseline, M7).
- ADR-0006: TypeScript SDK conformance harness against `vectors.json` (M6).
- ADR-0007: Rust SDK conformance harness against `vectors.json` (M7).
