<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# ADR-0005 Event Signing Scheme — Architect Plan

> **Status:** Read-only architectural plan, produced 2026-05-17 by an
> `opus-architect` agent dispatch after the
> `competitive_positioning_upgrade_plan_20260517` Track 2 (Sigstore
> Rekor) shipped. The Sigstore Rekor anchor [`ADR-0006`](../adr/0006-sigstore-rekor-redundant-anchor.md)
> currently relies on a bring-your-own-key Ed25519 stopgap; this plan
> reconciles that with a proper signing scheme.
>
> **Scope:** plan only. Implementation tickets follow in subsequent
> commits per § 3.
>
> **Hard constraint:** v0.0.1-alpha `vectors.json` MUST continue to
> verify byte-for-byte. `chain.schema_version` stays at 1.
> `canonicalize(AuditEvent)` byte-identical. No required-field
> additions to `AuditEvent`.

## 1. Decisions (A–H)

### A. Signing granularity — **A2 + A3 mixed (default segment-head; per-event opt-in)**

Mirror the `AnchorPolicy` (`anchoring/base.py:115-136`) two-tier
design: default sign each segment's `ChainHead` (cadence aligned with
anchoring, zero hot-path cost); opt-in `SignaturePolicy.per_event=True`
for single-event proof bundles ("law-firm engagement letter",
"irreversible legal action"). Reject A1 (per-event mandatory):
Ed25519 ~50µs per signature is unacceptable at default thousands-of-
events-per-second. Reject A2-only: loses symmetry with
`AnchorPolicy.per_event` and the lawyer-founder "single formal
letter as standalone evidence" client story.

### B. Signature storage — **B3 (pure sidecar `SignatureRecord`)**

- B1 (field on `AuditEvent`) is immediately disqualified by hard
  constraint #1.
- B2 (field on `ChainedEvent` outside the hash) preserves chain
  bytes but disturbs the TS `types.ts` dataclass parity + the
  `proof_bundle.schema.json` shape, raising migration cost.
- B3 mirrors `AnchorRecord` (`anchoring/base.py:67-112`) exactly: a
  new `signing/` subpackage with `SignatureRecord` sidecar.
  Proof bundles add an optional `signatures: list[SignatureRecord]`
  field alongside the existing `anchors`. Zero impact on the 451 +
  200 existing tests.

### C. Bytes signed — **C2 (`canonicalize(...)` canonical-JSON bytes)**

- C1 (sign the 32-byte `event_hash`) is byte-minimal but loses
  semantic provenance: verifier cannot reproduce the signed content
  independently of trusting `event_hash` calculation.
- C3 (DSSE envelope) overlaps `intoto.py` (already shipped), requires
  porting DSSE PAE to TS — cross-language risk.
- C2 cleanest: Python uses `canonical.py`, TS uses `canonical.ts`,
  both already byte-stable (locked by `vectors.json`). Segment-head
  mode signs `canonicalize({"chain_id", "seq", "event_hash",
  "schema_version": 1})`; per-event signs `canonicalize(AuditEvent)`.

### D. Key management — `KeyProvider` ABC + three concrete providers

- `attestplane.signing.KeyProvider` — abstract base, isomorphic to
  `TSAProvider`, including `__init_subclass__` forbidden-verb gate
  (rejects `revoke`/`rotate`/`delete`/`replace` — a KeyProvider does
  NOT own trust-root authority, only key access).
- v0.1 concrete providers:
  - `InMemoryKeyProvider(seed: bytes | None)` — tests / dev.
  - `FileKeyProvider(path, passphrase=None)` — PKCS#8 PEM persistence;
    compatible with ADR-0006's existing `signing_key=` parameter.
  - `EnvKeyProvider(env_var)` — deployment pattern.
- Rotation: `SignatureRecord.key_id` field = first 16 bytes of
  SHA-256(public_key_DER), hex. External `TrustRoots` YAML maps
  `key_id → pubkey_der + valid_from + valid_until`. Unknown
  `key_id` ⇒ `signature_status="unknown_key"` (NOT chain failure).
- Public-key distribution deliberately **NOT** baked in-tree
  (substrate must not become a PKI authority — boundary preserved
  per ADR-0004).

### E. Fulcio / OIDC — **deferred to ADR-0007 with hooks reserved**

Reasons to punt: (a) OIDC flow needs refresh tokens or browser
interaction in the substrate, violating "synchronous, no-network
runtime"; (b) Fulcio short-cert + Rekor combined semantics warrant a
dedicated ADR; (c) bring-your-own-key satisfies ~90% of law-firm use
cases.

Hooks reserved so Fulcio lands as a non-breaking amendment later:

- `KeyProvider` abstract returns `SigningMaterial =
  Ed25519PrivateKey | (Ed25519PrivateKey, X509Cert)` (union accepts
  future Fulcio cert).
- `SignatureRecord.signing_cert_chain: tuple[bytes, ...] = ()` —
  defaults to empty tuple; Fulcio fills with the short cert chain;
  no `signature_schema_version` bump needed.

### F. Verifier pipeline — **chain → signature → anchor**

Order rationale: signature failure is "who is responsible for this
chain" (semantic gate); anchor failure is "when did this exist"
(temporal gate). Verifying signatures first avoids spending TSA/Rekor
RTT on unauthorised chains.

`SignatureStatus = Literal["unsigned", "valid", "invalid",
"unknown_key", "expired_key"]`. Failure does **not** auto-fail the
whole chain — caller decides by context. New fields on
`BundleVerificationResult`:

- `signature_status: SignatureStatus`
- `first_bad_signature_index: int | None`
- `signed_segment_count: int`

Parallels existing `cert_status` (anchor verification output).

### G. Cross-language conformance

- Algorithm: Ed25519 only in v1 (matches ADR-0006; TS `node:crypto`
  supports natively since Node 12; no pkijs).
- Bytes signed: C2 → already byte-stable via `vectors.json`.
- Ship `signature_vectors.json` (5 entries): segment-head signed /
  per-event signed / unknown_key / invalid / multi-signature on the
  same event. Generator extends `generate_vectors.py`.
- TS `verifier.ts` gains `verifySignatures(bundle, trustRoots)`,
  CI-gated against byte equivalence with Python.

### H. Plurality — **plurality (any-of-n), not k-of-n threshold**

`MultiSignerProvider(providers: tuple[KeyProvider, ...])` produces N
`SignatureRecord` entries per segment-head (mirrors
`MultiTSAProvider`). Verifier: any matched-trust-root valid signature
counts as "segment signed".

No threshold (k-of-n): (a) requires FROST or Shamir coordination, 5×
complexity; (b) eternal-cradle's 3-of-5 guardian scheme should NOT
infect this substrate; (c) "dual-lawyer co-signing" needs are
handled at the application layer by checking "two specific
`key_id`s both `valid`" against the plurality output.

## 2. Acceptance criteria

1. `vectors.json` 10 vectors byte-identical pass in both languages.
2. `signature_vectors.json` 5 new vectors byte-identical + verifier
   results identical cross-language.
3. `SignatureRecord` does NOT appear in `canonicalize(AuditEvent)`
   input (negative test).
4. `KeyProvider.__init_subclass__` rejects any subclass declaring
   `revoke`/`rotate`/`delete`/`replace` (mirror ADR-0003 boundary
   test).
5. `SigstoreRekorAnchor.__init__(signing_key=...)` accepts the union
   `KeyProvider | Ed25519PrivateKey` for backward compatibility (no
   API break to ADR-0006 callers).
6. `proof_bundle.schema.json` stays at v1 (only adds optional
   `signatures` array; additive). TS `proof_bundle.ts` synchronised.
7. `BundleVerificationResult` adds `signature_status` +
   `signed_segment_count` fields.
8. ADR-0005 document explicitly lists scenarios this scheme does
   **not** cover (NOT an eIDAS QES; NOT a replacement for human
   wet-ink signing).

## 3. Implementation tickets (dependency-ordered)

| # | Title | Effort (PD) | Depends |
|---|-------|-------------|---------|
| T1 | `signing/base.py`: `KeyProvider` ABC + `SigningMaterial` + `SignatureRecord` + `SignaturePolicy` + `SIGNATURE_SCHEMA_VERSION` + error hierarchy + forbidden-verb gate | 1.5 | — |
| T2 | `signing/providers.py`: `InMemoryKeyProvider` / `FileKeyProvider` / `EnvKeyProvider` / `MultiSignerProvider` | 1.0 | T1 |
| T3 | `signing/signer.py`: `Signer` worker (segment-head + per-event paths); canonical-JSON input via `canonical.py`; thread-safe with the existing Anchorer | 2.0 | T1, T2 |
| T4 | `verifier.py` extension: signature pipeline + `SignatureStatus` + trust-roots loader (YAML safe-load only) | 2.0 | T1 |
| T5 | `proof_bundle.py` + `schemas/v1/proof_bundle.schema.json` additive extension + JSON Schema validator synchronisation | 1.0 | T1, T4 |
| T6 | TS mirror: `sdk/typescript/src/signing.ts` + `verifier.ts` extension + `proof_bundle.ts` schema alignment | 2.5 | T3, T4, T5 |
| T7 | `generate_vectors.py` adds 5 entries to `signature_vectors.json` + cross-language conformance test | 1.5 | T3, T6 |
| T8 | ADR-0005 document final draft + ADR-0006 § 4 amendment footnote + CHANGELOG | 1.0 | all |

**Total: ~12.5 PD.** Terminal review gate **required**, because this
change crosses schema boundaries (`proof_bundle`), cross-language
byte-stability (Python/TS), and rewrites the already-shipped
ADR-0006 API surface.

## 4. Test surface

- **Python (+~25 cases)**: `tests/signing/test_key_provider.py`
  (forbidden-verb gate / subclassing); `test_signer.py` (segment-head
  + per-event modes / empty chain / single-event chain);
  `test_signature_record.py` (schema / `key_id` stability);
  `test_verifier_signatures.py` (valid / invalid / unknown_key /
  expired_key / unsigned chain pass-through);
  `tests/negative/test_signature_tamper.py` (single-byte payload
  flip → signature invalid).
- **TS (+~15 cases)**: `signing.spec.ts` (5 shared vectors byte-
  identical with Python); `verifier.spec.ts` (multi-signer plurality
  / trust-root miss).
- **Conformance fixtures**: `signature_vectors.json` (5 entries)
  generated from deterministic Ed25519 seeds.
- **Negative**: 1 vector in `vectors.json` — "signed event with
  signature stripped → chain still verifies, `signature_status='unsigned'`"
  — proves sidecar decoupling.

## 5. Risk register

| # | Risk | Mitigation |
|---|------|------------|
| R1 | TS `node:crypto` Ed25519 verify differs from Python `cryptography` at edge bytes (leading-zero pubkey, low-order points, S=0) | T7 ships 5 adversarial vectors covering these edges |
| R2 | `proof_bundle.schema.json` additive extension rejected by old verifiers | Schema uses `additionalProperties` permissively; T5 adds backward-compat test using a v0.1.0-alpha verifier reading the new bundle |
| R3 | ADR-0006 `SigstoreRekorAnchor.__init__(signing_key=...)` callers broken | T2 union type `KeyProvider \| Ed25519PrivateKey` + deprecation warning; the old keyword stays for ≥6 months before retirement |
| R4 | TrustRoots YAML loading becomes a new attack surface (path traversal / YAML deserialisation) | `yaml.safe_load` only; trust roots path MUST be passed explicitly (no env-var default); SECURITY.md entry |

## 6. Out of scope (explicitly NOT in ADR-0005)

- HSM / PKCS#11 / Cloud KMS integration (future ADR-0009 draft).
- eIDAS qualified electronic signature (QES) — this scheme is NOT a
  QES; law-firm documents requiring QES must go through an external
  QTSP separately.
- Fulcio / OIDC keyless flow — punted to ADR-0007.
- Key escrow / custody / court disclosure procedures.
- Threshold signing (FROST / Shamir over the signing key).
- Signature-algorithm agility — v1 locks Ed25519; future algorithm
  migration via `schema_version=2` ADR amendment.
- Sigstore Rekor `signedEntryTimestamp` Merkle inclusion proof
  (already noted as deferred in ADR-0006).

## 7. Update protocol

This plan supersedes only the ADR-0005 sketch hinted at in ADR-0003's
"Follow-up ADRs anticipated" section. Revisions to this plan require
an entry at the document tail with date + rationale, never silent
edits — mirrors the `competitive_positioning_upgrade_plan_20260517 §
8` discipline.

### Revisions

- **2026-05-17** — Initial plan from `opus-architect` dispatch after
  Track 2 completion (commit fb0600e).
