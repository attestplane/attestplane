# Proof-Bundle `schema_version` Policy

`proof_bundle.schema.json` now carries a top-level `schema_version` field in
`MAJOR.MINOR` form. The verifier uses it to decide whether a bundle is a
current-line bundle or a forward-compatible additive bundle.

## Supported Shape

- `schema_version` is required at the proof-bundle top level.
- The value must parse as `MAJOR.MINOR`.
- The current verifier line supports `1.7`.
- The `chain_metadata.schema_version` field remains the independent substrate
  canonicalization version and is not part of this policy.

## Rejection Rules

- Missing `schema_version` is rejected with the `schema_version_missing`
  policy label.
- A major version greater than the verifier's supported major is rejected with
  `schema_version_major_unsupported`.
- Unknown top-level fields are rejected with `unknown_field` when the bundle's
  minor version is not greater than the verifier's known minor.

## Forward Compatibility

- Bundles with a future minor version are accepted when the major still
  matches the supported major.
- Unknown top-level fields are accepted only on that forward-compatible path.
- Every accepted future-minor bundle records
  `schema_version_forward_compat: true` in `attestplane verify --json`.
- `verify --explain` surfaces the forward-compatibility status as an
  informational line for operators.

## Consumer Guidance

- Use `result` or `ok` in the JSON payload to gate automation.
- Use `schema_version_forward_compat` to detect the additive-accept path.
- Use `--explain` for human review when you need to see the schema-version
  compatibility detail alongside the normal verifier summary.

## Cross-References

- [`docs/schema/verify-json.md`](./verify-json.md)
- [`docs/cli/verify-json.md`](../cli/verify-json.md)
- [`schemas/v1/proof_bundle.schema.json`](../../schemas/v1/proof_bundle.schema.json)
