# 0001. Use Apache License 2.0 as the project license

- **Date**: 2026-05-17
- **Status**: Accepted
- **Deciders**: @merchloubna70-dot (founder, sole maintainer at decision time)
- **Related**: [GOVERNANCE.md §6](../../GOVERNANCE.md), [LICENSE](../../LICENSE), [NOTICE](../../NOTICE), Attestplane commercial strategy v1.3 (private)

## Context

Attestplane is a verifiable audit substrate for AI agent systems intended for adoption by EU-regulated entities (DORA, BaFin, NIS2 scope) and US Federal customers (FedRAMP-aspirational from M8). The license decision affects:

- **Adoption.** Regulators, banks, and enterprises evaluating Attestplane will require a license they can route through procurement without dedicated legal review for each clause.
- **Patent exposure.** The hash chain semantics, RFC-3161 anchoring approach, and framework-mapping algorithms are novel implementations. Contributor patent litigation exposure must be limited explicitly.
- **Trademark separation.** The codebase license must not grant rights to the "Attestplane" word mark or the certification mark "Attestplane Certified"; those are held separately by Attestplane Pte. Ltd. and governed by [TRADEMARK.md](../../TRADEMARK.md).
- **Commercial strategy.** The chosen license must permit a proprietary enterprise layer (private repository, separate licensing) without forcing source disclosure of that layer, while keeping the substrate core fully open.
- **Compliance signaling.** EU procurement preferences and the [DORA Regulatory Technical Standards](https://www.eba.europa.eu/) explicitly note that auditable, well-known OSS licenses are acceptable risk profiles; novel or restrictive licenses are not.

Three license families were seriously evaluated.

## Decision

The Attestplane substrate is licensed under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0), without modification. The full canonical text appears in `LICENSE`. Copyright notice and trademark notice are split out into `NOTICE` per Apache convention.

The trademark policy in `TRADEMARK.md` explicitly carves trademarks out of the license grant. The Apache 2.0 grant covers copyright and patent claims in the software; it does not grant rights to use the Attestplane or Attestplane Certified marks.

GOVERNANCE.md §6.1 commits the project to keeping the substrate Apache 2.0 in perpetuity, with a supermajority-vote change procedure intended to be effectively irreversible.

## Consequences

Easier:

- EU enterprise procurement: Apache 2.0 is on every short-list of "no legal review required" licenses.
- Regulator engagement: BaFin, DORA-aligned banks, ENISA review do not flag Apache 2.0 as a risk.
- Contributor onboarding: most companies have pre-approved Apache 2.0 contributions in their CLA-free playbooks.
- Patent retaliation handling: Apache 2.0's patent grant and termination clause give attestplane contributors and downstream consumers a known, tested defense.
- Enterprise-layer monetization: a separate proprietary layer is permitted by Apache 2.0 without requiring source disclosure of that layer.

Harder:

- Cannot ever ship the substrate core itself under a non-OSS license without violating the perpetual Apache 2.0 commitment in GOVERNANCE.md §6.1 (this is intended).
- Strong copyleft contribution (GPL-derived code) cannot be incorporated into the substrate without dual-licensing or removal.
- No "source-available with usage restrictions" carve-out is possible at the substrate layer (BUSL, SSPL, FSL, Elastic License, Confluent Community License were all rejected for this reason).

Follow-up work:

- M5: Add SBOM generation to release process to satisfy CRA 2027 Article 13 supply-chain attestation.
- M5: Add SPDX license identifiers to all source files as they are written.
- M8: Re-evaluate license posture against FedRAMP requirements; expected outcome is "no change needed".

## Alternatives considered

**Business Source License (BSL / BUSL-1.1) with a four-year Apache 2.0 conversion clock.**
Rejected. While BSL preserves more commercial leverage in the short term, every meaningful EU procurement evaluation in 2025-2026 has flagged BSL as an unknown-license risk. The marginal commercial benefit does not outweigh the procurement friction. BSL also conflicts with the AI Act compliance narrative — auditable infrastructure should not change license terms over time.

**MIT License.**
Rejected. MIT lacks the explicit patent grant Apache 2.0 provides. For a project implementing novel hash chain and attestation semantics with patent exposure, the absence of a patent grant is a real liability for downstream adopters. The "shorter is simpler" benefit of MIT is not worth the legal ambiguity.

**Mozilla Public License 2.0 (MPL-2.0).**
Rejected. MPL is file-level copyleft, which complicates the proprietary enterprise layer story (any file touched in both substrate and enterprise contexts becomes contagious). The marginal copyleft protection MPL adds versus Apache 2.0 is not material for our threat model.

**GPL family (GPLv3, AGPLv3).**
Rejected. AGPLv3 would force any SaaS service built on Attestplane (including third-party services and the planned future Attestplane SaaS aggregator) to publish all server-side modifications. This contradicts the commercial strategy of selling a private enterprise layer and SaaS aggregator. GPL also has well-known EU enterprise procurement friction.

## Compliance and audit notes

The license decision itself is documented in this ADR (immutable). License changes would require a new ADR superseding this one, plus the supermajority maintainer vote per GOVERNANCE.md §6.3, plus public notification per the procedure in that section. Prior Attestplane releases would remain governed by their release-time license — Apache 2.0 commits and tags before any change date would not retroactively re-license.

This ADR does not affect existing audit chains; the license under which evidence is produced is metadata, not part of the cryptographic chain.
