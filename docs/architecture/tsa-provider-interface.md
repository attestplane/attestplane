<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# TSA Provider Interface Boundary

## Status

Accepted alpha boundary for `v0.0.5-alpha`.

## Decision

Attestplane keeps timestamp authority access behind provider interfaces:

- Python: `TSAProvider`, `MockTSAProvider`, `MultiTSAProvider`
- TypeScript: matching `TSAProvider`, `MockTSAProvider`, `MultiTSAProvider`

The provider interface is a source abstraction. It is not a new trust root. A
verifier must still validate timestamp material against declared trust roots
when anchor verification is requested.

## Safe Claims

- "TSA source selection is pluggable."
- "The mock provider supports deterministic tests."
- "The provider interface does not make a timestamp legally qualified."

## Non-Claims

- No eIDAS qualified timestamp claim.
- No long-term archival trust guarantee.
- No hosted TSA trust-root claim.
- No production supply-chain certification claim.

## Rationale

Keeping source selection pluggable lets tests and offline users remain
deterministic while avoiding hard-coding a single commercial timestamp service
into the verifier surface. The verifier remains responsible for fail-closed
material checks.
