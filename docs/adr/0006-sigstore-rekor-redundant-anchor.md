# 0006. Sigstore Rekor as a redundant transparency-log anchor

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer at decision time)
- **Related**: [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0003](0003-tsa-rfc-3161-anchoring.md), [ADR-0008](0008-evidence-event-taxonomy-v1.md), [`competitive_positioning_upgrade_plan_20260517.md`](../architecture/competitive_positioning_upgrade_plan_20260517.md) Track 2, [Sigstore Rekor v2](https://docs.sigstore.dev/logging/overview/), [DSSE](https://github.com/secure-systems-lab/dsse), [in-toto Attestation v1](https://github.com/in-toto/attestation)

## Context

[ADR-0003](0003-tsa-rfc-3161-anchoring.md) locked RFC-3161 Time-Stamp
Authority anchoring as the v0.1 design, with FreeTSA and DigiCert as the
default providers and `MultiTSAProvider` recommending plurality (≥ 2
independent TSAs). The competitive research session of 2026-05-17 (see
the linked upgrade plan) identified Sigstore Rekor as the dominant
ecosystem transparency-log primitive: PyPI, npm, Homebrew, Maven
Central, NVIDIA NGC, and most modern OSS supply-chain tooling already
publish to Rekor, and `cosign verify` / `slsa-verifier` consume the
resulting LogEntry as canonical evidence.

A redundant Sigstore anchor closes three gaps:

1. **Public verifiability without trust roots.** RFC-3161 requires the
   verifier to obtain TSA-specific root certificates (from the TSA's
   own publication site, from an eIDAS Trusted List, or out of band).
   Rekor's signing key is widely known and embedded in `cosign`,
   `rekor-cli`, `slsa-verifier`, and the broader Sigstore client
   ecosystem. A consumer who already has those tools installed can
   verify an Attestplane chain anchored to Rekor with no additional
   trust setup.
2. **Free public log with high availability.** FreeTSA has no SLA;
   DigiCert costs money. Sigstore Rekor is free for OSS use and
   operated by the Linux Foundation with public uptime monitoring. A
   plurality deployment (Rekor + RFC-3161 TSA) is cheaper and more
   resilient than two RFC-3161 TSAs.
3. **Native fit for Attestplane's in-toto/DSSE wire format.** [ADR-0008
   Track 1](../architecture/competitive_positioning_upgrade_plan_20260517.md)
   ships `proof_bundle_to_in_toto_statement()` + DSSE envelope
   serialization. Rekor's `intoto` entry type accepts exactly this
   shape; the integration is mechanical rather than semantically novel.

## Decision

### 1. Add `SigstoreRekorAnchor` as a sibling of the RFC-3161 providers

`attestplane.anchoring.sigstore.SigstoreRekorAnchor` extends
:class:`~attestplane.anchoring.TSAProvider` and produces an
:class:`~attestplane.anchoring.AnchorRecord` whose semantics are
"Rekor-flavoured" rather than RFC-3161-flavoured. The
`AnchorRecord` byte shape is preserved (no v2 schema bump); the
`tsa_provider_id` carries the prefix `sigstore.rekor:` and the
verifier dispatches to a separate code path when it sees that prefix.

Rationale for not bumping `anchor_schema_version`:

- The v0.0.2-alpha chain + anchor wire shape is already in
  conformance fixtures and downstream tooling. Bumping for a new
  provider would force every consumer to handle two schemas.
- The `AnchorRecord.tsa_cert_chain` and `ocsp_responses` fields are
  semantically generic ("frozen credentials at issuance"); the
  Sigstore mapping reuses them with documented Sigstore-specific
  meaning (see § 3).

### 2. Use Rekor's `intoto` entry type

The Sigstore Rekor anchor submits a DSSE-wrapped Attestplane in-toto
Statement (produced via `proof_bundle_to_in_toto_statement()` +
`statement_to_dsse_envelope()` from [Track 1](../architecture/competitive_positioning_upgrade_plan_20260517.md))
as a Rekor `intoto` log entry. This is the same entry type that
SLSA Provenance and cosign attestation flows use, so downstream
tooling already understands the response.

### 3. Field mapping from Rekor LogEntry to AnchorRecord

| `AnchorRecord` field | Sigstore Rekor source |
|---|---|
| `tsa_provider_id` | `"sigstore.rekor:<log_id>"`, e.g. `"sigstore.rekor:c0d23d6ad406973f"` for the public log |
| `tsa_token` | JSON bytes of the full Rekor LogEntry response (including `logIndex`, `logID`, `body`, `integratedTime`, `verification.signedEntryTimestamp`, `verification.inclusionProof`) |
| `tsa_cert_chain` | A 1-tuple containing the Rekor public key in DER (Ed25519 in the public Sigstore instance; ECDSA on private deployments) |
| `ocsp_responses` | A 1-tuple containing the synthetic marker `b"SIGSTORE-REKOR-NO-OCSP-APPLIES"`. Rekor does not use X.509 PKI, so OCSP is inapplicable. |
| `anchored_seq` | Per-substrate chain seq, set by the Anchorer worker. |
| `anchored_event_hash` | The chain head's `event_hash`, identical to the RFC-3161 path. |
| `issued_at_claimed` | The Rekor `integratedTime` (UNIX seconds → UTC datetime). |

The verifier dispatches by `tsa_provider_id` prefix. When the prefix is
`sigstore.rekor:` the verifier:

1. Skips RFC-3161 ASN.1 parsing.
2. Parses the JSON LogEntry in `tsa_token`.
3. Verifies the `signedEntryTimestamp` signature against the
   `tsa_cert_chain[0]` Rekor public key.
4. Verifies that the entry's `body` payload digest matches
   `anchored_event_hash`.
5. Skips the OCSP path entirely (`ocsp_responses` marker recognised).

### 4. Bring-your-own-key signing for v0.1

The Sigstore canonical flow uses Fulcio-issued short-lived OIDC
certificates for keyless signing. v0.1 does **not** integrate Fulcio
because:

- Fulcio requires an OIDC identity provider; this is a substantial
  runtime dependency that the substrate is structurally trying to
  avoid.
- The Attestplane substrate already produces verifiable hash chains;
  Rekor's value here is the *transparency log*, not the keyless
  signing layer.
- Future ADR-0005 (event signing scheme; deferred) will formalise the
  per-substrate Ed25519 keypair; Fulcio integration becomes a thin
  layer on top of that decision and properly belongs in ADR-0005 or a
  successor.

The v0.1 SDK submits Rekor entries signed with a substrate-provided
Ed25519 keypair (`SigstoreRekorAnchor.__init__(signing_key=...)`).
Callers either generate the keypair once per deployment (recommended)
or pass `None` to use an ephemeral key (suitable for tests and
substrate-local-only verification).

#### 4.1. Amendment (2026-05-17) — coexistence with ADR-0005 event signing

[ADR-0005](0005-event-signing-scheme.md) ships the formal event-signing
scheme. Both ADRs introduce Ed25519 keys, with distinct roles. The
amendment locks how they coexist in a single `ProofBundle`:

| Field | Role | Key source | Verification |
|---|---|---|---|
| `ProofBundle.anchor_records[].tsa_token` (Rekor) | Submits the chain head to a transparency log; the log's signature attests **inclusion + time** | Rekor's *own* signing key (Sigstore / private Rekor instance) | Rekor public key (embedded in `cosign` / `slsa-verifier`) |
| `SigstoreRekorAnchor`'s `signing_key=` constructor argument | Signs the submission payload that Rekor stores; allows an organisation to bind the Rekor entry to its identity | Substrate operator's *Rekor-submission* key (often a separate key per deployment) | Operator publishes the corresponding pubkey out-of-band |
| `ProofBundle.signatures[].signature` (ADR-0005) | Signs `canonicalize(AuditEvent)` or the 5-key segment-head payload to bind individual events to the substrate operator | `KeyProvider`-supplied operator key (`InMemoryKeyProvider` / `FileKeyProvider` / `EnvKeyProvider` / `MultiSignerProvider`) | `TrustRoots` lookup by `key_id`, RFC 8410 SPKI |

Two design points the amendment locks:

1. **`SigstoreRekorAnchor`'s submission key MAY but NEED NOT be the
   same key supplied to ADR-0005's `KeyProvider`.** They are
   independent. A deployer who already has a Sigstore-bound key may
   reuse it as the substrate's signing key; a deployer who prefers
   separation of duties uses two distinct keys. The SDK does not
   enforce either policy.
2. **`SignatureRecord.signing_cert_chain` is reserved for the Fulcio
   path (see ADR-0005 § 9 + the anticipated ADR-0007).** When
   `SigstoreRekorAnchor` is given a Fulcio-issued short-lived
   certificate, that certificate populates `signing_cert_chain` on the
   *signature record*, and the Rekor log entry's `body.spec.publicKey`
   field references the *same* cert. The two layers will be linked
   when ADR-0007 lands; v1 leaves both layers ungated.

Plurality (§ 5 below) extends naturally to event signing:
`MultiSignerProvider` (ADR-0005 § 4) and `MultiTSAProvider`
(ADR-0003 § 2) compose independently. A deployer may run:

- N signing keys via `MultiSignerProvider`
- M anchor providers via `MultiTSAProvider` (mix of RFC-3161 TSAs + Sigstore Rekor)

and the resulting `ProofBundle` carries up to `len(events) × N`
signature records and up to `len(events) × M` anchor records, all
verifiable independently. The verifier accepts any single valid
signature per seq as evidence of operator binding (plurality priority,
ADR-0005 § 7) and any single valid anchor as evidence of temporal
binding (existing ADR-0003 + ADR-0006 § 5 semantics).

### 5. Plurality recommendation generalises

[ADR-0003 § 2](0003-tsa-rfc-3161-anchoring.md) recommended ≥ 2 RFC-3161
TSAs. ADR-0006 generalises this to ≥ 2 independent anchor providers
where "independent" can mean (a) two RFC-3161 TSAs, (b) one RFC-3161
TSA + Rekor, or (c) two Sigstore Rekor instances (e.g. public Sigstore
plus a private organisational Rekor). `MultiTSAProvider` already accepts
heterogeneous providers; no API change needed.

The recommended v0.1 default deployment becomes:

- **FreeTSA + Sigstore Rekor public** for OSS / dev / self-host (both free).
- **DigiCert + Sigstore Rekor public** for commercial deployments
  (paid TSA SLA + free public transparency log).

### 6. No live network calls in CI

Following the same discipline as ADR-0003 § 4 and the
[nightly-anchor workflow](../runbooks/nightly-anchor.md):

- Pre-merge tests use `TestRekorAuthority` (an in-tree synthetic Rekor
  signing key + recorded entries via `RecordedHttpTransport`-style
  replay).
- Live Sigstore Rekor verification is exercised by a separate nightly
  workflow (`.github/workflows/nightly-anchor.yml` will be extended in
  a follow-up to include both FreeTSA and Rekor; not blocking this
  ADR's acceptance).

## Consequences

### Positive

- Downstream tooling that already speaks Sigstore (`cosign verify`,
  `slsa-verifier`, GUAC ingestion) can validate Attestplane chains
  with zero additional trust-root setup.
- Free public transparency log adds redundancy to RFC-3161
  anchoring at no cost.
- Native fit with the Track 1 in-toto / DSSE wire format produced by
  `proof_bundle_to_in_toto_statement()` — Rekor's `intoto` entry
  type accepts exactly this shape.
- The "SLSA-for-AI-Agents" positioning (per
  `competitive_positioning_upgrade_plan_20260517.md` § 2) becomes
  technically grounded: Attestplane evidence lives in the same
  transparency log Linux Foundation already operates for the
  software-supply-chain community.

### Negative

- AnchorRecord fields `tsa_cert_chain` and `ocsp_responses` carry
  Sigstore-specific repurposed meanings (Rekor pubkey + synthetic
  OCSP marker). Documentation cost on every code review where someone
  unfamiliar reads the field names and assumes X.509 semantics.
- The verifier now has two code paths (RFC-3161 ASN.1 vs Rekor JSON)
  dispatched by `tsa_provider_id` prefix; adding a third anchor kind
  in future warrants reconsidering with an `anchor_kind` discriminator
  field at that point.
- Sigstore Rekor's signing keys rotate periodically (per their public
  rotation policy). Long-term LTV is weaker than RFC-3161 + CAdES-A:
  Rekor's *historical* SETs continue to verify because the old key is
  retained, but operators may need to update their pinned Rekor
  public keys at rotation time. ADR-0007 (retention / re-anchoring;
  anticipated) will address this.
- Bringing your own key for v0.1 means the Sigstore "OIDC-bound
  identity" benefit is missed. ADR-0005 (event signing scheme) is the
  proper venue to layer Fulcio in later.

### Risks accepted

- Sigstore Rekor public infrastructure is operated by the Linux
  Foundation; a substrate that depends on it inherits LF's operational
  posture. Mitigated by the plurality recommendation: RFC-3161 +
  Rekor means the chain remains verifiable even if Rekor is offline
  for an extended period.
- "Sigstore-bundle compatible" claim per
  [`allowed_claims.md`](../policy/allowed_claims.md) § v0.0.2-alpha
  becomes truthful only after the v0.0.2-alpha ships with
  `SigstoreRekorAnchor` and `bundle_to_dsse_envelope`. Until then the
  claim must be paired with the milestone qualifier (`v0.1 / M5`).

### Reversibility

- The Sigstore Rekor anchor is **additive**: existing v0.0.2-alpha
  chains continue to verify under the RFC-3161-only path. Removing
  this anchor in a future version is reversible — anchors previously
  produced with `SigstoreRekorAnchor` would simply lose verification
  capability without breaking the underlying chain hashes.
- Promoting `SigstoreRekorAnchor` from optional to required would
  require a new ADR and is **not** part of v0.1 / M5 scope.

## Alternatives considered

### A. Skip Rekor for v0.1; ship only RFC-3161

Rejected. Track 2 of the competitive positioning upgrade plan
explicitly funds this work to close the public-verifiability gap
identified in the 20-agent research. Postponing means the
"SLSA-for-AI-Agents" framing remains aspirational on the wire-format
side until the next milestone.

### B. Bump `anchor_schema_version` to 2; add native Rekor fields

Considered. Would yield a cleaner separation: `RekorAnchorRecord` with
`log_index`, `log_id`, `signed_entry_timestamp`, `inclusion_proof` as
top-level fields rather than overloading `tsa_cert_chain` etc.
Rejected for v0.1 because:

- v0.0.2-alpha's anchor shape is already frozen in
  `anchor_vectors.json` and downstream tooling.
- Two schemas force every consumer to branch.
- The Sigstore-mapping convention in § 3 is compact and documented
  in this ADR; the marginal cleanliness gain doesn't justify the
  breaking change.

A future v2 anchor schema may revisit this when a third anchor kind
(e.g., Ethereum / OpenTimestamps) lands.

### C. Use Rekor's `hashedrekord` entry type instead of `intoto`

Considered. `hashedrekord` is simpler (just a signed hash). Rejected
because:

- Track 1 already ships in-toto Statement serialization.
- `intoto` entries integrate with `cosign verify-attestation` and
  `slsa-verifier` natively; `hashedrekord` would need a separate
  verification flow.
- The in-toto entry's `predicateType` field carries the Attestplane
  predicate URL, identifying the entry as Attestplane evidence to
  Rekor browsers.

### D. Fulcio + OIDC keyless signing in v0.1

Rejected. Adding OIDC dependency to a substrate is a substantial
runtime requirement that the project structurally tries to avoid.
Future ADR-0005 (event signing scheme) is the proper venue.

## Compliance and audit notes

- **EU AI Act Art. 12(1)** — Rekor's append-only log + public
  transparency provide an additional integrity layer beyond the
  substrate's internal chain. Auditors familiar with SLSA / supply
  chain attestation will recognise the format and can verify with
  existing tooling.
- **DORA Art. 8** — redundant anchor reduces single-point-of-failure
  risk in the ICT-related audit trail (the regulator's concern is
  that audit evidence remains verifiable years after an incident).
- **eIDAS qualified time-stamping** — Sigstore Rekor is **not** an
  eIDAS qualified trust service. RFC-3161 anchors via qualified TSAs
  (per ADR-0003 § 6 and the eIDAS Trusted List loader shipped at
  commit `2ad7162`) remain the path to qualified-trust-service-level
  evidence. The recommended deployment has both: qualified RFC-3161
  TSA for the EU regulatory baseline + Sigstore Rekor for the global
  transparency-log baseline.
- **GDPR Art. 5(1)(c) data minimization** — preserved: Rekor entries
  contain only hashes and metadata, never raw event content.

## Follow-up ADRs anticipated

- **ADR-0005 (Event signing scheme)** — Ed25519 per-substrate keypair;
  Sigstore Rekor anchors will adopt the same key for signing entries,
  removing the v0.1 "bring-your-own-key" caveat.
- **ADR-0007 (Retention / re-anchoring)** — addresses Rekor signing
  key rotation and long-term anchor verifiability.
- **Future ADR (Anchor schema v2)** — if a third heterogeneous anchor
  kind ships, introduce an `anchor_kind` discriminator and migrate
  Rekor entries to native fields.
