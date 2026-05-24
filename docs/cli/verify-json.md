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
When the two are combined, the explanatory text is carried in
`reasons[].message` while stdout remains valid JSON.

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
