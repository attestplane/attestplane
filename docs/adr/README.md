# Architecture Decision Records (ADRs)

This directory contains the Architecture Decision Records for the Attestplane project.

## What is an ADR?

An Architecture Decision Record is a short document that captures a single load-bearing decision: the context that motivated it, the decision itself, and the consequences of accepting it. ADRs are immutable once accepted — superseded decisions become a new ADR that references the old one.

The Attestplane project uses ADRs to document:

- New compliance-framework mappings (EU AI Act, DORA, GDPR, NIS2, CRA, etc.)
- Hash chain algorithm or semantic changes
- Time-stamp authority (TSA) integration approaches
- Security boundary or threat model changes
- Trust assumptions about transparency logs (Rekor, Sigstore)
- License or governance changes that affect downstream consumers
- Public API surface additions or changes

What does *not* require an ADR:

- Bug fixes that restore documented behavior
- Internal refactors that preserve all observable behavior
- Documentation corrections
- Dependency version bumps without behavioral change
- Test additions

## Convention

We use the [Michael Nygard ADR template](https://github.com/joelparkerhenderson/architecture-decision-record/blob/main/locales/en/templates/decision-record-template-by-michael-nygard/index.md). Each ADR is a separate file named `NNNN-short-title.md` where `NNNN` is a four-digit, zero-padded sequence number.

| Field | Required | Notes |
|---|---|---|
| Title | yes | Imperative phrase: "Adopt X", "Replace Y with Z", "Restrict W to ..." |
| Date | yes | ISO-8601 (`YYYY-MM-DD`) |
| Status | yes | `Proposed` / `Accepted` / `Deprecated` / `Superseded by ADR-NNNN` |
| Context | yes | What is motivating this decision — constraints, history, options considered |
| Decision | yes | What we are deciding, in active voice |
| Consequences | yes | What becomes easier or harder, both desirable and undesirable |

A copy of the template lives at [0000-template.md](0000-template.md).

## Lifecycle

1. **Draft.** Author opens a PR with the ADR file in `Proposed` status. PR description should link to the related issue or design discussion.
2. **Review.** Maintainers and any affected stakeholders comment on the PR. Open questions are resolved in the ADR text itself, not in PR comments.
3. **Accept.** When supermajority of maintainers approves (per [GOVERNANCE.md §4.2](../../GOVERNANCE.md)), status flips to `Accepted` in the same PR and merges.
4. **Supersede or deprecate.** A later ADR may supersede this one. Update the original's status to `Superseded by ADR-NNNN` in a separate PR. Do not delete or rewrite accepted ADRs — the historical record matters.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-use-apache-2-0-license.md) | Use Apache License 2.0 as the project license | Accepted |
| [0002](0002-substrate-data-model-and-hash-chain-v0.md) | Substrate core data model and hash chain (v0.0.1) | Accepted |
| [0003](0003-tsa-rfc-3161-anchoring.md) | Time-Stamp Authority anchoring (RFC 3161) for the audit chain | Accepted |

New ADRs append to this table in the same PR that introduces the ADR file.
