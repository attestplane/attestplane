<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Documentation Index

This is the stable user-facing entrypoint for Attestplane documentation.
It groups the material that most people look for first: governance,
security, compliance and specs, quickstart guidance, and API references.

This index is linted by `scripts/docs/check_index.py`. If you add a new
user-facing document in one of the sections below, add it here at the same
time.

## Start Here

| Document | Purpose |
|---|---|
| [README.md](../README.md) | Project overview and release posture |
| [docs/quickstart.md](quickstart.md) | Five-minute evaluation walkthrough |
| [docs/non-goals.md](non-goals.md) | Explicit non-goals and anti-claims |
| [CHANGELOG.md](../CHANGELOG.md) | Release history and published evidence |

## Governance

| Document | Purpose |
|---|---|
| [GOVERNANCE.md](../GOVERNANCE.md) | Decision process, maintainer roles, and update policy |
| [MAINTAINERS.md](../MAINTAINERS.md) | Maintainer roster, succession, and area ownership |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Contribution workflow and DCO sign-off |
| [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) | Community standards and enforcement |
| [TRADEMARK.md](../TRADEMARK.md) | Trademark policy and permitted use |
| [docs/governance/conflict-resolution.md](governance/conflict-resolution.md) | Governance dispute handling |
| [docs/governance/reviewer-tier.md](governance/reviewer-tier.md) | Reviewer-tier specification |

## Security

| Document | Purpose |
|---|---|
| [SECURITY.md](../SECURITY.md) | Vulnerability disclosure policy |
| [SECURITY_zh.md](../SECURITY_zh.md) | Chinese-language security policy mirror |
| [docs/security/gpg-key-rotation-playbook.md](security/gpg-key-rotation-playbook.md) | Security key publication workflow |
| [docs/security/release-signing.md](security/release-signing.md) | Release-signing posture and interim controls |
| [docs/security/threat-model-v0.0.5-alpha.md](security/threat-model-v0.0.5-alpha.md) | Early threat-model snapshot |
| [docs/security/threat-model-v1.md](security/threat-model-v1.md) | Current threat-model and assurance case |
| [docs/security/openssf-best-practices.md](security/openssf-best-practices.md) | OpenSSF best-practices mirror |
| [docs/security/openssf-silver-roadmap.md](security/openssf-silver-roadmap.md) | OpenSSF Silver readiness roadmap |
| [docs/security/openssf-scorecard-publication.md](security/openssf-scorecard-publication.md) | OpenSSF Scorecard publication notes |
| [docs/security/mitre-cna-application.md](security/mitre-cna-application.md) | MITRE CNA application notes |
| [docs/security/reproducible-builds-submission.md](security/reproducible-builds-submission.md) | Reproducible-builds submission notes |

## Compliance and Specs

| Document | Purpose |
|---|---|
| [docs/adr/README.md](adr/README.md) | Architecture decision record index |
| [docs/architecture/ATTESTATION_GATES.md](architecture/ATTESTATION_GATES.md) | Core attestation gates |
| [docs/architecture/verifier_independence.md](architecture/verifier_independence.md) | Independent verifier trust model |
| [docs/errors.md](errors.md) | Stable verifier error taxonomy |
| [docs/policy/allowed_claims.md](policy/allowed_claims.md) | Approved public claims |
| [docs/policy/claims_policy.md](policy/claims_policy.md) | Claim-review policy |
| [docs/policy/forbidden_claims.md](policy/forbidden_claims.md) | Claims that must not be made |
| [docs/release/verifying-signatures.md](release/verifying-signatures.md) | Release-artifact verification recipe |
| [docs/release/ga-ca-cut-criteria.md](release/ga-ca-cut-criteria.md) | GA / CA release cut criteria |
| [docs/release/npm-dist-tag-policy.md](release/npm-dist-tag-policy.md) | npm dist-tag policy |
| [docs/roadmap/USER_ROADMAP.md](roadmap/USER_ROADMAP.md) | Public roadmap and milestones |
| [docs/spec/aia-12-aligned-profile.md](spec/aia-12-aligned-profile.md) | AIA-12 aligned evidence profile |
| [docs/spec/canonical-json-v1.md](spec/canonical-json-v1.md) | Canonical JSON v1 spec |
| [docs/spec/canonical-text-v1.md](spec/canonical-text-v1.md) | Canonical TEXT v1 spec |
| [docs/spec/compat.md](spec/compat.md) | Compatibility policy |
| [docs/spec/evidence-event-taxonomy-v1.md](spec/evidence-event-taxonomy-v1.md) | Evidence-event taxonomy |
| [docs/spec/gdpr-articles-5-22-30-mapping.md](spec/gdpr-articles-5-22-30-mapping.md) | GDPR article mapping |
| [docs/spec/iso-iec-42001-aims-mapping.md](spec/iso-iec-42001-aims-mapping.md) | ISO/IEC 42001 mapping |
| [docs/spec/nist-ai-rmf-1.0-mapping.md](spec/nist-ai-rmf-1.0-mapping.md) | NIST AI RMF mapping |

## API References

| Document | Purpose |
|---|---|
| [api/public/README.md](../api/public/README.md) | Public API manifest gate |
| [sdk/python/README.md](../sdk/python/README.md) | Python SDK documentation |
| [sdk/typescript/README.md](../sdk/typescript/README.md) | TypeScript SDK documentation |
| [docs/contributor/api-reference.md](contributor/api-reference.md) | Contributor-facing API reference notes |
| [docs/schema/verify-json.md](schema/verify-json.md) | JSON verify schema guide |
| [docs/usage/cli_proofbundle_verifier_alpha.md](usage/cli_proofbundle_verifier_alpha.md) | CLI ProofBundle verifier usage |
| [storage/compat/README.md](../storage/compat/README.md) | Storage compatibility reference |
| [tests/conformance/README.md](../tests/conformance/README.md) | Conformance test documentation |
| [tests/cross_sdk/README.md](../tests/cross_sdk/README.md) | Cross-SDK test documentation |
| [release/alpha-train/README.md](../release/alpha-train/README.md) | Local release-train documentation |
| [scripts/local_codex_runner/README.md](../scripts/local_codex_runner/README.md) | Local Codex runner documentation |

## Not Indexed Here

Validation reports, release-note drafts, and other transient audit
artifacts are intentionally excluded from this index. They stay under
`docs/validation/` and `docs/release-notes/` and are not part of the
stable user-facing navigation surface.
