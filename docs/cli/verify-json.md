# `attestplane verify --json`

`attestplane verify --json` emits the machine-readable verifier result used by
the v1.7.x support-task delta. It is the JSON companion to the human-facing
`verify --explain` path.

## Output Contract

The JSON payload includes the verifier outcome plus the machine-readable
reason surface:

- `result`
- `ok`
- `error_code`
- `primary_reason`
- `secondary_reasons`
- `schema_version_forward_compat`
- `chain_result.reason`
- the existing compatibility fields such as `retention_proofs_reason` and
  `signed_attestation_schema_reason`

Successful results use `result: accept`, `primary_reason: null`, and
`secondary_reasons: []`.
Rejected results should be consumed by checking the exit code first and then
inspecting the reason list.

## `verify --explain`

`verify --explain` is the operator-oriented companion to `verify --json`.
Use it when a person needs the failure summary; use `verify --json` when a CI
job or integration needs machine-readable branching.

When a bundle is accepted through the forward-compatible additive path,
`verify --explain` prints the `schema_version_forward_compat` note so the
operator can see that the bundle was accepted because its minor version is
newer than the verifier's known minor.

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
- [`docs/schema/schema-version-policy.md`](../schema/schema-version-policy.md)
  - proof-bundle `schema_version` compatibility policy.
