# GA/CA Cut Evidence for v0.8.5-rc.5

Date: 2026-05-20

This document records the currently available evidence for the GA/Controlled
Availability decision gate.

## Current Release State

- Git HEAD before this evidence document: `d7e5d7a`
- Latest RC tag: `v0.8.5-rc.5`
- GitHub `release-cd` run: `26161926322`
- PyPI package: `attestplane==0.8.5rc5`
- npm package: `@attestplane/attestplane@0.8.5-rc.5`
- npm dist-tags:
  - `rc`: `0.8.5-rc.5`
  - `latest`: `0.8.0-beta.0`
  - `beta`: `0.8.0-beta.0`
  - `alpha`: `0.7.0-alpha`

`autodev-train` was paused after `v0.8.5-rc.5` so the train does not
automatically cut `v0.8.5-rc.6` while GA/CA evidence is being completed.

## Clean Install Smoke

### PyPI

Command:

```bash
PY312=/Users/macworkers/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/bin/python3.12
rm -rf /tmp/attestplane-ga-ca-pip-smoke
"$PY312" -m venv /tmp/attestplane-ga-ca-pip-smoke
/tmp/attestplane-ga-ca-pip-smoke/bin/python -m pip install --upgrade pip
/tmp/attestplane-ga-ca-pip-smoke/bin/python -m pip install 'attestplane==0.8.5rc5'
/tmp/attestplane-ga-ca-pip-smoke/bin/python - <<'PY'
import attestplane
print(getattr(attestplane, "__version__", "missing"))
PY
/tmp/attestplane-ga-ca-pip-smoke/bin/attestplane --help
```

Result: PASS

Observed version: `0.8.5rc5`

### npm

Command:

```bash
rm -rf /tmp/attestplane-ga-ca-npm-smoke
mkdir -p /tmp/attestplane-ga-ca-npm-smoke
cd /tmp/attestplane-ga-ca-npm-smoke
npm init -y
npm install '@attestplane/attestplane@0.8.5-rc.5'
node --input-type=module - <<'JS'
import * as attestplane from '@attestplane/attestplane';
console.log(Object.keys(attestplane).slice(0, 12).join(','));
console.log('ProofBundleBuilder' in attestplane);
JS
```

Result: PASS

Observed package import included `ProofBundleBuilder`.

## Conformance Evidence

### Python

Command:

```bash
sdk/python/.venv/bin/python -m pytest -q \
  sdk/python/tests/test_conformance.py \
  sdk/python/tests/test_conformance_negative.py \
  sdk/python/tests/conformance/test_verifier_conformance.py \
  sdk/python/tests/test_adapter_conformance.py
```

Result: PASS

Observed result: `38 passed in 0.18s`

Coverage:

- canonical conformance vectors
- negative conformance vectors
- verifier conformance vectors
- adapter conformance fixtures

### TypeScript

Command:

```bash
cd sdk/typescript
npm test -- \
  test/conformance.test.ts \
  test/verifier_conformance.test.ts \
  test/adapter_conformance.test.ts \
  test/package_import_smoke.test.ts
```

Result: PASS

Observed result:

- 4 test files passed
- 29 tests passed

Coverage:

- canonical conformance vectors
- verifier conformance vectors
- adapter conformance fixtures
- package import smoke

## Cross-SDK Roundtrip

Command:

```bash
PATH="$PWD/sdk/python/.venv/bin:$PATH" bash scripts/test-cross-sdk-roundtrip.sh
```

Result: PASS

Observed result:

- Python emitted 8 text and 5 JSON canonical outputs.
- TypeScript re-emitted all 13 outputs.
- Python verified all 13 outputs.
- Py/TS outputs were byte-identical.

## Remaining GA/CA Decision Gaps

This evidence does not by itself authorize GA or Controlled Availability.
Remaining decision items:

1. Maintainers must define whether `ca` means GA/stable or Controlled
   Availability.
2. Stable GA still requires an explicit npm `latest` migration decision.
3. Release notes must record the selected channel and claim boundary.
4. Rollback ownership and registry correction steps must be accepted by the
   maintainer.
5. Release permissions should remain scoped to GitHub `release-cd`; no PR or
   fork workflow should inherit publishing authority.

Until those decisions are made, `v0.8.5-rc.5` remains the latest RC, and npm
`latest` remains pinned to `0.8.0-beta.0`.
