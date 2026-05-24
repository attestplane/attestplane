# `attestplane verify --json`

`attestplane verify --json` emits the machine-readable CI-gating contract for
`attestplane verify`. It is intentionally separate from the legacy
human-readable report fields.

## Output Contract

The payload is fixed at schema version 1:

```json
{
  "schema_version": 1,
  "result": "pass",
  "exit_code": 0,
  "reasons": [],
  "bundle": {
    "schema_version": 1,
    "digest": "..."
  }
}
```

- `schema_version` is the CLI result schema version.
- `result` is `pass` or `fail`.
- `exit_code` is the process exit code that callers should gate on.
- `reasons[]` is an ordered list of `{code, path, message}` entries.
- When `--explain` is set, each reason may also include an `explanation`
  field with the stable human rationale string for that reason code.
- `bundle.schema_version` is the proof-bundle schema version currently handled
  by this verifier contract.
- `bundle.digest` is the SHA-256 digest of the input bundle bytes.
- The verifier reason-code taxonomy is versioned separately via
  `taxonomy_version`. The taxonomy is additive-only: new reason codes may be
  added, but existing codes are not renamed, removed, or reused.

Consumers should keep branching on `exit_code` first and then inspect
`result` and `reasons[]` for diagnostics.

## `verify --explain`

`verify --explain` is the operator-oriented companion to `verify --json`.
Use it with `--json` when a CI gate needs machine-readable output and a human
still needs a plain-language rejection summary.

Synopsis:

```sh
attestplane verify --json --explain "$bundle"
```

The flag is additive: it does not bump `schema_version`, it does not change
the `verify --json` contract documented in #220, and it does not alter the
bundle forward-compatibility rules documented in #217. It also does not alter
`taxonomy_version`; the shared `att.verify.*` reason-code taxonomy lives in
`docs/errors.md`.

Within that taxonomy, additive unknown fields remain accepted, while
unsupported major versions and fail-closed critical/required fields surface
`att.verify.schema_version_unsupported` or `att.verify.schema_unknown`
respectively.

When the two flags are combined, stdout remains valid JSON and the rationale
text is carried in `reasons[].explanation`.

When `--explain` is used without `--json`, rationale lines are written to
stderr in reason-code order while stdout keeps the existing human summary.

### Pass Example

```json
{
  "schema_version": 1,
  "result": "pass",
  "exit_code": 0,
  "reasons": [],
  "bundle": {
    "schema_version": 1,
    "digest": "..."
  }
}
```

### Fail Example

```json
{
  "schema_version": 1,
  "result": "fail",
  "exit_code": 1,
  "reasons": [
    {
      "code": "att.verify.schema_version_unsupported",
      "path": "bundle.schema_version",
      "message": "bundle schema_version 2 is not supported"
    }
  ],
  "bundle": {
    "schema_version": 2,
    "digest": "..."
  }
}
```

## CI Gating Example

```sh
attestplane verify --json "$bundle" > verify.json
rc=$?

result=$(jq -r '.result' verify.json)

if [ "$rc" -ne 0 ] || [ "$result" != "pass" ]; then
  printf 'verify failed (rc=%s, result=%s)\n' "$rc" "$result"
  jq -r '.reasons[]? | "\(.code) \(.path) \(.message)"' verify.json
  exit "$rc"
fi
```

## See Also

- [`docs/schema/verify-json.md`](../schema/verify-json.md) - schema-version
  policy for the v1 verifier JSON contract.
- [`schemas/cli/verify-result-v1.json`](../../schemas/cli/verify-result-v1.json)
  - JSON Schema for the structured result.
- [`docs/errors.md`](../errors.md) - `att.verify.*` reason-code taxonomy.
