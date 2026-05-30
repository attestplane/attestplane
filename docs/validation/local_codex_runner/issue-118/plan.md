# Issue 118 Implementation Plan

Plan ID: `62384e54aa68607a`

## Scope

Document the v1.6.2 user-visible delta for release consumers. The single real
change to summarize is that planned-task issues created from Opus consultations
are now re-fetched from GitHub before downstream consumption, eliminating the
first-run race where downstream automation saw zero newly created issues.

This runner phase used only local repository files, local command output, and
the issue text. The project-level Opus consultation requirement is not executed
in this phase because the runner prompt explicitly forbids external advisory
services.

## Current Local Findings

- `docs/release-notes/v1.6.2.draft.md` exists and currently says only
  `fix: fetch opus planned issues after creation`; it needs a user-facing
  one-paragraph explanation.
- The issue names `docs/releases/v1.6.2.md`, but this checkout has no
  `docs/releases/` directory. The implementation phase must either create the
  issue-requested path or reconcile it with the existing
  `docs/release-notes/v1.6.2.draft.md` workflow.
- `scripts/release/plan_to_issues.py` already contains the relevant local code
  path: `create_issues(...)` creates issues, then calls
  `fetch_uploaded_issues(...)`, and raises if the created issues cannot be
  fetched back from GitHub.
- `README.md` has a release/package table under "Published v1.0.x pre-GA
  status"; the requested README change should stay limited to that release
  table area.
- The issue-required command
  `python -m scripts.release.render_release_notes --version v1.6.2 --check`
  references a module that is not present in this checkout. The implementation
  phase should record that blocker if it remains absent and run the closest
  local release-note validation without weakening the acceptance criteria.

## Implementation Approach

1. Update the active v1.6.2 release note.
   - Prefer the issue-requested `docs/releases/v1.6.2.md` if the
     implementation phase confirms that path is now the canonical final release
     note location.
   - If the local release workflow still treats draft release notes as the
     source of truth, update `docs/release-notes/v1.6.2.draft.md` and record
     why `docs/releases/v1.6.2.md` is absent.
   - Replace the terse change bullet with a one-paragraph user-facing summary:
     planned-task issues created from Opus consultations are re-fetched from
     GitHub before downstream consumption, so the first runner pass no longer
     sees zero newly created issues.
   - Keep the summary scoped to automation behavior; do not imply SDK, CLI,
     verifier, schema, package, registry, signing, or compliance behavior
     changed.

2. Separate infrastructure-only notes.
   - Add an `Infrastructure` bullet or subsection for CI-only improvements,
     including the proxy strategy and local Python on the Opus runner.
   - Word this as operational/CI hygiene so users do not mistake it for product
     behavior.
   - Local related draft notes exist for nearby releases:
     `docs/release-notes/v1.5.8.draft.md` mentions proxy strategy and
     `docs/release-notes/v1.6.0.draft.md` mentions local Python on the Opus
     runner.

3. Update `CHANGELOG.md`.
   - Add a concise v1.6.2 entry or unreleased note in the repository's existing
     changelog style.
   - Cross-link the source planning issue
     [#113](https://github.com/attestplane/attestplaneissues113), this task
     [#118](https://github.com/attestplane/attestplaneissues118), the
     #108-style boundary audit / milestone ISSUE 1 when the exact local issue
     number is available from runner evidence, and the related planned-task
     issues spawned from this plan.
   - If the implementation phase cannot identify the exact ISSUE 1 or related
     task issue numbers using local evidence only, leave a narrow placeholder
     in implementation evidence rather than inventing issue links.

4. Update only the README release table.
   - Keep any README edit constrained to the release/package table area named
     by the issue.
   - Add only a short reference to the v1.6.2 release note if needed by the
     local release table pattern.
   - Do not modify broad product positioning, roadmap, badges, install
     instructions, package versions, or claim-safety language.

5. Preserve release boundaries.
   - Do not touch artifact manifests, checksums, upload plans, release
     workflows, package metadata, SDK code, verifier code, schemas, or release
     gates.
   - If milestone ISSUE 1 later surfaces an undisclosed behavior change, expand
     the v1.6.2 summary before closure as required by the issue text.

## Files Likely To Change

- `CHANGELOG.md`
- `docs/releases/v1.6.2.md` if the implementation phase creates or confirms the
  issue-requested final release-note path
- `docs/release-notes/v1.6.2.draft.md` if the local draft release-note path
  remains authoritative
- `README.md` release table only
- `docs/validation/local_codex_runner/issue-118/code.md` and `test.md` in later
  phases

Files that should not change for this docs task:

- `release/artifacts/v1.6.2/artifact-manifest.json`
- `release/artifacts/v1.6.2/checksums.sha256`
- `release/artifacts/v1.6.2/upload-plan.md`
- SDK, verifier, schema, CI workflow, and release-gate implementation files

## Tests And Local Gates

Issue-required validation commands:

```bash
markdownlint docs/releases/v1.6.2.md CHANGELOG.md
python -m scripts.release.render_release_notes --version v1.6.2 --check
git diff --stat -- docs CHANGELOG.md
```

If `docs/releases/v1.6.2.md` is not created because the local workflow keeps
`docs/release-notes/v1.6.2.draft.md` authoritative, run markdownlint against the
actual edited release-note file and record the path reconciliation in
`test.md`.

If `scripts.release.render_release_notes` remains absent, record the exact
module-not-found failure in `test.md` and run the closest available local
release-doc checks without claiming the required command passed.

Additional local checks:

```bash
rg -n "v1\\.6\\.2|first-run|planned-task|Infrastructure|#113|#118" \
  CHANGELOG.md README.md docs/release-notes docs/releases
rg -n "production-ready|compliance certification|SLSA L3|certified provenance" \
  CHANGELOG.md docs/release-notes/v1.6.2* docs/releases/v1.6.2.md
```

No full product gate is required for docs-only text unless the implementation
phase touches release automation, SDK code, schemas, package metadata, artifact
manifests, or release gates. If any such file is touched, stop and run the
nearest local release gate before closure.

## Risk Classification

P2, low implementation risk.

The intended change is documentation-only and should not alter runtime or
release behavior. The main risk is release-note path ambiguity:
`docs/releases/v1.6.2.md` is required by the issue, while the local tree uses
`docs/release-notes/v1.6.2.draft.md`. A secondary risk is overclaiming the
release by making CI-only improvements look like product changes. Mitigate by
keeping product text to the single planned-task re-fetch race fix, separating
infrastructure notes, and preserving the existing explicit release boundaries.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-118/plan.md` for this planning
  phase.
- `docs/validation/local_codex_runner/issue-118/code.md` in the implementation
  phase, listing exact docs files changed, release-note path reconciliation, and
  issue links used.
- `docs/validation/local_codex_runner/issue-118/test.md` in the validation
  phase, with exact markdownlint, release-note render/check, and diff-stat
  outputs or documented local blockers.
- `docs/validation/local_codex_runner/issue-118/review.md` if a later review
  phase runs, confirming the one real user-visible change, separated
  infrastructure note, cross-links, and release-boundary preservation.

## Safety Confirmation

This task will not merge branches, create tags, move tags, publish npm
packages, publish PyPI packages, push to PyPI, push to any remote, or weaken
release gates. It will not lower P0/P1 severity, remove failing tests to
manufacture a pass, loosen release gates, loosen claim-safety policy, or
read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI
tokens, private keys, `.pypirc`, or `.npmrc`.
