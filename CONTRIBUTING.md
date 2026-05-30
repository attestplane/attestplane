# Contributing to Attestplane

**Languages:** [English](CONTRIBUTING.md) | [中文](CONTRIBUTING_zh.md)

Attestplane is an **Open Trust Substrate** for AI Agents: a compliance foundation
centered on a cryptographic audit chain, with framework mappings for the EU AI
Act, NIST AI RMF, ISO 42001, and SOC 2. This project is licensed under Apache
License 2.0 and uses the DCO (Developer Certificate of Origin), not a CLA, as
its contributor agreement. Substantive contributions of all kinds are welcome.
Project governance and trademark-use rules are documented in
[`GOVERNANCE.md`](GOVERNANCE.md) and [`TRADEMARK.md`](TRADEMARK.md).

---

## 1. DCO Sign-off Requirement

This project uses **Developer Certificate of Origin 1.1** (DCO), not a CLA.
Every commit must include a sign-off line showing that you have read and certify
the version 1.1 terms in [`DCO.txt`](DCO.txt).

```bash
git commit -s -m "feat(sdk/python): add JCS canonicalization helper"
# -s automatically appends: Signed-off-by: Your Name <you@example.com>
```

If you forgot to sign off, you can add sign-offs to the last N commits with:

```bash
git rebase HEAD~N --signoff
```

**Before opening a PR, confirm that every commit has a `Signed-off-by:` line;
PRs without sign-off will not be merged.**

The full DCO text is available in the repository root at [`DCO.txt`](DCO.txt),
which contains the standard DCO 1.1 text.

## Release Boundary

Package publication must go through the GitHub Actions CD path documented in
[`docs/runbooks/github-cd-release.md`](docs/runbooks/github-cd-release.md).
Do not publish Attestplane packages from a local machine with `npm publish`,
`twine upload`, direct PyPI upload commands, or ad-hoc registry scripts.

Local release work is limited to preparing code and docs, running gates,
committing, pushing, creating an intentional release tag, dispatching the CD
workflow, and verifying registry state.

---

## Your first contribution

New here? Welcome. We aim to make the contribution path as low-friction as
possible while keeping the audit-chain discipline this project depends on.

- Read the worked end-to-end example in
  [`docs/contributor/first-pr-walkthrough.md`](docs/contributor/first-pr-walkthrough.md).
  It reconstructs a real merged PR (PR #32, the SLSA generator tag-ref fix)
  step-by-step from branch creation through merge, and is the canonical
  reference for the "small fix with proper discipline" shape.
- Browse newcomer-friendly work under the
  [`good first issue`](https://github.com/attestplane/attestplanelabels/good%20first%20issue)
  label.
- The full label schema lives at
  [`.github/labels.yml`](.github/labels.yml) — it is the canonical source.
- Stuck? Comment on the issue, open a draft PR with a question in the
  description, or start a
  [GitHub Discussion](https://github.com/attestplane/attestplanediscussions).
- **Security issues do not go through public issues.** Follow
  [`SECURITY.md`](SECURITY.md) and use the private channels documented
  there.

---

## 2. Local Dev Setup

### Prerequisites

| Tool | Minimum version |
| ---- | --------------- |
| Python | 3.11+ |
| Node.js + npm | 20+ |

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/attestplane/attestplane.git
cd attestplane

# 2. Python SDK
pip install -e "sdk/python[dev]"
pytest sdk/python/

# 3. TypeScript SDK (FastAPI / Express / NestJS helper)
cd sdk/typescript && npm install && npm test
```

The complete runbook for the database, TSA sidecar, and local Rekor instance
will be provided in `docs/runbooks/LOCAL_DEV.md` before M5.

---

## 3. PR Workflow

### Branch naming

```text
feature/<short-description>    # new feature
fix/<short-description>        # bug fix
docs/<short-description>       # documentation change
refactor/<short-description>   # refactor without behavior changes
test/<short-description>       # test-only addition
```

Examples: `feature/rfc3161-anchor-retry` and `fix/blake3-chain-off-by-one`.

### Conventional Commits

Use the [Conventional Commits](https://www.conventionalcommits.org/) format:

```text
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
Signed-off-by: Your Name <you@example.com>
```

Common types: `feat` / `fix` / `test` / `docs` / `refactor` / `chore` /
`perf`.

The scope should match the SDK or package name, such as
`feat(sdk/python)`, `fix(sdk/typescript)`, or `docs(adr)`.

### Development rhythm

Follow a **red -> green -> refactor -> commit** TDD rhythm:

1. **Red**: write a failing test first to make the behavior contract explicit.
2. **Green**: write the smallest implementation that makes the test pass.
3. **Refactor**: clean up the code while keeping the tests green.
4. **Commit**: make one commit for each logical unit, recording a complete
   "red -> green -> refactor" unit.

Keep PRs small and focused. A single PR should do one thing so it is easier to
review and bisect.

---

## 4. PR Checklist

- [ ] `pytest sdk/python/` passes
- [ ] `npm test` for the TypeScript SDK passes
- [ ] Affected documentation is updated, including ADRs, API docs, or changelog
      entries where relevant
- [ ] New public APIs, state transitions, and framework mappings have
      corresponding test coverage
- [ ] `CHANGELOG.md` includes the corresponding entry
- [ ] Breaking changes are marked with `BREAKING CHANGE:` in the commit footer
      and the migration path is explained in the PR description
- [ ] **Every commit has a DCO `Signed-off-by:` line**

---

## 5. Code Review Expectations

- Review focuses on **behavior contracts**: whether audit-chain invariants are
  satisfied, not style preference.
- Any **load-bearing architecture decision** (new framework mapping, hash-chain
  algorithm change, TSA integration approach, or security-boundary adjustment)
  must include an ADR (Architecture Decision Record) in [`docs/adr/`](docs/adr/README.md)
  using the [`docs/adr/0000-template.md`](docs/adr/0000-template.md) template.
  Load-bearing PRs without a corresponding ADR will not be merged.
- Review comments should cite specific code lines, not only say "this is wrong."
- Follow the existing ADR files for format; ADR numbers must increase without
  gaps.
- If two reviewers reach a substantive deadlock on a single PR, follow the
  PR-level procedure in
  [`docs/governance/conflict-resolution.md`](docs/governance/conflict-resolution.md)
  (third reviewer within 24h → `[DECISION]` lazy-consensus thread within 72h →
  `GOVERNANCE.md` §4.2 supermajority vote if still unresolved). Broader policy
  disputes still use `GOVERNANCE.md` §4.3 directly.

---

## 6. Reporting Bugs

For **general bugs**, open a [GitHub Issue](https://github.com/attestplane/attestplaneissues)
and include:

- The minimal command sequence that reproduces the bug
- Expected behavior vs actual behavior
- Relevant logs or panic output
- The affected SDK or framework mapping

For **security vulnerabilities**, **do not disclose details in a public issue.**
Follow the responsible disclosure process in [`SECURITY.md`](SECURITY.md) and
report through a private channel.

Audit-chain forgery, hash collisions, and RFC-3161 anchor bypasses are
high-severity vulnerabilities and must be reported privately.

---

## 7. License Grant

This project uses the **Apache License 2.0**. See [`LICENSE`](LICENSE).

By submitting a contribution to this repository:

1. You have read and certify the full Developer Certificate of Origin 1.1 terms
   in [`DCO.txt`](DCO.txt).
2. Your contribution is intentionally submitted for inclusion in the Work and is
   released under Apache License 2.0. You retain your copyright. Attestplane
   Pte. Ltd. (Singapore, in formation as of 2026-05-17) and all other downstream
   recipients receive your contribution under Apache License 2.0. This project
   does not require contributors to assign copyright to any company or grant
   extra copyright permissions, which is the key distinction between DCO and a
   CLA.
3. The `Signed-off-by:` line on your commit is written evidence of the DCO
   attestation above.

If you have questions, contact
[contributors@attestplane.com](mailto:contributors@attestplane.com).

---

## 8. Code of Conduct

This project follows [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). All
contributors, maintainers, and community members must follow its behavior
standards.
