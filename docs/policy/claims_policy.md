<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Claims Policy

This document defines how Attestplane controls public-facing claims about
the project's capabilities. It is the enforcement counterpart of
[`forbidden_claims.md`](forbidden_claims.md) and
[`allowed_claims.md`](allowed_claims.md).

## Scope

"Public-facing claim" means any human-readable statement about what
Attestplane *is* or *does*, appearing in:

- `README.md` at the repository root
- `sdk/*/README.md`
- Release notes on GitHub Releases
- `CHANGELOG.md`
- Marketing copy on `attestplane.io`, `attestplane.com`, social posts,
  conference slides, blog posts attributed to the project
- npm package description (`package.json`'s `description` field) and PyPI
  long description
- ADR commentary intended for external readers
- Customer-facing communications produced under the Attestplane name

It does **not** include private business strategy documents (under
`~/Documents/attestplane-business/`), pre-merge ADR drafts, or internal
notes.

## Three-tier rule

### Tier 1 — Permitted phrasings (no review required)

The set listed in [`allowed_claims.md`](allowed_claims.md). Authors may
copy this language verbatim or with minor stylistic edits.

### Tier 2 — Conditional phrasings (require milestone qualifier)

Forward-looking design claims must include the milestone qualifier
("M5", "M6", "M7", "M8+") and a link to the corresponding ADR or
roadmap entry. Example:

> "Designed for RFC-3161 anchoring (ships v0.1 / M5; see ADR-0003)."

### Tier 3 — Forbidden phrasings (do not use)

The set listed in [`forbidden_claims.md`](forbidden_claims.md). These
must not appear in any artifact in the scope above.

## Enforcement

### Pre-merge

Every pull request that modifies a file in the scope above triggers a
documentation review. The reviewer (default: `@merchloubna70-dot` via
CODEOWNERS) confirms:

1. No new Tier-3 phrasing introduced.
2. Tier-2 phrasings carry the milestone qualifier.
3. Tier-1 claims have at least one of: shipped code, CI test, accepted
   ADR, or published artifact.

The PR template (`.github/pull_request_template.md`) prompts the author
to assert compliance with this policy. Reviewers may reject a PR solely
on policy violation.

### CI gate

`scripts/check-policy.sh` (run by the `ci` workflow's "Project policy
invariants" job) scans the diff for terminology listed in
[`forbidden_claims.md`](forbidden_claims.md). If a forbidden term is added
on a tracked path, the job fails and the PR is blocked.

The forbidden-term regex is conservative: it allows the term to appear
inside backticks, quoted negative examples, or this policy document
itself. It rejects bare unquoted use.

### Post-merge revision

If a forbidden claim is discovered after merge:

1. Open a P0 issue tagged `claim-safety`.
2. Open a corrective PR that removes or rephrases the claim within 24 h.
3. Record the incident in the next release notes ("documentation
   correction" section).

## Authority

The founder, as the sole maintainer, is the final arbiter of claim
classification at v0.0.1-alpha. When the maintainer team grows past one,
this section will be replaced with a `claims-review` group decision rule
documented in `GOVERNANCE.md`.

Disagreements about classification are resolved by replacing the disputed
claim with the most conservative permitted variant available, pending
maintainer review.

## Why this exists

The project's positioning as **lawyer-founded regulatory substrate**
creates an asymmetric risk: an inflated public claim made today may be
cited months or years later by a customer, regulator, or adverse counsel
in a dispute. Suppressing the inflated claim once it is in the public
record is much harder than refusing to make it in the first place.

This policy makes the founder's review discipline explicit and
auditable. The PR template, the CI gate, and this document together
constitute the audit trail that the founder *did* exercise the
appropriate care.
