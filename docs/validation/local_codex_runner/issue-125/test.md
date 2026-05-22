# Issue 125 Test Evidence

Plan ID: `f9ab1b6b3254613c`

## Issue-Requested Validation

### `markdownlint docs/release-notes/v1.7.0.md CHANGELOG.md`

Result: blocked by missing local executable.

```text
zsh:1: command not found: markdownlint
```

Fallback attempt with `npx --no-install markdownlint-cli2` did not install or
run a linter. The local npm invocation attempted to reach the registry and was
blocked by the restricted runner environment:

```text
npm error code EPERM
npm error syscall connect
npm error FetchError: request to https://registry.npmjs.org/markdownlint-cli2 failed
```

### `python scripts/release/check_changelog.py --version 1.7.0`

Result: blocked because this checkout does not contain the issue-named script.

```text
can't open file '/Users/macworkers/Projects/attestplane-local-runner/scripts/release/check_changelog.py': [Errno 2] No such file or directory
```

## Local Checks Run

### Whitespace / patch sanity

Command:

```sh
git diff --check
```

Result: pass, no output.

### Release-note contract check

Command:

```sh
python - <<'PY'
from pathlib import Path
required = [
    'first stable release since `v1.5.0`',
    '`3f551d9` requires strict consumers to reject empty proof bundles',
    'Issue 1 tightens the minimum signed-attestation schema',
    'Issue 3 adds the SDK migration path',
    '## What Integrators Must Do',
    'https://github.com/attestplane/attestplane/issues/120',
    'https://github.com/attestplane/attestplane/issues/125',
]
for rel in [Path('docs/release-notes/v1.7.0.md'), Path('docs/release-notes/v1.7.0.draft.md')]:
    text = rel.read_text(encoding='utf-8')
    missing = [needle for needle in required if needle not in text]
    if missing:
        raise SystemExit(f'{rel}: missing {missing!r}')
print('release note contract check passed')
PY
```

Result:

```text
release note contract check passed
```

### Product delta gate check

Command:

```sh
python scripts/release/release_gate.py \
  --release-tag v1.7.0 \
  --channel latest \
  --require-product-delta \
  --product-delta-base v1.5.0 \
  --product-delta-head HEAD \
  --json
```

Result: pass. The JSON output reported:

```json
{
  "decision": {
    "audit_required": false,
    "reasons": [
      "default_fast_track"
    ],
    "track": "fast"
  },
  "product_delta": {
    "allowed": true,
    "reason": "product_implementation_delta"
  },
  "verification": {
    "allowed": true,
    "reason": "audit_not_required"
  }
}
```

### Content grep

Command:

```sh
rg -n 'first stable release since `v1\.5\.0`|What Integrators Must Do|3f551d9|5b32c86|Issue #119|Issue #120|Issue #125|ProofBundleBuilder\.minimal|EmptyProofBundleError|IncompleteProofBundleError' CHANGELOG.md docs/release-notes/v1.7.0.md docs/release-notes/v1.7.0.draft.md docs/contributor/api-reference.md
```

Result: pass. Matches were found in the final release note, draft release note,
changelog, and SDK API-reference migration note.

### Secret / local-hostname grep

Command:

```sh
rg -n 'secret|private key|github token|openai token|chatgpt|\.pypirc|\.npmrc|internal runner|signing key' CHANGELOG.md docs/release-notes/v1.7.0.md docs/release-notes/v1.7.0.draft.md docs/contributor/api-reference.md
```

Result: no matches in the new v1.7.0 release notes or SDK migration note. The
only match was a pre-existing historical `CHANGELOG.md` line about an
ADR-0005 operator signing-key term outside this change's v1.7.0 section.
