# 0005. Event signing scheme — Ed25519 sidecar `SignatureRecord` + KeyProvider abstraction

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer at decision time)
- **Related**: [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0003](0003-tsa-rfc-3161-anchoring.md), [ADR-0004](0004-aios-to-attestplane-boundary.md), [ADR-0006](0006-sigstore-rekor-redundant-anchor.md), [`adr_0005_signing_plan_20260517.md`](../architecture/adr_0005_signing_plan_20260517.md), [`adr_0005_t3_t4_review_20260517.md`](../architecture/adr_0005_t3_t4_review_20260517.md), [`adr_0005_t6_review_20260517.md`](../architecture/adr_0005_t6_review_20260517.md), RFC 8410, RFC 8032, EU AI Act Art. 12, DORA Art. 11/12

## Context

ADR-0002 froze the substrate's append-only hash chain and ten conformance
vectors as a permanent external contract. ADR-0003 layered RFC-3161 TSA
anchoring; ADR-0006 added Sigstore Rekor as a redundant transparency-log
anchor. Both anchor every event hash chain to *external* third parties.

Anchoring proves "this chain head existed at time T" — it does **not**
prove "this chain head was produced by substrate operator X". For the
EU AI Act Art. 12 / DORA Art. 11–12 positioning (auditor-grade evidence
that the recorded events were emitted by a specific high-risk AI system,
not synthesised after the fact by an attacker who compromised the
storage layer), every chain head and/or every individual event must
carry a cryptographic signature from a key bound to the substrate
operator.

The naive design — sign every `ChainedEvent` with an operator key, embed
the signature inside the event — invalidates `vectors.json`. ADR-0002's
load-bearing rule is that v0.0.1-alpha vectors verify byte-for-byte
forever. The signing scheme must therefore be **strictly additive**
(sidecar `SignatureRecord` parallel to ADR-0003's `AnchorRecord`), and
introduce a clean abstraction for key access without violating ADR-0004
§ 1 (substrate components hold *access*, not *authority*; key lifecycle
remains the deployer's responsibility).

The detailed design walkthrough by `opus-architect` and the per-ticket
implementation reviews are linked above. This ADR records the locked
decisions and acceptance status.

## Decision

### 1. Sidecar `SignatureRecord` — never inside `ChainedEvent`

Mirrors ADR-0003's `AnchorRecord` pattern. `SignatureRecord` is a
top-level type persisted alongside the chain in a parallel signature
store, referencing the `ChainedEvent` (or segment head) it covers by
`(signed_seq, signed_event_hash)`. `ChainedEvent.schema_version` stays
at `1`; `vectors.json` is untouched.

```python
@dataclass(frozen=True, slots=True)
class SignatureRecord:
    signature_schema_version: int            # = 1; independent of chain + anchor schemas
    signed_seq: int
    signed_event_hash: bytes                 # 32-byte SHA-256
    signature: bytes                         # 64-byte Ed25519
    key_id: str                              # 16-byte hex of SHA-256(public_key_DER)
    public_key_der: bytes                    # SubjectPublicKeyInfo SPKI bytes
    signing_cert_chain: tuple[bytes, ...]    # empty in v1; Fulcio hook reserved
    signed_at: datetime
    signature_mode: Literal["segment_head", "per_event"]
    signed_payload: bytes                    # canonical bytes that were signed
```

A v0.0.2-alpha distribution bundle (`ProofBundle`) carries `signatures`
as an additive optional field. A v0.0.1-alpha bundle on its own continues
to verify under v0.0.1-alpha rules; signatures are strictly additive
evidence layered on top.

### 2. `SIGNATURE_SCHEMA_VERSION` is independent

Frozen at `1` for v1. Independent of `chain.schema_version` (ADR-0002)
and `anchor_schema_version` (ADR-0003). Future bumps require an ADR
amendment + a parallel migration of frozen `signature_vectors.json`.

### 3. Two signing modes — segment-head (default) + per-event (opt-in)

- **Segment-head** (`signature_mode = "segment_head"`) signs a canonical
  JSON over a fixed five-key payload:

  ```json
  {"chain_id": "<str>",
   "event_hash": "<lowercase hex>",
   "schema_version": 1,
   "seq": <int>,
   "signature_schema_version": 1}
  ```

  Default: every `SignaturePolicy.batch_size` events (64) OR
  `max_idle_seconds` (60) — whichever fires first. Coverage transitivity
  (option a, decided in `adr_0005_t3_t4_review_20260517.md`): a valid
  segment-head at seq=N covers seqs `{prev_signed_head+1 .. N}` via
  hash-chain integrity.

- **Per-event** (`signature_mode = "per_event"`) signs
  `canonicalize(AuditEvent)` — the exact bytes `hash_event()` already
  hashes, so byte-stability is identical to `vectors.json`. Opt-in
  (`SignaturePolicy.per_event=True`); recommended for low-volume
  high-value events (signing ceremonies, irreversible decisions, legal
  attestations). Coverage: only the signed seq.

### 4. `KeyProvider` abstraction — access, not authority

Abstract base in `attestplane.signing.base`. Concrete providers ship
in `attestplane.signing.providers`:

- `InMemoryKeyProvider` — tests / dev; optional 32-byte deterministic seed.
- `FileKeyProvider` — PKCS#8 PEM file on disk; optional passphrase; read on every signing call (file rotation picks up automatically).
- `EnvKeyProvider` — PKCS#8 PEM bytes from an environment variable (secret-manager-friendly).
- `MultiSignerProvider` — plurality (any-of-n) composite; NOT a `KeyProvider` subclass (returns `list[SigningMaterial]`).

**Forbidden-verb gate (ADR-0004 § 1 boundary preservation).** `KeyProvider`
subclasses are rejected at class-creation time (Python
`__init_subclass__`; TS constructor-time check) if they declare any of
the four reserved mutating verbs at the public level:

```
revoke, rotate, delete, replace
```

A `KeyProvider` holds key *access*, not key *authority*; key lifecycle
(creation, rotation, retirement, deletion) is the deployer's operational
responsibility. Surfacing those verbs on the substrate would invite
callers to invoke them against the substrate, eroding the boundary
ADR-0004 § 1 protects.

### 5. `key_id` derivation — 16-byte hex of SHA-256(public_key_DER)

```
key_id = sha256(public_key_der)[:16].hex()  // 32 lowercase hex chars
```

Stable across Python + TypeScript. Used for `TrustRoots` lookup and
embedded in `SignatureRecord` for self-consistency cross-checks at
verification time.

### 6. `TrustRoots` — JSON (TS) + YAML (Python)

Operator-side configuration of the keys the verifier accepts, with
validity windows. Schema:

```yaml
version: 1
keys:
  - key_id: "<32 lowercase hex chars>"
    public_key_der_b64: "<base64 SPKI>"
    valid_from: "2026-05-17T00:00:00Z"
    valid_until: "2027-05-17T00:00:00Z"
    provider_id: "<optional>"
    label: "<optional>"
```

Strict invariants (both languages): `version == 1`, non-empty `keys`,
each `key_id` cross-checked against `derive_key_id(public_key_der)`,
`valid_from < valid_until`, UTC-aware datetimes, no additional
properties at top level or per-entry, 1 MB file-size cap, duplicate
`key_id` rejected.

**Python**: YAML via `yaml.safe_load` (operator convenience).
**TypeScript**: JSON only (per `adr_0005_t6_review_20260517.md` § 1
decision 3 — avoids adding a YAML npm dep to a package whose only
runtime dep is `uuid`). Operators convert YAML → JSON via `yq` if needed.

### 7. Verifier extension — chain → signature → anchor

`verify_chain_with_signatures(events, signatures, *, chain_id, trust_roots)`
returns `(SignatureStatus, results, signed_segment_count, first_bad_index)`.
`verify_chain_full` combines chain integrity + signature verification +
ADR-0003/0006 anchor verification in one call, always executing all
three steps (no short-circuit) for forensic completeness.

`SignatureStatus` is a 5-value enum:

```
unsigned, valid, invalid, unknown_key, expired_key
```

Plurality priority (lower rank = better):

```
valid (0) < expired_key (1) < invalid (2) < unknown_key (3) < unsigned (4)
```

Per-seq merge picks the rank-minimum; bundle-level status is the
rank-maximum across the merged per-seq map. Any single `valid`
signature for a seq lifts that seq to `valid`.

### 8. Cross-language byte stability — frozen `signature_vectors.json`

Five frozen vectors in `sdk/python/tests/conformance/signature_vectors.json`
(T7 artefact). Python ships replay tests in
`sdk/python/tests/signing/test_signature_vectors.py`; TypeScript ships a
16-assertion conformance gate in
`sdk/typescript/test/conformance/signature_vectors.test.ts`. Either
side drifting fails CI.

The Ed25519 SPKI byte sequence is fixed-length 44 bytes with constant
prefix (`30 2a 30 05 06 03 2b 65 70 03 21 00 <32-byte-key>`) per RFC 8410
— no leading-zero ambiguity, no padding edge case.

**TypeScript Ed25519 seed → KeyObject path** (load-bearing R1
mitigation): PKCS#8 DER wrap (16-byte constant prefix
`302e020100300506032b657004220420` + 32-byte seed = valid 48-byte
PKCS#8 blob byte-equal to the output of `cryptography`'s
`Ed25519PrivateKey.from_private_bytes(seed)` serialisation). The
architect's initial JWK recipe was rejected because Node 22 requires
the public `x` field alongside `d`; the PKCS#8 path sidesteps the issue
without sacrificing byte stability. See
`adr_0005_t6_review_20260517.md` § 3 + § 8 revision entry.

### 9. Out of scope (explicitly)

- **Fulcio / OIDC keyless signing**. ADR-0007 (anticipated) layers
  short-lived OIDC certificates on top of the `signing_cert_chain`
  field; v1 leaves the field empty.
- **k-of-n threshold signatures**. v1 ships plurality (any-of-n) only;
  threshold is a future ADR if a customer engagement justifies it.
- **TypeScript Rekor port + ADR-0007 hooks**. Deferred per
  `adr_0005_t6_review_20260517.md` § 1 decision 9.
- **Background-thread Signer in TypeScript**. Sync-only API for v1
  (per `adr_0005_t6_review_20260517.md` § 1 decision 5); matches the
  TS `anchoring.ts` posture.
- **`canonicalize()` change**. Hard-locked by ADR-0002.

## Consequences

### Positive

- A regulator or auditor with a substrate's published trust-roots can
  independently verify that a chain head was produced by a specific
  substrate operator, not just that it existed at time T (the anchor
  proof). The combination of `verify_chain_with_signatures` +
  `verify_chain_with_anchors` is the auditor-grade evidence package
  EU AI Act Art. 12 / DORA Art. 11–12 actually need.
- Strict ADR-0004 § 1 boundary preserved at compile/import time via
  the forbidden-verb gate — substrate code cannot accidentally grow
  key-authority surface in the future.
- Cross-language byte stability locked by `signature_vectors.json` + a
  16-assertion CI gate on the TypeScript side. Future drift between
  Python and TypeScript SDKs fails CI on either side.
- Additive — v0.0.1-alpha bundles continue to verify under v0.0.1-alpha
  rules; consumers that don't speak signatures see no change. v0.0.2-alpha
  consumers gain a new optional `signatures` field.

### Negative

- Three independent schema versions to track (`chain.schema_version`,
  `anchor_schema_version`, `signature_schema_version`). Future
  contributors must understand that they are intentionally independent
  and that bumping one does not bump the others.
- `KeyProvider` subclasses cannot use the natural verbs `revoke` /
  `rotate` / `delete` / `replace` even in private helpers without
  underscoring. Documentation cost in onboarding.
- TypeScript Ed25519 seed path uses PKCS#8 DER wrap rather than the
  more discoverable JWK route, with an inline constant byte prefix.
  Reviewers unfamiliar with RFC 8410 will need to consult the ADR
  link in the source comment.

### Risks accepted

- The forbidden-verb gate is enforced at class-creation time in Python
  and constructor-time in TypeScript. A subclass that monkey-patches
  the prototype after construction in TS could in principle bypass the
  gate; this is treated as a reviewer-detectable smell, not a
  hard-blocking runtime check, because Python's `__init_subclass__`
  has the same theoretical limitation (subclasses can rebind methods
  after class creation).
- `SignatureRecord.public_key_der` is carried inside the record so
  signatures verify offline against the embedded pubkey. This means the
  signing record is ~50–100 bytes larger than strictly necessary. The
  alternative (lookup-only via `key_id` against trust roots) was
  rejected because offline-verifiability outweighs the marginal size cost.

### Reversibility

- The `signatures` field on `ProofBundle` is optional and absent when no
  records are added — existing v0.0.1-alpha bundles round-trip
  byte-identically.
- Removing the signing scheme entirely is a no-op for bundle consumers
  (the field is dropped); chain verification remains intact.
- Bumping `SIGNATURE_SCHEMA_VERSION` to 2 in the future requires
  preserving the v1 reader for backward verification of historical
  bundles.

## Alternatives considered

### A. Sign every `ChainedEvent` with the signature embedded inline

Rejected. Invalidates `vectors.json` and breaks every external consumer
that has already pinned a hash. ADR-0002's frozen contract is non-negotiable.

### B. Use a `signatures: list[bytes]` field directly on `ChainedEvent`

Rejected for the same reason as A: any field added to `ChainedEvent`
changes its canonical bytes, which changes the event hash, which
invalidates `vectors.json`.

### C. Detached signatures in a parallel `*.sig` file with no

   `SignatureRecord` type

Rejected. Loses the metadata that makes the signatures auditor-grade:
`key_id`, `signed_at`, `signed_payload` (the exact bytes signed),
`signature_mode`. A bare detached signature is not enough evidence to
satisfy "the operator signed *this specific event* at *this time* with
*this specific key*".

### D. k-of-n threshold signing instead of plurality

Rejected for v1. The implementation complexity (FROST or similar) is
substantial, and no customer has asked for it. Plurality (any-of-n)
already provides multi-signer evidence; if a regulator requires a
specific threshold, that becomes a future ADR with concrete motivating
constraints.

### E. JWK seed import path in TypeScript

Initially planned per `adr_0005_t6_review_20260517.md` § 3 first
revision. Rejected after Node 22 testing: `createPrivateKey({format:
'jwk', key: {kty:'OKP', crv:'Ed25519', d}})` requires the public `x`
field, which would force recomputing the Ed25519 point in TypeScript
land. Replaced with PKCS#8 wrap (§ 8 above), which is byte-equal to
Python's serialisation and uses only `node:crypto` primitives.

## Compliance and audit notes

For an external auditor verifying a v0.0.2-alpha bundle that includes
`signatures`:

1. The substrate operator's `TrustRoots` file (published out-of-band by
   the deployer; not part of the bundle) names the accepted `key_id`s.
2. Each `SignatureRecord` carries `public_key_der`, so the verifier
   can re-derive `key_id` and confirm it matches the trust-roots entry.
3. Validity windows (`valid_from`, `valid_until`) gate temporal acceptance.
4. The verifier re-canonicalises the covered payload (for segment_head
   mode) or the covered `AuditEvent` (per_event mode) and confirms
   `signed_payload` matches byte-for-byte before checking Ed25519.
5. The combination of `chain.verify_chain` + `verify_chain_with_signatures`
   - `verify_chain_with_anchors` is what an auditor presents to a
   notified body. Each step is independent and forensic-grade.

The library does **not** make legal claims on behalf of the deployer —
the legal disclaimer in `proof_bundle.auditor_export` (per ADR-0002 §
"governance and audit notes") explicitly notes that bundle verification
is a technical chain-integrity statement, not a compliance opinion.

## Follow-up ADRs anticipated

- **ADR-0007** — Fulcio / OIDC keyless signing as an opt-in layer on
  `SignatureRecord.signing_cert_chain`, plus retention / re-anchoring /
  re-signing policy as long-term keys rotate.
- **ADR-0009** — k-of-n threshold signatures (if customer engagement
  warrants it; deferred indefinitely otherwise).

## Implementation status

Shipped 2026-05-17 across both SDKs.

- **Python** (`attestplane.signing` package): `base.py`, `providers.py`,
  `signer.py` (sync + background worker), `trust_roots.py` (YAML loader),
  `verifier_ext.py`. Conformance tests in
  `sdk/python/tests/signing/`. Frozen vectors in
  `sdk/python/tests/conformance/signature_vectors.json` (5 vectors).
- **TypeScript** (`@attestplane/attestplane` ≥ 0.0.2-alpha):
  `src/signing/{base,providers,signer,trust_roots,verifier_ext}.ts` —
  sync-only `Signer`, JSON-only `TrustRoots`. Conformance gate in
  `test/conformance/signature_vectors.test.ts` (16 architect-locked
  assertions). Full test suite 320/320 green.
- **`ProofBundle.signatures?`** additive field present in both SDKs;
  absent when no records added (v0.0.1-alpha byte compatibility
  preserved).
