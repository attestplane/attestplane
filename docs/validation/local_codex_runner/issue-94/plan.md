# Issue 94 Implementation Plan

Plan ID: `1c6c43895e7a304f`

## Scope

Summarize the user-visible delta for `v1.5.9` in the local release-note surface.
The local draft currently records the change only as `fix: consult opus for
stable planning`; the implementation phase should rewrite that into bounded
release-consumer language and link it to the source planning issue and task
issue.

This runner phase used only local repository files, local command output, and
the issue text. The project-level Opus consultation requirement is not executed
in this phase because the runner prompt explicitly forbids external advisory
services.

## Current Local Findings

- `docs/release-notes/v1.5.9.draft.md` exists and is the release note named by
  `release/artifacts/v1.5.9/artifact-manifest.json`.
- The current `v1.5.9` change summary is terse: `fix: consult opus for stable
  planning`.
- The existing release note already contains explicit boundaries for compliance,
  production readiness, certified provenance, SLSA L3, production-grade
  supply-chain security, and long-term archival trust.
- `release/artifacts/v1.5.9/artifact-manifest.json` records local prep
  non-actions and identifies the release-note file; it should be used as
  context, not edited for this docs-only task.
- `release/artifacts/v1.5.9/upload-plan.md` contains tag, push, and workflow
  commands as a plan document only. The implementation phase must not execute
  those commands.
- Local evidence for this runner phase is under
  `docs/validation/local_codex_runner/issue-94/`.

## Implementation Approach

1. Update the `v1.5.9` release note.
   - Edit `docs/release-notes/v1.5.9.draft.md`.
   - Replace or supplement the terse change bullet with a short
     user-visible summary: stable release planning now requires Opus
     consultation before the suffix-free stable package cut proceeds.
   - Keep wording scoped to release-planning/release-integrity behavior.
   - Do not imply SDK, verifier, schema, artifact, registry, signing,
     compliance, production-readiness, or provenance behavior changed unless
     local evidence in the implementation phase proves it.

2. Add issue cross-links in the release note.
   - Link source planning issue
     [#91](https://github.com/attestplane/attestplane/issues/91).
   - Link this planned-task issue
     [#94](https://github.com/attestplane/attestplane/issues/94).
   - If local evidence identifies additional task issues from the same plan,
     link them. If no local-only evidence identifies them, do not invent task
     issue numbers; record the limitation in implementation evidence.

3. Preserve claim boundaries.
   - Keep the existing `Explicit Boundaries` section intact unless tightening
     wording is needed.
   - Avoid stronger claims than the local files support.
   - Do not add claims about successful publication, live registry state,
     security certification, compliance, or production readiness.

4. Avoid release-surface churn outside the docs scope.
   - Do not edit checksums, artifact manifests, upload plans, package metadata,
     release workflows, SDK code, verifier code, schemas, or runbook gates.
   - A runbook edit is not expected unless implementation discovers that
     `docs/release-notes/v1.5.9.draft.md` cannot satisfy acceptance criterion
     1 by itself.

## Files Likely To Change

- `docs/release-notes/v1.5.9.draft.md`
- `docs/validation/local_codex_runner/issue-94/code.md` in the implementation
  phase.
- `docs/validation/local_codex_runner/issue-94/test.md` in the validation
  phase.
- `docs/validation/local_codex_runner/issue-94/review.md` if a later review
  phase is run.

Files that should normally remain unchanged:

- `release/artifacts/v1.5.9/artifact-manifest.json`
- `release/artifacts/v1.5.9/checksums.sha256`
- `release/artifacts/v1.5.9/upload-plan.md`
- `docs/runbooks/*`
- package manifests, SDK source, verifier source, schemas, CI workflows, and
  release-gate implementation files

## Tests And Local Gates

Issue-required validation:

```bash
git diff --check
```

Focused supporting checks for the implementation phase:

```bash
git diff -- docs/release-notes/v1.5.9.draft.md
rg -n "v1\\.5\\.9|#91|#94|Opus|stable planning|Explicit Boundaries" \
  docs/release-notes/v1.5.9.draft.md
rg -n "production-ready|EU AI Act compliant|GDPR compliant|SLSA L3|certified provenance" \
  docs/release-notes/v1.5.9.draft.md
```

No full product gate is required for this docs-only task if the implementation
touches only release-note text and local runner evidence. If any release
automation, package metadata, artifact metadata, SDK, verifier, schema, or gate
file is changed, stop and run the nearest local release gate before closure.

## Risk Classification

P2, low implementation risk.

The planned work is documentation-only and should not affect runtime or release
behavior. The main risk is overclaiming: translating `fix: consult opus for
stable planning` into user-facing language could imply that publication,
registry state, product behavior, or compliance posture changed. Mitigate this
by describing only the release-planning integrity delta and preserving the
existing explicit non-claim boundaries.

A secondary risk is incomplete issue linkage. The prompt provides source issue
`#91` and task issue `#94`; additional task issues should only be linked if
identified from local repository evidence.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-94/plan.md` for this planning
  phase.
- `docs/validation/local_codex_runner/issue-94/code.md` in the implementation
  phase, listing exact docs files changed, issue links added, and any task-link
  limitation.
- `docs/validation/local_codex_runner/issue-94/test.md` in the validation
  phase, with exact `git diff --check` output and focused supporting-check
  output.
- `docs/validation/local_codex_runner/issue-94/review.md` if a later review
  phase runs, confirming release-note scope, claim boundaries, and no release
  gate weakening.

Do not update release assets, checksums, package artifacts, upload plans, or
release metadata for this docs-only task unless a later authorized phase
explicitly changes the task scope.

## Safety Confirmation

This task will not merge branches, create tags, move tags, publish npm
packages, publish PyPI packages, push to PyPI, push to any remote, or weaken
release gates. It will not lower P0/P1 severity, remove failing tests to
manufacture a pass, loosen release gates, loosen claim-safety policy, or
read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI
tokens, private keys, `.pypirc`, or `.npmrc`.
