# 0016. Freeze public SDK and wire-format surfaces for the v0.8 RC line

- **Date**: 2026-05-20
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot
- **Related**: [ADR-0002](0002-substrate-data-model-and-hash-chain-v0.md), [ADR-0010](0010-verification-reason-codes.md), [ADR-0014](0014-adapter-conformance-fixture-pinning.md), [compatibility policy](../spec/compat.md)

## Context

Attestplane `v0.8.0-beta.0` is published to PyPI and npm, registry-installed
verifier conformance passes in both SDKs, and cross-SDK round-trip checks pass.
The next pre-GA step is a release-candidate line. A release candidate changes
the public commitment: consumers can begin integration and staging work against
a stable surface, but the project must still avoid GA and production-readiness
claims.

The load-bearing compatibility surfaces are not just package names. They
include canonical byte output, hash-chain semantics, proof-bundle shape,
verification reason codes, and adapter-conformance fixtures. If any of these
move silently during the RC line, downstream integrators cannot evaluate
attestation evidence reliably.

## Decision

The `v0.8.0-rc.N` line freezes these surfaces pending GA:

- Python imports exported from `attestplane`.
- TypeScript exports from `@attestplane/attestplane`.
- Canonical JSON and canonical TEXT byte output.
- Hash-chain event hash computation.
- ProofBundle v1 required fields and metadata closure rules.
- `VerifyErrorCode` string values.
- `AP-EVD/1.0` adapter-conformance fixture shape.
- Registry release process: RC npm packages publish under the `rc` dist-tag;
  `latest` may only point to a pre-release by explicit maintainer decision
  recorded in release notes.

Breaking any frozen surface requires:

1. A new `v0.8.0-rc.N+1` release.
2. A changelog entry explaining the break.
3. Updated conformance fixtures and fixture hashes.
4. Registry-installed verifier-conformance and cross-SDK round-trip evidence.

Existing RC versions must not be retagged or republished.

## Consequences

Downstream integrators get a stable staging target before GA. The project gets
a narrow path to fix RC defects without pretending the beta line was already
GA.

The project must maintain stronger release discipline: API drift must be
intentional, documented, and tested through cross-SDK conformance. Some
otherwise-local cleanups now require an RC bump if they affect public exports
or wire-format bytes.

This ADR does not claim production readiness, legal admissibility, compliance
certification, or LTS support. Those remain GA-blocking decisions.
