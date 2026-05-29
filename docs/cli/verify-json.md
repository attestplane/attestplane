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
  "reason_code": null,
  "taxonomy_version": 1,
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
- `reason_code` is the machine-readable primary verifier rejection code, or
  `null` on success.
- `taxonomy_version` pins the shared verifier rejection taxonomy that both
  `--json` and `--explain` use.
- `taxonomy_version` appears in the `verify --json` payload for both plain
  JSON mode and `verify --json --explain`; it is additive output metadata,
  not a bundle field.
- `reasons[]` is an ordered list of `{code, path, message}` entries.
- When `--explain` is set, the payload also includes a top-level
  `explanation[]` array with `{primary_reason, pointer, message}` entries.
  On success, the array contains a compact summary; on rejection, it mirrors
  the ordered rejection reasons.
- When `--explain` is set, each `reasons[]` item may also include an
  `explanation` field with the stable human rationale string for that reason
  code.
- `bundle.schema_version` is the proof-bundle schema version currently handled
  by this verifier contract.
- `bundle.digest` is the SHA-256 digest of the input bundle bytes.
- The verifier reason-code taxonomy is additive-only: new reason codes may be
  added, but existing codes are not renamed, removed, or reused within a
  stable `taxonomy_version`.

Consumers should keep branching on `exit_code` first and then inspect
`result`, `taxonomy_version`, and `reasons[]` for diagnostics. CI consumers
that pin the taxonomy should treat a `taxonomy_version` change as a contract
change and refresh the pinned expectation before relying on the reason-code
surface. For the versioning background, see
[`docs/release-notes/v1.7.x-delta.md`](../release-notes/v1.7.x-delta.md).

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
text is carried in `explanation[]` and `reasons[].explanation`.

When `--explain` is used without `--json`, stdout prints a compact
`OK|FAIL signer_subject=... schema_version=... anchor=...` summary and
stderr prints one rationale line per rejection reason in the same order as
the structured payload.

### Pass Example

```json
{
  "schema_version": 1,
  "result": "pass",
  "exit_code": 0,
  "reason_code": null,
  "taxonomy_version": 1,
  "reasons": [],
  "explanation": [
    {
      "primary_reason": null,
      "pointer": "/",
      "message": "signer_subject=key_id:... schema_version=1 anchor=absent"
    }
  ],
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
  "reason_code": "att.verify.schema_version_unsupported",
  "taxonomy_version": 1,
  "explanation": [
    {
      "primary_reason": "att.verify.schema_version_unsupported",
      "pointer": "/chain_metadata/schema_version",
      "message": "chain_metadata.schema_version=2; this verifier handles 1"
    }
  ],
  "reasons": [
    {
      "code": "att.verify.schema_version_unsupported",
      "path": "/chain_metadata/schema_version",
      "message": "chain_metadata.schema_version=2; this verifier handles 1"
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

Pinned CI consumers should assert the expected `taxonomy_version` before
depending on the reason-code set, because that field is the contract marker for
the shared `--json` / `--explain` taxonomy surface.

## See Also

- [`docs/schema/verify-json.md`](../schema/verify-json.md) - schema-version
  policy for the v1 verifier JSON contract.
- [`schemas/cli/verify-result-v1.json`](../../schemas/cli/verify-result-v1.json)
  - JSON Schema for the structured result.
- [`docs/errors.md`](../errors.md) - `att.verify.*` reason-code taxonomy.
- [`docs/release-notes/v1.7.x-delta.md`](../release-notes/v1.7.x-delta.md) -
  existing reason-code taxonomy versioning note referenced by the v1.8.x
  consumer-pinning delta.
