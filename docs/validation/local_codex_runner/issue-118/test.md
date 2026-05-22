# Issue 118 Validation Evidence

Plan ID: `62384e54aa68607a`

## Issue-required validation

```text
$ markdownlint docs/releases/v1.6.2.md CHANGELOG.md
zsh:1: command not found: markdownlint
```

The repository has `.markdownlint.jsonc`, but this runner environment does not
have a `markdownlint` binary or a local `node_modules/.bin` markdownlint
installation.

```text
$ python -m scripts.release.render_release_notes --version v1.6.2 --check
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named scripts.release.render_release_notes
```

The issue-required render-check module is absent from this checkout.

```text
$ git diff --stat -- docs CHANGELOG.md
 CHANGELOG.md                       | 16 ++++++++++++++++
 docs/release-notes/v1.6.2.draft.md | 29 +++++++++++++++++++++++++----
 2 files changed, 41 insertions(+), 4 deletions(-)
```

Note: because `docs/releases/v1.6.2.md` is a new untracked file before staging,
the exact `git diff --stat -- docs CHANGELOG.md` command does not include it.

## Additional local validation

```text
$ rg -n "v1\\.6\\.2|first-run|planned-task|Infrastructure|#113|#117|#118|#108" CHANGELOG.md README.md docs/release-notes docs/releases
CHANGELOG.md:14:### v1.6.2 user-visible delta
CHANGELOG.md:16:- `v1.6.2` documents one user-visible automation fix: planned-task
CHANGELOG.md:23:  [Issue #113](https://github.com/attestplane/attestplane/issues/113);
CHANGELOG.md:25:  [Issue #108](https://github.com/attestplane/attestplane/issues/108);
CHANGELOG.md:27:  [Issue #117](https://github.com/attestplane/attestplane/issues/117)
CHANGELOG.md:28:  and [Issue #118](https://github.com/attestplane/attestplane/issues/118).
README.md:260:| v1.6.2 release note | [docs/releases/v1.6.2.md](docs/releases/v1.6.2.md) | user-visible planned-task refetch race fix; CI-only items separated as infrastructure |
docs/releases/v1.6.2.md:1:# v1.6.2
docs/releases/v1.6.2.md:8:The single user-visible change in `v1.6.2` is release-planning automation
docs/releases/v1.6.2.md:9:reliability: planned-task issues created from Opus consultations are now
docs/releases/v1.6.2.md:11:first-run race where the runner could create planned-task issues successfully
docs/releases/v1.6.2.md:15:Planning context: [Issue #113](https://github.com/attestplane/attestplane/issues/113);
docs/releases/v1.6.2.md:17:[Issue #108](https://github.com/attestplane/attestplane/issues/108);
docs/releases/v1.6.2.md:19:[Issue #117](https://github.com/attestplane/attestplane/issues/117) and
docs/releases/v1.6.2.md:20:[Issue #118](https://github.com/attestplane/attestplane/issues/118).
docs/releases/v1.6.2.md:22:## Infrastructure
docs/release-notes/v1.6.2.draft.md:1:# v1.6.2
docs/release-notes/v1.6.2.draft.md:7:The single user-visible change in `v1.6.2` is release-planning automation
docs/release-notes/v1.6.2.draft.md:8:reliability: planned-task issues created from Opus consultations are now
docs/release-notes/v1.6.2.draft.md:10:first-run race where the runner could create planned-task issues successfully
docs/release-notes/v1.6.2.draft.md:14:Planning context: [Issue #113](https://github.com/attestplane/attestplane/issues/113);
docs/release-notes/v1.6.2.draft.md:16:[Issue #108](https://github.com/attestplane/attestplane/issues/108);
docs/release-notes/v1.6.2.draft.md:18:[Issue #117](https://github.com/attestplane/attestplane/issues/117) and
docs/release-notes/v1.6.2.draft.md:19:[Issue #118](https://github.com/attestplane/attestplane/issues/118).
docs/release-notes/v1.6.2.draft.md:21:## Infrastructure
```

```text
$ git diff --check -- CHANGELOG.md README.md docs/releases/v1.6.2.md docs/release-notes/v1.6.2.draft.md
```

Exit status: `0`.
