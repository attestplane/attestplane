<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# OpenSSF Scorecard — public score publication

Attestplane publishes its OpenSSF Scorecard score in the project
[`README.md`](../../README.md) badge row via the public Scorecard API
endpoint `https://api.scorecard.dev/projects/github.com/attestplane/attestplane/badge`
(linking through to
`https://scorecard.dev/viewer/?uri=github.com/attestplane/attestplane`).

The Scorecard analysis itself runs in CI on every push to `main` and on
a weekly cadence; this document records the publication posture, the
honest caveats around what the score means, and pointers to the
existing artifacts.

## What is OpenSSF Scorecard

[OpenSSF Scorecard](https://scorecard.dev/) is an automated, open-source
analysis tool maintained by the Open Source Security Foundation. It
evaluates a repository against a fixed set of security heuristics
(Branch-Protection, Token-Permissions, Pinned-Dependencies, SAST,
Signed-Releases, Dangerous-Workflow, Code-Review, etc.), normalises
each check to 0-10, and reports an aggregate score plus per-check
detail. The data source is the repository itself plus public GitHub
metadata; no manual self-attestation is involved.

## Current attestplane Scorecard CI workflow

| Item | Value |
|------|-------|
| Workflow file | [`.github/workflows/scorecard.yml`](../../.github/workflows/scorecard.yml) |
| Workflow name | `ossf-scorecard` |
| Job name | `OSSF Scorecard` |
| Triggers | `push` to `main`, weekly cron (`0 6 * * 1`), `branch_protection_rule`, `workflow_dispatch` |
| Action | `ossf/scorecard-action` pinned by SHA |
| Publish flag | `publish_results: true` (results uploaded to OpenSSF transparency log) |
| SARIF artifact | Uploaded to GitHub code scanning and as a workflow artifact (`results.sarif`) |

The `publish_results: true` flag is what allows the public
`api.scorecard.dev` endpoint to surface a score for this repository at
all. Without it, the workflow would still run but the score would only
be visible to maintainers via the SARIF artifact.

## Scorecard monitoring posture

Scorecard is a public security signal, not a release gate. The project
keeps that distinction explicit:

- A scheduled monitor run stores the latest normalized Scorecard
  summary on disk and compares it against the previous baseline.
- Meaningful regressions open or update a GitHub issue labeled
  `type:security`, `scorecard-regression`, `monitor-only`, and
  `priority:P2`.
- The monitor records the drift for human follow-up, but it does not
  block package publication, tag creation, or any existing release
  workflow.
- The first monitor run may bootstrap the baseline summary; later runs
  compare the new summary against that stored baseline.

The local helper script is
[`scripts/security/scorecard_diff.py`](../../scripts/security/scorecard_diff.py)
for deterministic comparisons and
[`scripts/security/scorecard_monitor.py`](../../scripts/security/scorecard_monitor.py)
for summary storage plus issue automation. A typical invocation looks
like:

```bash
python scripts/security/scorecard_monitor.py \
  --baseline .scorecard/scorecard-baseline.json \
  --current .scorecard/scorecard-current.json \
  --latest-summary .scorecard/scorecard-latest-summary.json
```

The comparison helper used by validation is:

```bash
python scripts/security/scorecard_diff.py \
  --baseline <baseline.json> \
  --current <current.json>
```

## How to verify the score

Three independent verification paths are available to any reader:

1. **Live badge.** The badge in [`README.md`](../../README.md) renders
   the current numeric score from `api.scorecard.dev`. The badge image
   is regenerated on each Scorecard publish.
2. **Scorecard viewer.** Navigate to
   `https://scorecard.dev/viewer/?uri=github.com/attestplane/attestplane`
   for the full per-check breakdown, with each check's reasoning and
   evidence.
3. **Local re-run.** Any reader can re-run Scorecard locally against a
   pinned commit using the upstream Scorecard CLI; the GitHub Actions
   run logs at
   `https://github.com/attestplane/attestplaneactions/workflows/scorecard.yml`
   are the canonical source of truth.

## Honest note: the score will publicly track, and may go down

Publishing the badge is intentional. It means every reader sees the
current score, including weeks where the score has dropped because a
new dependency is unpinned, a workflow action has not yet been pinned
by SHA, or a Scorecard rule version has tightened against the current
baseline. The project accepts that exposure deliberately — a score
that can only go up is not a useful trust signal.

## Known gaps

The published Scorecard score typically reflects gaps in:

- **Branch-Protection** — Scorecard cannot always observe all
  branch-protection rule details over the GitHub API; the score for
  this check can read lower than the actual posture.
- **Token-Permissions** — workflow `permissions:` blocks default to
  read-all at the workflow level; per-job tightening is an ongoing
  hygiene task tracked alongside Silver-tier advancement.
- **Pinned-Dependencies** — third-party action pinning by SHA is
  enforced for security-relevant workflows; full coverage across every
  workflow is incremental work.

Per-criterion advancement is sequenced in the OpenSSF
[Silver-tier roadmap](openssf-silver-roadmap.md) where it overlaps
with Best Practices criteria; the two badges are complementary, not
redundant.

## Complementary artifact

This Scorecard publication pairs with the project's
[OpenSSF Best Practices passing badge (project 12924)](https://www.bestpractices.devprojects/12924),
documented in
[`openssf-best-practices.md`](openssf-best-practices.md). Together
they form the project's *OSSF posture* pair: Best Practices captures
the documented process state at 100%; Scorecard captures the live,
automated security-heuristic snapshot.

## Non-claim

Publishing an OpenSSF Scorecard score is a **process matter, not a
compliance certification**. The score reflects how well the
repository's observable state matches Scorecard's heuristics on the
day of measurement. It does not constitute SLSA Build L3 attestation,
EU AI Act Article 12 logging conformance, CRA 2027 readiness, or any
regulatory determination. The AIA-12 *aligned* profile recorded in
[`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md)
is unaffected by the Scorecard score.
