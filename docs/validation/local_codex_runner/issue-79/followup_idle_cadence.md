# Follow-Up Issue Draft: Idle-Cadence Hygiene Noise

Parent issue: `#79`

## Summary

The focused stable boundary `v1.5.0..v1.5.6` contains real human work, so the
release train should publish `v1.5.6`.

The broader root-to-HEAD hygiene check required by the issue body,
`git diff --check $(git rev-list --max-parents=0 HEAD)..HEAD`, still reports
pre-existing whitespace and EOF noise that is unrelated to the release
boundary decision. That noise should not block the stable cut, but it is a
follow-up risk because it can make future cadence validation harder to read.

## Current Findings

The root-to-HEAD `git diff --check` output reported:

- trailing whitespace in `CONTRIBUTING_zh.md`
- new blank line at EOF in `docs/validation/local_codex_runner/issue-80/codex_review_report.md`
- new blank line at EOF in `docs/validation/local_codex_runner/issue-89/codex_review_report.md`
- new blank line at EOF in `release/artifacts/v0.8.0-beta.0/artifact-manifest.json`
- new blank line at EOF in `release/artifacts/v0.8.0-beta.0/checksums.sha256`
- new blank line at EOF in `scripts/__init__.py`
- new blank line at EOF in `scripts/local_codex_runner/__init__.py`
- new blank line at EOF in `scripts/local_codex_runner/launchd/com.attestplane.local-codex-runner.plist.example`
- new blank line at EOF in `scripts/local_codex_runner/prompt_builder.py`
- new blank line at EOF in `scripts/local_codex_runner/run_once.sh`
- new blank line at EOF in `scripts/local_codex_runner/state_store.py`
- new blank line at EOF in `tests/local_codex_runner/conftest.py`
- new blank line at EOF in `tests/local_codex_runner/test_prompt_builder.py`

## Draft Acceptance Criteria

1. Reduce or explicitly baseline the repo-wide `git diff --check` noise so
   future release-integrity checks can distinguish stable-boundary findings
   from historical hygiene issues.
2. Preserve the existing stable-train cadence rule: skip only when the range
   contains no real human work.
3. Keep the fix scoped to hygiene and validation clarity only. Do not move
   tags, publish packages, or weaken release gates.

## Evidence Reference

The focused stable boundary check stayed clean:

```bash
git diff --check v1.5.0..v1.5.6
```

The follow-up exists only because the broader repository baseline still has
pre-existing hygiene noise.

