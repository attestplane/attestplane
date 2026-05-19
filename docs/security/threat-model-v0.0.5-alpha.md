<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# v0.0.5-alpha Threat Model Snapshot

## Scope

This snapshot covers the open-source verifier and proof-bundle surfaces in
`v0.0.5-alpha`. It does not cover a hosted Attestplane service, customer
sidecar stores, customer retention policies, or production deployment controls.

## Trust Root

The verifier trust root remains:

```text
open verifier + versioned schemas + exported evidence bytes + declared trust roots
```

Hosted APIs, dashboards, or release pages are retrieval conveniences only.

## Main Threats

| Threat | Current mitigation |
|---|---|
| Bundle tampering | Recompute chain hashes, metadata closure, artifact hash checks. |
| Policy trace forgery | `policy_trace_refs` must match policy events in chain order. |
| Retention proof forgery | `retention_proofs` must be shaped and reference bundle events. |
| Error handling ambiguity | `VERIFY_*` taxonomy provides stable machine-readable outcomes. |
| Closed verifier dependency | Python and TypeScript verifiers run offline with cross-language fixtures. |
| Over-claiming compliance | README, release notes, and policy docs preserve alpha/no-go claims. |

## Explicit Non-Claims

- No EU AI Act compliance claim.
- No GDPR compliance claim.
- No legal sufficiency claim for retention or deletion requests.
- No production readiness claim.
- No hosted API trust-root claim.
- No SLSA L3 or production-grade supply-chain claim.

## Remaining Limitations

- Retention/deletion proof markers are reference checks, not legal proof.
- Release signatures and SBOM assets improve package review but are not a full
  production supply-chain program.
- RFC-3161 and signature verification remain explicit opt-in verifier paths,
  not default certification.
