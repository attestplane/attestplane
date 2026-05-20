# Attestplane Compatibility Policy

This document defines the wire-format compatibility contract for the
`v0.8.0-rc.1` release-candidate line. It is a release-candidate policy,
not a GA or compliance certification claim.

## Wire-Format Identifiers

Attestplane separates package versions from protocol and schema versions:

| Surface | Identifier | Current value | Compatibility rule |
|---|---|---:|---|
| Chain event schema | `event.schema_version` | `1` | Verifiers must reject unsupported major versions. |
| Proof bundle | `bundle_version` | `1` | Verifiers must reject unsupported bundle versions. |
| Evidence taxonomy | `evidence_taxonomy_version` | `1` | Additive event types require a new conformance vector. |
| Adapter protocol | `AP-EVD/1.0` | `1.0.0` | Fixture shape is frozen for the RC line. |
| Signature sidecar | `signature_schema_version` | `1` | Signature records are additive and optional. |
| Retention proof | retention proof object shape | `v1` | Unknown fields are not accepted by current validators. |

## Release-Candidate Freeze

For `v0.8.0-rc.1` and later `0.8.0-rc.N` releases, the following surfaces
are frozen pending GA:

- Python public imports from `attestplane`.
- TypeScript public exports from `@attestplane/attestplane`.
- Canonical JSON and canonical TEXT byte output.
- Hash-chain event hash computation.
- ProofBundle v1 required fields.
- `VerifyErrorCode` values.
- `AP-EVD/1.0` adapter-conformance fixture shape.

Breaking any frozen surface requires a new release-candidate version, a
changelog entry, and updated conformance fixtures. The project must not
reuse an existing RC version after publication.

## Forward Compatibility

Current verifiers fail closed when they see unsupported required schema
versions. Optional sidecar sections may be absent. Producers that need
future features must emit explicit version fields rather than relying on
implicit interpretation by older verifiers.

Consumers must treat unknown major versions as unsupported. Consumers may
ignore absent optional sidecar sections, but they must not silently accept
malformed sidecar records when those sections are present.

## Version Negotiation

Attestplane does not provide runtime negotiation in the SDKs yet. The
negotiation contract for RC1 is out-of-band:

1. Producer declares package version and wire-format identifiers in release
   notes or integration metadata.
2. Consumer checks the identifiers against its supported set before replay.
3. Consumer fails closed on unsupported major versions or missing required
   fields.

Runtime negotiation is a GA-adjacent feature and must land under a later ADR
if it becomes part of the public API.

## Non-Claims

This compatibility policy does not claim production readiness, legal
admissibility, compliance certification, FIPS/Common Criteria status, SLSA
level beyond published evidence, or LTS support.
