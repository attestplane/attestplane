# Issue 104 Code Evidence

Implemented the v1.6.0 user-visible release summary as a docs-only change.

Files changed:

- Added `docs/releases/v1.6.0.md`.
- Updated `docs/release-notes/v1.6.0.draft.md` so the draft source no longer
  contradicts the final one-page summary.
- Added `CHANGELOG.md / Unreleased / v1.6.0 user-visible delta`.

Release-bucket mapping:

- Autodev planning loop hardening: Opus consultation for stable planning,
  accepted-plan to planned-task issue conversion, shared plan issuance across
  release tiers, schema and fan-out unification, structured autodev events,
  open issue inclusion, and planned issue reload from GitHub.
- Daily architecture audit fan-out: generated daily architecture audit plans,
  architecture plan fan-out, architecture planning on the Opus runner, and
  local Python selection on that runner.
- Release plumbing robustness: explicit stable-train git proxy strategy, idle
  cadence skipping before remote probe, importable release-planning scripts,
  transient Scorecard link handling, and markdown/plan-parser cleanup.

Compatibility and boundary decisions:

- The summary states: "No breaking changes. No public API surface changes."
- The compatibility note explicitly says v1.6.0 does not change SDK APIs, CLI
  behavior, verifier semantics, schemas, package names, release asset names,
  registry behavior, signing policy, release-gate policy, or claim-safety
  policy.
- Existing claim-safety exclusions are preserved: no EU AI Act compliance, GDPR
  compliance, legal certification, production readiness, certified provenance,
  SLSA L3, production-grade supply-chain security, or long-term archival trust
  guarantee is claimed.

Issue-link evidence:

- Linked the source planning issue:
  [Issue #100](https://github.com/attestplane/attestplaneissues100).
- Linked this planned task:
  [Issue #104](https://github.com/attestplane/attestplaneissues104).
- The local runner prompt requires cross-links to "ISSUE 1 boundary report" and
  "ISSUE 2 regression coverage", but local files and issue-104 evidence do not
  expose concrete issue numbers for those labels. The release summary and
  changelog therefore link those named artifacts back to the source planning
  issue instead of inventing missing IDs.
- The changelog references the prior docs-delta pattern from Issues #98, #94,
  #90, #85, #81, and #77 without duplicating those summaries.

Release-boundary confirmation:

- No package metadata, artifact manifests, checksums, upload plans, SDK code,
  verifier code, schema files, release gates, workflows, tags, or publish
  commands were changed.
- The implementation used only local repository files, local command output, and
  the issue text.
