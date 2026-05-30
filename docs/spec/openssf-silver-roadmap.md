# OpenSSF Silver Roadmap

This document tracks the gap between current attestation controls and the
[OpenSSF Scorecard](https://securityscorecards.dev/) Silver badge requirements.
Each section below lists a requirement, the degree to which it is met today,
and the planned work to close the gap.

> **Status** — Working document. Updated as controls are added or retired.

## Known gaps

| Silver requirement | Current coverage | Gap | Target |
|---|---|---|---|
| Binary-Artifact Provenance (SLSA Build L3) | SLSA Build L3 provenance published for npm releases via `slsa-provenance.yml` | Covered — no gap | Shipped |
| Cryptographic signing of release artifacts | Keyless release signing (OIDC + Sigstore) for npm | Maintain via `release-cd.yml` | Shipped |
| Dependency-Update Automation | Dependabot or Renovate configured | Covered — no gap | Shipped |
| Fuzzing | Not yet configured | No fuzzing infrastructure | Q3 2026 |
| SAST (static analysis) | CodeQL enabled on PR and push to `main` | Covered — no gap | Shipped |
| Security policy (`SECURITY.md`) | Published | Covered — no gap | Shipped |
| Pinned Dependencies | Action and container-image references pinned by SHA in all workflows | Covered — no gap | Shipped |
| Token Permissions | `contents: read` default with per-step elevation | Covered — no gap | Shipped |

## Post-quantum cryptography (PQC)

Referenced by AT-08 (quantum cryptanalysis) in the compliance traceability
matrix. The current signing scheme (`ecdsa` / P-256) is pre-quantum. A
PQC-migration ADR and key-agility framework are on the long-term roadmap.

## Supply-chain resilience

Referenced by AT-09 (supply-chain compromise) in the compliance traceability
matrix. Pinned manifests, SBOM generation, reproducible builds, and SLSA
provenance provide post-hoc detection of build-time dependency compromise.
