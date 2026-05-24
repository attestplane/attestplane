# `verify --json` Schema Version Policy

`verify --json` is a CLI report contract, not a bundle wire-format schema.
Its fields are additive-only for v1.7.x consumers, while bundle
`schema_version` handling continues to follow the wire-format policy in
[`docs/schema/schema-version-policy.md`](./schema-version-policy.md).

## Policy

- A supported bundle schema version should verify normally.
- An unsupported bundle or payload schema version should remain a rejected
  verifier result and surface `att.verify.schema_version_unsupported` in the
  reason list.
- Additive future-minor bundles should set `schema_version_forward_compat: true`
  in the structured JSON output.
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
- [`docs/schema/schema-version-policy.md`](./schema-version-policy.md) -
  wire-format `schema_version` rules for proof bundles.
