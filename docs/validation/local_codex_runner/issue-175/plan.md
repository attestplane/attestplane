# Issue 175 Implementation Plan

Plan ID: `e1a00e102aecf1fc`

## Scope

Add focused property coverage for the restricted-JCS canonicalization helper and keep the verifier signed-schema round-trip regression selected by the issue validation command. This should be a pure test addition: no canonicalization behavior change, no fixture regeneration, no release workflow change.

This runner phase used only local repository files, local command output, and the issue text. The project-level Opus consultation requirement is not executed in this phase because the runner prompt explicitly forbids external advisory services.

## Current Local Findings

- Python canonicalization lives in `sdk/python/src/attestplane/canonical.py`.
- The canonicalizer returns `bytes`, and `bytes` are also a documented accepted input type that canonicalizes to a base64url JSON string. Therefore the literal property `canonicalize(canonicalize(x)) == canonicalize(x)` is not valid for this API: for example, canonical bytes passed back into `canonicalize()` are treated as payload bytes, not as already-canonical JSON.
- The implementable idempotency property should be canonical byte reparse idempotency: `canonicalize(json.loads(canonicalize(x).decode("utf-8"))) == canonicalize(x)`. This preserves the issue intent across primitive values, objects, arrays, dataclasses, datetimes, and bytes after they have been projected into the canonical JSON value domain.
- Hypothesis is already available in the Python dev extra in `sdk/python/pyproject.toml`, and existing property tests already use it in `sdk/python/tests/test_properties.py`; no new heavy dependency is needed.
- There is no current `tests/canonicalization/` directory, but the issue validation command expects `pytest tests/canonicalization -k property`.
- Positive canonicalization vectors are loaded through `tests/conformance/canonicalization_vectors.py` and replayed in `tests/conformance/test_canonicalization_minimum_bundle_vectors.py`.
- Signed-schema round-trip coverage already lives in `tests/verifier/test_signed_schema_roundtrip.py`; the validation selector `pytest tests/verifier -k round_trip` should continue selecting meaningful tests there.

## Implementation Approach

1. Add a new focused canonicalization property test module under `tests/canonicalization/`.
   - Prefer `tests/canonicalization/test_canonicalization_properties.py`.
   - Keep test names containing `property` so `pytest tests/canonicalization -k property` selects the new coverage.
   - Import the canonicalization vector helper with the same local `importlib.util.spec_from_file_location(...)` pattern used by existing verifier/conformance tests, avoiding package layout assumptions.

2. Implement table-driven idempotency coverage for all positive vectors.
   - Load each positive vector with `load_positive_canonicalization_vectors()`.
   - Emit the corresponding minimum bundle with `emit_positive_canonicalization_bundle(vector)`.
   - Compute canonical bytes from the bundle, parse those bytes with `json.loads(...)`, and assert canonicalizing the parsed value returns the exact same bytes.
   - Also run the property against representative direct-domain table cases covering `None`, booleans, signed int64 boundaries, NFC strings with escapes, bytes, UTC datetimes, lists, nested dicts, tuples, and a dataclass such as `SubjectRef`.

3. Implement generated idempotency coverage with Hypothesis.
   - Reuse or locally duplicate the lightweight strategy pattern from `sdk/python/tests/test_properties.py`: bounded recursive values, signed 64-bit integers, small lists/dicts, and NFC-safe text.
   - Add generated accepted extended-domain values for bytes and UTC datetimes through `st.one_of(...)` so documented non-JSON Python input types are included.
   - Use tight settings, for example `max_examples=50` and small recursive sizes, so the required test command stays comfortably under 10 seconds.
   - The asserted property should be the byte reparse form, not direct `canonicalize(canonicalize(x))`, for the API reason documented above.

4. Implement commutativity coverage for independent normalization stages without changing runtime code.
   - In the test module, add small test-only pure helpers for the three independent stages:
     - key sorting by recursively rebuilding dicts with sorted string keys;
     - Unicode NFC validation/projection for strings, matching the current helper's reject-non-NFC contract;
     - number canonicalization validation for signed 64-bit integers and rejection of floats.
   - Generate only values inside the documented accepted domain for the positive commutativity property.
   - Apply the three stages in every permutation and assert all permutations produce the same canonical bytes as `canonicalize(value)`.
   - Include at least one table case that combines unsorted keys, NFC non-ASCII strings, nested arrays/objects, and int64 boundary values so the stages are exercised together.
   - Add a negative guard for non-NFC text and/or out-of-range integers to confirm the helper still rejects invalid inputs instead of repairing them.

5. Keep verifier round-trip coverage unchanged unless the selector is ineffective.
   - Run `pytest tests/verifier -k round_trip` after adding tests.
   - If the selector unexpectedly misses the existing `roundtrip` tests because of underscore naming, make the smallest test-name adjustment in `tests/verifier/test_signed_schema_roundtrip.py` that preserves behavior and improves selector clarity. Do not change verifier runtime logic for this issue.

6. Avoid fixture and release-surface churn.
   - Do not edit existing positive/negative vector JSON files.
   - Do not update `sdk/python/tests/conformance/FIXTURE_HASHES.lock`.
   - Do not change `sdk/python/src/attestplane/canonical.py` unless implementation reveals the existing helper violates the documented spec; such a runtime defect should be escalated separately rather than folded into this pure test task.

## Files Likely To Change

- `tests/canonicalization/test_canonicalization_properties.py` (new)
- `tests/canonicalization/__init__.py` only if local test import behavior requires it; prefer omitting it if pytest discovery works without it.
- `tests/verifier/test_signed_schema_roundtrip.py` only if `pytest tests/verifier -k round_trip` does not select the intended existing round-trip tests.
- `docs/validation/local_codex_runner/issue-175/code.md` in the implementation phase.
- `docs/validation/local_codex_runner/issue-175/test.md` in the validation phase.
- `docs/validation/local_codex_runner/issue-175/review.md` if a later review phase is run.

Files that should normally remain unchanged:

- `sdk/python/src/attestplane/canonical.py`
- `sdk/typescript/src/canonical.ts`
- `tests/conformance/vectors/canonicalization/**/*.json`
- `sdk/python/tests/conformance/FIXTURE_HASHES.lock`
- Release runbooks, package manifests, and publishing configuration.

## Tests And Local Gates

Issue-required validation:

```bash
PYTHONPATH=sdk/python/src pytest tests/canonicalization -k property
PYTHONPATH=sdk/python/src pytest tests/verifier -k round_trip
```

Focused supporting checks:

```bash
PYTHONPATH=sdk/python/src pytest tests/conformance/test_canonicalization_minimum_bundle_vectors.py -q
PYTHONPATH=sdk/python/src pytest sdk/python/tests/test_canonical.py sdk/python/tests/test_properties.py -q
PYTHONPATH=sdk/python/src pytest tests/verifier/test_signed_schema_roundtrip.py -q
```

Local gate before closure:

```bash
run_gate attestplane
```

If `run_gate attestplane` is unavailable in this checkout, record that in `docs/validation/local_codex_runner/issue-175/test.md` and run the focused commands above without weakening any required release gate.

## Risk Classification

Risk: Low.

Reason: the intended work is additive test coverage only, uses an existing dev dependency, and does not change canonicalization runtime behavior or public fixtures. The main risk is semantic ambiguity in the issue's literal idempotency expression because `canonicalize()` returns bytes and bytes are valid payload inputs. The mitigation is to document the API mismatch in evidence and assert canonical byte reparse idempotency, which is the closed-form invariant for the canonical JSON output domain.

There is a small timing risk from property tests. Keep generated structures bounded and Hypothesis example counts modest so the required command remains under 10 seconds on the existing runner.

## Evidence Files To Update

- `docs/validation/local_codex_runner/issue-175/plan.md` for this planning phase.
- `docs/validation/local_codex_runner/issue-175/code.md` in the implementation phase, listing exact test files added and the idempotency interpretation used.
- `docs/validation/local_codex_runner/issue-175/test.md` in the validation phase, with exact outputs from the issue-required commands and focused supporting checks.
- `docs/validation/local_codex_runner/issue-175/review.md` if review is run.

Do not update release assets, package manifests, fixture lock files, or schema hash locks for this pure test task.

## Safety Confirmation

This task will not merge branches, create or move tags, publish npm packages, publish PyPI packages, push to PyPI, push to any remote, or weaken release gates. It will not lower P0/P1 severity, remove failing tests to manufacture a pass, loosen claim-safety policy, or read/log credentials files such as ChatGPT cookies, GitHub tokens, OpenAI tokens, private keys, `.pypirc`, or `.npmrc`.
