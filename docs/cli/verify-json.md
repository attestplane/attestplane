# `attestplane verify --json`

`attestplane verify --json` emits one deterministic JSON document to stdout.
It is the machine-readable companion to the human-oriented `verify` summary.

`verify --explain` remains the operator-friendly path when a human needs the
failure narrative rather than the structured report.

## Output Contract

The payload is a single report envelope with stable key order:

```json
{
  "schema_version": "1",
  "bundle_schema_version": 1,
  "ok": false,
  "reasons": [
    {
      "code": "REASON_REQUIRED_FIELD_MISSING",
      "field": "/events",
      "message": "events must contain at least one event"
    }
  ],
  "verifier_version": "1.7.6"
}
```

Field meaning:

- `schema_version` identifies the CLI report schema. It is independent of the
  bundle schema version.
- `bundle_schema_version` echoes the bundle's schema/bundle version.
- `ok` mirrors the verifier exit status: `true` for success, `false` for
  rejection.
- `reasons[]` is the ordered machine-readable failure list. It is empty when
  `ok=true`.
- `verifier_version` is the CLI/verifier semver string.

The report is additive-only. Future fields such as `severity` may be added to
each reason entry without breaking v1 consumers, but the current schema omits
that field.

## CI Gating

Use the exit code as the gate and inspect `reasons[]` only after a non-zero
result:

```sh
attestplane verify --json "$bundle" > verify.json
rc=$?

if [ "$rc" -ne 0 ]; then
  jq -r '"'"'.reasons[] | [.code, .field, .message] | @tsv'"'"' verify.json
  exit "$rc"
fi
```

If you need to diff a stable snapshot, normalize the JSON first:

```sh
attestplane verify --json "$bundle" | jq -S . > actual.json
diff -u tests/golden/verify-json/valid_minimal.json actual.json
```

## See Also

- [`docs/schema/verify-json.md`](../schema/verify-json.md) - schema-version
  policy for the CLI report envelope.
- [`docs/errors.md`](../errors.md) - the `att.verify.*` taxonomy used by the
  internal verifier result.
