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
- `bundle.schema_version` is the proof-bundle schema version currently handled
  by this verifier contract.
- `bundle.digest` is the SHA-256 digest of the input bundle bytes.

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
bundle forward-compatibility rules documented in #217. The shared
`att.verify.*` reason-code taxonomy lives in `docs/errors.md`.

When the two flags are combined, the explanatory text is carried in
`reasons[].message` while stdout remains valid JSON.

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
