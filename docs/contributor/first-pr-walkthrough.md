<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Your First Pull Request: A Walkthrough

Welcome. This document walks through one real, already-merged Attestplane pull
request end-to-end so that a first-time contributor can see what the project's
contribution discipline looks like in practice. It is not a rulebook; the
authoritative rules live in [`CONTRIBUTING.md`](../../CONTRIBUTING.md),
[`SECURITY.md`](../../SECURITY.md), and the ADR set in
[`docs/adr/`](../adr/README.md). This walkthrough is a worked example you can
read alongside those documents.

## 1. What this walkthrough covers

The canonical example is PR #32 — a small,
recent, well-scoped release-tooling fix that exercises every part of the
contribution flow: a feature-branch worktree, a touch into a workflow file,
a paired ADR caveat update, the ADR frozen-blocks lock refresh, lint, DCO
sign-off, the opus-reviewer review cycle, and a clean squash-and-delete
merge. It is a deliberately small change with proper discipline around it,
which makes it a useful shape to imitate on a first contribution.

PR #32's user-visible effect was narrow: the SLSA generator reusable workflow
was pinned by commit SHA, the upstream binary-fetch path rejected that with
`Invalid ref: <sha>. Expected ref of the form refs/tags/vX.Y.Z`, and the
`v1.0.8` release dry-run failed. The fix swapped the `uses:` clause to the
tag ref `@v2.1.0` and recorded the commit SHA as an audit-anchor comment,
with [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md) updated to
document why a tag ref is acceptable here.

For a documentation-only shape, see PR #27 as a secondary reference; the
discipline below applies to both.

## 2. Prerequisites

You will need:

| Tool | Why |
| ---- | --- |
| `git` | Worktrees and DCO sign-off |
| `gh` CLI | Fork creation, PR open, review reading |
| Python 3.11+ | `sdk/python` tests |
| Node 20+ | `sdk/typescript` tests |
| `typos` and `codespell` | Lint of any text you touch |
| `python3 -c "import yaml; yaml.safe_load(open(...))"` | YAML validity for any workflow you touch |

Optional, for release-adjacent PRs like PR #32: `cosign` (verify signed
release assets locally) and `slsa-verifier` (verify `.intoto.jsonl`
provenance attestations locally). Not needed for docs-only or SDK-only
first contributions.

## 3. Setup

Fork the repository on GitHub, then clone your fork and add the upstream
remote:

```bash
gh repo fork attestplane/attestplane --clone --remote
cd attestplane
```

Install the SDK dependencies per [`CONTRIBUTING.md`](../../CONTRIBUTING.md)
§2. For an SDK change:

```bash
pip install -e "sdk/python[dev]" && pytest sdk/python/
cd sdk/typescript && npm install && npm test
```

For a release-tooling change like PR #32, the smoke tests live in
`scripts/` (for example `scripts/check-adr-frozen-blocks.sh`) rather than the
SDK test suites; the relevant gate is whichever script the PR's diff touches.

## 4. Step-by-step: PR #32 reconstructed

What follows reconstructs the maintainer's steps for PR #32 so a new
contributor can imitate the same shape. Numbers reference the lines or
files in the actual merged diff, which you can inspect with
`gh pr diff 32 --repo attestplane/attestplane`.

### 4.1 Identify the issue

The release dry-run for `v1.0.8` failed with `Invalid ref: <sha>` in the
upstream SLSA generator binary-fetch path. The constraint is upstream and
the fix had to happen in this repository's `slsa-provenance.yml`. The
maintainer captured this as the PR description's "Summary" paragraph,
linking to the failed Actions run for the audit trail. Linking to the
failing CI run (or the issue) in your PR description is part of the
project's discipline; it gives reviewers a single anchor for "what was
broken."

### 4.2 Branch naming

The branch was `fix/slsa-generator-tag-ref`. This matches the convention in
[`CONTRIBUTING.md`](../../CONTRIBUTING.md) §3: `fix/<short-description>` for
a bug fix, `feature/<short-description>` for a new feature,
`docs/<short-description>` for a documentation change. Use the same prefix
your PR's `type:` Conventional Commits scope would use.

### 4.3 Read the ADR before editing

Before touching the SLSA workflow, the maintainer read
[ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md) in full. ADR-0018
is the existing decision record for cosign keyless signing and SLSA
provenance. The fix had to be consistent with that decision, not a
re-decision. This is a project-wide pattern: **find the ADR before you
edit code that an ADR has already governed.**

For a first contribution, the common cases are: (a) no ADR exists for this
area — a small fix usually does not need one, cite this in the PR
description; (b) an ADR exists and your fix is consistent with it — say so
explicitly, naming the ADR by number; (c) an ADR exists and your fix changes
the decision — this needs an ADR update with maintainer sign-off
(`needs-adr` label) before you proceed, and is rarely a first-PR shape.

### 4.4 The actual edit

PR #32's code change was seven added lines and four removed lines in
`.github/workflows/slsa-provenance.yml`: the `uses:` clause moved from
`@f7dd8c54...` to `@v2.1.0`; the existing pin comment was expanded into a
sidecar audit-anchor comment recording the commit SHA, the upstream
constraint (tag-ref only), and the bump-verification procedure; a
back-reference to ADR-0018 was added inline. The SHA pin information was
preserved as a comment rather than removed, so the audit anchor remained
inspectable. This is the project's standard move when a SHA pin must be
swapped for a tag ref: **the SHA does not disappear, it migrates from
`uses:` into a comment immediately above `uses:`.**

### 4.5 The ADR caveat addition

`docs/adr/0018-keyless-signing-and-slsa-provenance.md` Decision §2 received
a new "Tag-ref vs SHA-pin caveat" subsection (18 added lines, 2 removed)
explaining the upstream platform constraint, the audit-anchor SHA
convention, and the three-step bump-verification procedure. This is the
"ADR documents the why" pattern: the workflow change is small, but the
reasoning belongs in the ADR so a future maintainer understands why the
tag ref is acceptable. The Decision section was edited because the caveat
is part of the decision, not a footnote.

### 4.6 The ADR frozen-blocks lock refresh

ADRs are content-hash-locked in `docs/adr/.frozen-blocks.lock`. Any ADR
edit changes that ADR's hash, and the lock file must be regenerated:

```bash
./scripts/check-adr-frozen-blocks.sh --update
```

PR #32's lock refresh changed exactly one line — the hash for
`0018-keyless-signing-and-slsa-provenance.md`. No other ADR's hash moved.
A diff that updates more than one ADR's hash in the lock is a signal that
something unintended happened; review carefully before pushing.

### 4.7 Lint

The maintainer ran the project's lint gates on the touched files:

```bash
typos --config _typos.toml <touched-files...>
codespell <touched-files...>
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/slsa-provenance.yml'))"
./scripts/check-adr-frozen-blocks.sh
```

All four exited zero before the commit. Lint discipline applies to every
touched file — workflows, ADRs, and Markdown are equally subject to `typos`
and `codespell`.

### 4.8 Commit with DCO sign-off

The commit was made with `-s` to append a `Signed-off-by:` trailer per the
Developer Certificate of Origin 1.1 — see
[`CONTRIBUTING.md`](../../CONTRIBUTING.md) §1 and [`DCO.txt`](../../DCO.txt).
The commit message followed Conventional Commits with type `fix` and scope
`release`, a one-line headline, an explanation paragraph, a verbatim copy
of the upstream error, the audit-anchor SHA, and a `Test plan:` block.

```bash
git commit -s -m "fix(release): switch SLSA generator to tag ref @v2.1.0 (...)"
```

If you forget `-s`, do not amend; use `git rebase HEAD~N --signoff`.

### 4.9 Push and open the PR

```bash
git push -u origin fix/slsa-generator-tag-ref
gh pr create --base main --title "fix(release): switch SLSA generator to tag ref @v2.1.0 (...)" \
             --body-file PR_BODY.md
```

The PR body for #32 used the structure from
[`.github/pull_request_template.md`](../../.github/pull_request_template.md):
Summary, Changes, Why this is OK, Red lines preserved, Test plan, Follow-up.
The "Red lines preserved" subsection is project-specific shorthand for the
maintainer's release-discipline checklist; first-time contributors are not
required to use that shorthand, but a brief "this change does not move tags,
publish anything, or modify frozen specs" sentence in the PR body is welcome
and accelerates review.

### 4.10 The opus-reviewer review cycle

PR #32 went through the project's automated review pass plus maintainer
review. Address review comments as additional commits on the same branch
(squash happens at merge time). Do not force-push over review history while
review is in flight; reviewers rely on commit-by-commit diffs.

### 4.11 Merge

Maintainers merge with **squash + delete branch**. The squash commit
preserves the PR title and description with `Signed-off-by:` trailers
collected automatically. After merge,
`git fetch upstream && git checkout main && git pull --ff-only` brings your
local main up to date. You do not retag, sign, or publish anything; release
tagging is a maintainer-only act gated by
[`docs/runbooks/github-cd-release.md`](../runbooks/github-cd-release.md).

## 5. What to look for in a first contribution

Before you push, walk this checklist. It mirrors the PR template's
"Compliance / security impact" and "Test plan" sections.

- [ ] Branch name uses the right prefix (`feat/`, `fix/`, `docs/`,
      `refactor/`, `test/`, `chore/`).
- [ ] Every commit has a `Signed-off-by:` trailer.
- [ ] The PR title follows Conventional Commits.
- [ ] The PR body has a Summary, a list of Changes, and a Test plan.
- [ ] Touched files are clean under `typos` and `codespell`.
- [ ] If you touched any YAML, it parses with `yaml.safe_load`.
- [ ] If you touched any ADR, `./scripts/check-adr-frozen-blocks.sh`
      exits zero (run with `--update` first, then without).
- [ ] If your change is load-bearing (new framework mapping, hash chain
      semantics, TSA integration, security boundary, public API), an ADR
      draft is included or the PR is explicitly tagged `needs-adr` for
      maintainer triage.
- [ ] You did not modify any frozen spec (see §7 below).
- [ ] You did not touch release tagging, signing material, or any path
      that publishes to a registry.

## 6. Where to ask

- **GitHub Issues** — issues
  for bug reports and feature requests. Filter to
  `good first issue`
  for newcomer-friendly work.
- **GitHub Discussions** —
  discussions for
  open-ended questions ("how should I approach X") and design conversations
  that are not yet a bug or feature.
- **Stuck mid-PR?** Comment on the issue your PR closes, or push your
  work-in-progress as a draft PR and ask a question in the PR description.

Response timelines for non-security questions are best-effort. The only
documented response SLA in this project is for vulnerability reports, and
that SLA lives in [`SECURITY.md`](../../SECURITY.md). Do not assume any
response window that `SECURITY.md` does not state.

## 7. What is out of scope for a first PR

A first PR is the wrong place for any of the following. These either need a
designed-and-reviewed ADR change, maintainer-only release tooling, or
both:

- **`docs/spec/aia-12-aligned-profile.md`** — this file is frozen and is
  not edited as part of routine work. A change here requires its own
  designed ADR pass.
- **Decision sections of any existing ADR** without explicit maintainer
  sign-off. ADR Context, Consequences, and footnote material can move with
  an ADR-adjacent PR; Decision sections move only under a `needs-adr`
  triage. ADR-0018's "Tag-ref vs SHA-pin caveat" addition in PR #32 was an
  exception that the maintainer signed off on inside the same PR; do not
  read it as a precedent for unsigned Decision edits.
- **Release workflows** in `.github/workflows/release-*.yml`,
  `.github/workflows/sign-release.yml`, and
  `.github/workflows/slsa-provenance.yml`, **except** for narrow upstream
  workaround fixes like PR #32 itself. If you are not certain whether your
  workflow change is in this category, open an issue or a discussion first.
- **Signing material.** No private keys, no `.cosign.key`, no GPG private
  blocks, no secrets in the repo, ever. The signing root is keyless via
  Sigstore — see [ADR-0018](../adr/0018-keyless-signing-and-slsa-provenance.md).
- **Tag movement.** Tags are immutable. Do not retag, do not force-push
  tags, do not delete tags. A bad release tag is corrected by a new tag
  with a higher version number, not by rewriting history.
- **Publishing to PyPI, npm, or any other registry.** Publication goes
  through GitHub Actions CD only; see
  [`docs/runbooks/github-cd-release.md`](../runbooks/github-cd-release.md).

If you want to work on any of the above, open an issue first and ask the
maintainer to confirm the scope before you start.

---

If anything in this walkthrough is wrong or outdated relative to a more
recent merged PR, please open an issue with the label `area:docs` so it can
be refreshed against the current example PR.
