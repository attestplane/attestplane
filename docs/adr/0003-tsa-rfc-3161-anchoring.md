# 0003. Time-Stamp Authority anchoring (RFC 3161) for the audit chain

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer at decision time)
- **Related**: [ADR-0001](0001-use-apache-2-0-license.md), [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md), [GOVERNANCE.md §1](../../GOVERNANCE.md), [SECURITY.md](../../SECURITY.md), RFC 3161, RFC 5816, RFC 5126 (CAdES), EU AI Act Art. 12, DORA Art. 11/12, NIS2 Art. 21(2)(d), GDPR Art. 5(1)(c)

## Context

ADR-0002 locked the substrate's append-only hash chain at `schema_version = 1` and froze ten conformance vectors as a permanent external contract. The chain proves *internal* integrity — "the events Attestplane stored have not been re-ordered or mutated after the fact" — but it does not prove *temporal* integrity: nothing in v0.0.1 prevents a deployer from regenerating the whole chain with rewritten timestamps if they later wish to.

For the regulatory positioning that motivates this project (EU AI Act Art. 12 "automatic recording of events" assessable by a notified body; DORA ICT incident records subject to regulator inspection; NIS2 incident notification with cryptographic provenance), temporal integrity must be anchored to an *independent third party*. The standard mechanism is RFC 3161 Time-Stamp Authority (TSA) anchoring: a recognised PKI authority cryptographically attests "this hash was presented to me at this time", converting the substrate's internal chain into evidence a regulator or auditor can verify without trusting Attestplane.

This ADR locks the v0.1 design choices for TSA anchoring. The targets are the M6 milestone (2026-08-15) and full TypeScript SDK parity in the same milestone.

This ADR is load-bearing in one specific way: the v0.0.1 SDK is already published to TestPyPI and npm, so its canonicalization form is in the hands of (potentially) the public. Any decision here that touches `canonicalize(ChainedEvent)` invalidates `vectors.json` and breaks every external consumer that has already pinned a hash. **The design must be strictly additive.**

## Decision

### 1. Sidecar `AnchorRecord` — never inside `ChainedEvent`

A new top-level type `AnchorRecord`, persisted alongside the chain in a parallel `AnchorStore`, references the `ChainedEvent` it anchors by `(seq, event_hash)`. Anchors are never inputs to `canonicalize(ChainedEvent)`. `ChainedEvent.schema_version` stays at `1`. `vectors.json` is untouched.

```python
@dataclass(frozen=True, slots=True)
class AnchorRecord:
    anchor_schema_version: int            # = 1; independent of chain schema
    anchored_seq: int
    anchored_event_hash: bytes
    tsa_provider_id: str                  # e.g. "freetsa.org" or "digicert.tsa-2026"
    tsa_token: bytes                      # RFC 3161 TimeStampToken DER
    tsa_cert_chain: list[bytes]           # frozen at issuance (LTV preparation)
    ocsp_responses: list[bytes]           # frozen at issuance
    issued_at_claimed: datetime           # parsed from token, informational
```

A v0.1 distribution bundle (`AttestBundle`) ships both the chain and the anchors together. A v0.0.1 chain on its own continues to verify under v0.0.1 rules; anchors are strictly additive evidence layered on top.

### 2. Pluggable `TSAProvider` interface; plurality is the default

The SDK ships an abstract `TSAProvider` interface and two built-in implementations:

- `FreeTSAProvider` — free, RSA-2048, no SLA. Default for OSS / dev / self-host.
- `DigiCertProvider` — paid, enterprise SLA. Default for commercial deployments.

A `MultiTSAProvider` composite fans out a single anchor request to N providers in parallel and stores all returned tokens on the same `AnchorRecord` (cardinality of `tsa_token` becomes a list under the hood; the type above is for a single-TSA simplification — actual implementation accepts multiple).

Plurality (≥ 2 independent TSAs anchoring the same chain tip) is the *recommended* deployment, because a single TSA is one PKI root of trust, which collapses to the same failure mode as trusting Attestplane.

Additional providers (Sectigo, GlobalSign, AWS Signer, GCP CAS) are out of scope for v0.1 but the interface design will accommodate them as community contributions.

### 3. Batch-tail anchoring with dual trigger; per-event is opt-in

Default `AnchorPolicy`:

- Anchor whenever **64 events** have accumulated since the last anchor, OR
- **60 seconds** have elapsed since the last unanchored append,
- whichever fires first.

Per-event anchoring (`AnchorPolicy.per_event=True`) is opt-in for high-value low-volume cases (signing ceremonies, agent boot, irreversible legal actions).

Time-window backstop prevents idle substrates from going hours unanchored. Batch-tail anchors only the chain tip; everything before inherits temporal proof transitively through `prev_hash` linkage already proven in v0.0.1.

### 4. Anchoring is never on the `append()` critical path

`AttestSubstrate.append()` always succeeds locally and never blocks on TSA reachability. Chain integrity is independent of any external network.

A background `Anchorer` worker consumes a durable per-substrate queue. Failures retry with exponential backoff. The substrate exposes anchor state through an extended `ChainHead`:

```python
@dataclass(frozen=True, slots=True)
class ChainHead:
    seq: int
    event_hash: bytes
    anchor_status: Literal["unanchored", "pending", "anchored", "failed_permanent"]  # v0.1 addition
    last_anchored_seq: int | None         # v0.1 addition
```

(`ChainHead` is not in `vectors.json`, so these additions do not violate the v0.0.1 contract.)

Failure-mode handling:

| Outcome | Append() effect | Anchorer state |
|---|---|---|
| TSA timeout / 5xx | none | queued for retry |
| Malformed / non-RFC-3161 response | none | quarantined; `failed_permanent`; alert |
| Clock skew > 60s vs TSA `genTime` | none | anchor recorded with `clock_skew_warning`; TSA time is authoritative |
| TSA cert expired/revoked **at verification time** | none | LTV concern (see §6), not an append concern |

Rationale: coupling chain durability to network availability of an external TSA is unacceptable for an audit substrate that must survive exactly the worst-case incident — when TSA endpoints are most likely overloaded.

### 5. New verification API; do not overload `verify_chain()`

```python
def verify_chain_with_anchors(
    events: list[ChainedEvent],
    anchors: list[AnchorRecord],
    *,
    trust_roots: list[Path],
    verification_time: datetime | None = None,
) -> AnchorVerificationResult: ...

@dataclass(frozen=True, slots=True)
class AnchorVerificationResult:
    chain_ok: bool
    anchored_seqs: set[int]
    unanchored_seqs: set[int]
    anchor_results: list[SingleAnchorResult]

@dataclass(frozen=True, slots=True)
class SingleAnchorResult:
    seq: int
    provider: str
    valid: bool
    cert_status: Literal["VALID", "EXPIRED_VALID_AT_ISSUANCE", "REVOKED"]
    ltv_artifacts_present: bool
```

`verification_time=None` means "now"; setting it to the historical anchor's `genTime` is what gives the auditor the "valid when issued" answer regulators need. The existing `verify_chain()` signature is left untouched, so v0.0.1 callers remain bytes-identical.

### 6. Long-term validation: freeze evidence at issuance

v0.1 minimum: at TSA-issuance time, snapshot the **full TSA certificate chain plus OCSP/CRL responses** and embed them in `AnchorRecord`. This is the CAdES-A inspired "freeze the evidence as of now" approach (RFC 5126 §6.4). Without it, an anchor becomes unverifiable the instant the TSA cert expires — which would defeat the entire regulatory purpose for audit logs that must remain verifiable for the 5- to 10-year Art. 12 retention horizon.

Deferred to later ADRs:

- **Re-anchoring** (anchor-of-anchor at a 12-month cadence) — ADR-0007.
- **Sigstore / Rekor transparency-log redundancy** — ADR-0006.

Both must ship before the first cert in our default TSA set expires (~12 months from M6).

### 7. Backwards compatibility and cross-language conformance

- `ChainedEvent.schema_version` stays at **1**. `canonicalize(ChainedEvent)` is byte-identical to v0.0.1. CI re-runs `vectors.json` on every commit and fails on drift.
- New independent `anchor_schema_version = 1` governs `AnchorRecord` evolution.
- New conformance fixture `sdk/python/tests/conformance/anchor_vectors.json` ships with v0.1, containing mock TSA responses with pinned cert chains. This is additive; existing `vectors.json` is untouched.
- v0.0.1 chains continue to verify identically. v0.1 chains without anchors verify identically. Anchors are strictly additive evidence.
- TypeScript SDK parity gate: TS replays `anchor_vectors.json` byte-for-byte; release blocked until passing.

## Consequences

### Positive

- v0.0.1 consumers on TestPyPI and npm are not broken. The substrate's existing 10 conformance vectors remain the permanent external contract.
- Plurality of TSAs converts "Attestplane attests" into "two unrelated PKI roots attest"; the regulator-defensible position.
- Anchor failures cannot take down the substrate. Event recording is preserved during exactly the worst-case incidents (when TSAs are most likely degraded).
- LTV evidence captured at issuance makes 5+ year retention verifiable without depending on TSA infrastructure that may not exist by then.
- Two-schema decoupling (chain schema + anchor schema) lets each evolve independently.

### Negative

- Anchor verification requires `trust_roots` paths — auditors must obtain root certificates for the TSA providers we use. Mitigated by shipping a `trust_roots/` directory with the SDK populated for our default providers.
- The bundle format `AttestBundle{events, anchors}` is now the canonical wire form for distribution; an unbundled `events`-only export reverts to v0.0.1 trust level. README must be explicit.
- DigiCert and other paid TSAs have monetary cost — deployers without budget are limited to FreeTSA only, which is single-provider and therefore less defensible than the plural recommendation.

### Risks accepted

- FreeTSA SLA is "best effort, no guarantee". The Anchorer's retry queue absorbs short outages, but a multi-day FreeTSA outage on a substrate that has only FreeTSA configured will produce `unanchored` events for that window. README will tell deployers running production workloads to configure ≥ 2 providers.
- RFC 3161 cert chain validation across libraries (Python, TypeScript, Rust) has historically been a source of cross-implementation drift. The `anchor_vectors.json` cross-language conformance gate is the explicit mitigation.

### Reversibility

- Anchor design changes before v0.1 release: trivial, no published artifacts.
- Anchor design changes after v0.1 release: requires `anchor_schema_version` increment; old anchors stay valid; never retroactive.
- `ChainedEvent` is *not* changed by this ADR; reversibility of the chain itself is governed by ADR-0002 §6.

## Three load-bearing things v0.1 MUST get right

1. **`canonicalize(ChainedEvent)` byte-identical to v0.0.1.** The frozen `vectors.json` contract is the trust signal to every existing TestPyPI/npm user; touching it resets community trust.
2. **Anchoring off the `append()` critical path.** Append p99 latency must not regress when anchoring is enabled; a CI benchmark gate must enforce this.
3. **Cert chain plus OCSP frozen inside `AnchorRecord` at issuance.** Without it, every anchor is a 12-month time bomb.

## Three anti-recommendations

1. **Do not** add `tsa_token` as an optional field on `ChainedEvent`, "just for v0.1". Optional fields in canonical JSON are how byte-conformance dies.
2. **Do not** ship a single bundled trusted TSA. One TSA equals one PKI root, which is the same failure mode as trusting Attestplane.
3. **Do not** make `append()` blocking on TSA reachability, not even with a short timeout. Audit substrates must record events *especially* during incidents when TSAs are degraded.

## Compliance notes

- **EU AI Act Art. 12(1)/(2)(a)** — "automatic recording of events"; TSA anchoring is the strongest evidentiary form for an independent reviewer.
- **DORA Art. 11/12** — ICT-related incident logging records subject to regulator inspection; RFC 3161 anchoring is the de facto industry baseline for "tamper-evident with cryptographic time".
- **NIS2 Art. 21(2)(d)** — incident-handling evidence preservation; anchored chain satisfies the "verifiable timeline" expectation.
- **GDPR Art. 5(1)(c)** — data minimization preserved: anchors store hashes and references, never the underlying data.
- **eIDAS qualified time-stamping** — out of scope for v0.1 (qualified TSAs are EU-specific and require AETS / TL list integration); deferred to a future ADR if a customer requires it.

## Follow-up ADRs anticipated

Numbering note: when this ADR was first drafted, slots 0004/0005/0006 were reserved for the three items below. The boundary ADR ([ADR-0004](0004-aios-to-attestplane-boundary.md)) was deemed more load-bearing and took the 0004 slot; the three items below renumber by +1.

- **ADR-0005 — Event signing scheme.** Ed25519 per-substrate keypair signs the chain tip alongside TSA anchoring. Closes the "who appended this" gap that TSA alone does not address.
- **ADR-0006 — Sigstore / Rekor transparency-log integration.** v0.2; redundant anchor with public verifiability, completes the supply-chain story.
- **ADR-0007 — Retention, re-anchoring cadence, archival format.** 12-month re-anchor policy, `AttestBundle` long-term archival schema, GDPR Art. 17 erasure vs. AI Act Art. 12 retention conflict resolution.
