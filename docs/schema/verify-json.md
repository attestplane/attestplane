# `verify --json` Schema Version Policy

`verify --json` is a CLI report contract, not a bundle wire-format schema.
Its fields are additive-only for v1.7.x consumers, while bundle
`schema_version` handling continues to follow the wire-format policy in
[`schemas/v1/README.md`](../../schemas/v1/README.md).

## Policy

- A supported bundle schema version should verify normally.
- A missing bundle schema version should surface
  `att.verify.schema_version_missing`.
- An unsupported bundle or payload schema version should remain a rejected
  verifier result and surface `att.verify.schema_version_unsupported` in the
  reason list.
- Additive unknown fields are preserved verbatim by the caller and ignored by
  the verifier. They do not affect `ok` when the rest of the bundle is valid.
- `schema_version` compatibility is independent from the verifier reason-code
  taxonomy version documented in `docs/errors.md`.
- Consumers should keep branching on exit code first, then inspect
  `primary_reason` and `secondary_reasons`.

## Negative Vectors

The negative conformance vectors under
`tests/conformance/vectors/negative/` pin the strict failure cases for
required fields, missing signatures, and schema-version behavior.

## Cross-Reference

- [`docs/cli/verify-json.md`](../cli/verify-json.md) - consumer-facing JSON
  contract.
- [`docs/errors.md`](../errors.md) - reason-code taxonomy and compatibility
  notes.
- [`schemas/v1/README.md`](../../schemas/v1/README.md) - wire-format
  `schema_version` rules for the v1 schemas.
