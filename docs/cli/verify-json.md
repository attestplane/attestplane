# `attestplane verify --json`

`attestplane verify --json` emits the machine-readable verifier result used by
the v1.7.x support-task delta. It is the JSON companion to the human-facing
`verify --explain` path.

## Output Contract

The JSON payload includes the verifier outcome plus the machine-readable
reason surface:

- `ok`
- `error_code`
- `primary_reason`
- `secondary_reasons`
- `chain_result.reason`
- the existing compatibility fields such as `retention_proofs_reason` and
  `signed_attestation_schema_reason`

Successful results use `primary_reason: null` and `secondary_reasons: []`.
Rejected results should be consumed by checking the exit code first and then
inspecting the reason list.

## `verify --explain`

`verify --explain` is the operator-oriented companion to `verify --json`.
Use it when a person needs the failure summary; use `verify --json` when a CI
job or integration needs machine-readable branching.

## Reason List

When you need a compact `reasons[]` view, derive it from the JSON payload:

```sh
jq -cr '"'"'[.primary_reason] + .secondary_reasons | map(select(. != null))'"'"' verify.json
```

This keeps the exit code as the gate while still exposing the ordered
reason list for downstream policy decisions.

## CI Gating Example

```sh
attestplane verify "$bundle" --json > verify.json
rc=$?

reasons=$(jq -cr '"'"'[.primary_reason] + .secondary_reasons | map(select(. != null))'"'"' verify.json)

if [ "$rc" -ne 0 ]; then
  printf '"'"'verify failed (rc=%s)\n'"'"' "$rc"
  printf '"'"'%s\n'"'"' "$reasons" | jq -r '"'"'.[]'"'"'
  exit "$rc"
fi
```

## See Also

- [`docs/errors.md`](../errors.md) - `att.verify.*` reason-code taxonomy
  reference from Issue #172.
- [`docs/schema/verify-json.md`](../schema/verify-json.md) - schema-version
  policy for verifier JSON consumers.
