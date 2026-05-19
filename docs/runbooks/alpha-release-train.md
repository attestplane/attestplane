# Alpha Release Train Runbook

The alpha release train packages the manual Attestplane alpha release sequence
into a finite, deterministic workflow.

It is not an autonomous product loop. It only releases prepared alpha
candidates whose scope, versions, release notes, artifacts, manifest, and
checksums already exist.

## Why Finite

An unbounded release loop would be unsafe for PyPI, npm, and GitHub Releases.
It could publish empty or duplicate alphas, move public trust surfaces without
review, and blur alpha/no-go claims. The supported loop is therefore:

1. Ask Opus for advisory next-alpha issue planning.
2. Review the advisory plan and create or curate issues manually.
3. Implement and validate exactly one alpha candidate.
4. Put the prepared candidate in `release/alpha-train/queue.json`.
5. Run the train with `--max-count 1`.
6. Verify GitHub Release, PyPI, npm, and issue status.
7. Prepare the next candidate only after the previous one is complete.

## Advisory Planning First

```bash
python scripts/release/alpha_release_train.py --plan-next-alpha --execute
```

This first step calls `ask_opus.sh architect` and writes an advisory issue plan
under `release/alpha-train/proposals/`. The file is marked:

```text
STATUS: ADVISORY
AUTHORITY: NOT_AUTHORIZED_FOR_PUBLISH
SCOPE: ISSUE_PLANNING_ONLY
```

The plan is not a queue entry. It cannot authorize publish, tag, release,
merge, issue closure, or npm `latest` changes. The runner rejects advisory
files if they are accidentally used as release notes, manifest, or checksum
inputs.

## Command

```bash
python scripts/release/alpha_release_train.py \
  --queue release/alpha-train/queue.json \
  --execute \
  --max-count 1
```

The connected advisory-to-release pipeline command is:

```bash
python scripts/release/alpha_release_train.py --pipeline --execute --max-count 1
```

It always runs Opus advisory issue planning first, writes a JSON stage report
under `release/alpha-train/reports/`, then consumes at most one prepared queue
candidate. An empty queue is a successful no-op after planning, not a release.

The runner performs:

- optional Opus advisory issue planning when `--plan-next-alpha` is passed,
- clean working tree check,
- Python full tests, ruff, mypy,
- TypeScript tests, typecheck, lint,
- public API, schema hash, fixture hash, ProofBundle verifier gates,
- release artifact prep gate,
- gitleaks,
- `git push origin main`,
- annotated release tag push,
- GitHub prerelease creation with artifacts,
- PyPI trusted publishing workflow,
- npm alpha-tag publishing workflow,
- registry verification.

## Stop Conditions

The train stops on:

- missing candidate files,
- dirty working tree,
- failed local gate,
- failed claim scan,
- gitleaks finding,
- existing conflicting tag or GitHub Release,
- workflow failure,
- PyPI/npm registry verification failure,
- npm `latest` pointing at the alpha candidate.

## Human Ownership

The founder/maintainer remains the release owner. The release train is only a
deterministic executor for a prepared alpha candidate. It does not approve its
own scope, downgrade findings, invent release notes, or close release blockers.

Operational owner for the current single-maintainer phase:

- GitHub owner: `@merchloubna70-dot`
- Registry owner: the authenticated PyPI/npm publisher for the project
- Manual review point: before adding an entry to `release/alpha-train/queue.json`

## Rollback and Recovery

Published registry artifacts are immutable. Do not delete or rewrite published
alpha artifacts as a normal rollback path.

If a run fails before publication:

1. Leave the tag unreleased if it was not pushed.
2. Delete only local, unpublished build artifacts if needed.
3. Fix the candidate and rerun from a clean working tree.

If a run fails after tag or GitHub Release creation but before registry publish:

1. Do not retag.
2. Mark the GitHub Release notes with the failed platform state.
3. Prepare a new alpha candidate if code changes are required.

If a registry publish succeeds and a later platform fails:

1. Do not overwrite the published package.
2. Record the partial release in the issue/release notes.
3. Publish a new alpha with a higher version for fixes.

## Code Ownership

`.github/CODEOWNERS` currently applies a catch-all owner rule to all files,
including:

- `release/alpha-train/**`
- `scripts/release/**`
- `.github/workflows/alpha-release-train.yml`

Branch protection should require that owner review once the project has more
than one maintainer. The current single-maintainer phase avoids self-locking.

## Explicit Non-Goals

- No autonomous code generation.
- No release scope invention.
- No npm `latest` promotion.
- No tag rewriting.
- No force push.
- No production/compliance/certification claim.
- No signed provenance claim unless signature artifacts are actually present.
