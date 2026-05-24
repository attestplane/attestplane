# `verify --json` Schema Version Policy

`verify --json` emits a CLI report schema, not the proof-bundle wire-format
schema.

## Policy

- `schema_version: "1"` is the version of the CLI report envelope.
- `bundle_schema_version` echoes the version declared by the bundle itself.
- A supported bundle version should verify normally and surface `ok: true`.
- An unsupported or malformed bundle should remain a rejected verifier result
  with `ok: false` and a populated `reasons[]` list.
- The CLI report schema is additive-only: future fields may be added without
  breaking consumers that branch on `schema_version`, `ok`, and `reasons[]`.
- Exit code remains the primary gate; JSON consumers should inspect
  `reasons[]` only after a non-zero exit code.

## Negative Vectors

The negative conformance vectors under `tests/conformance/vectors/negative/`
pin the strict failure cases for required fields, signature presence, and
schema-version behavior.

## Cross-Reference

- [`docs/cli/verify-json.md`](../cli/verify-json.md) - consumer-facing JSON
  contract.
- [`docs/errors.md`](../errors.md) - the internal `att.verify.*` taxonomy.
- [`schemas/v1/README.md`](../../schemas/v1/README.md) - wire-format
  `schema_version` rules for the v1 schemas.
