# `verify --json` Schema Version Policy

`verify --json` is a CLI report contract, not a bundle wire-format schema.
Its fields are additive-only for v1.7.x consumers, while bundle
`schema_version` handling continues to follow the wire-format policy in
[`schemas/v1/README.md`](../../schemas/v1/README.md). The companion
`verify --explain` surface is additive as well: it does not bump
`schema_version`, and it only enriches the human-readable rejection text that
accompanies the structured JSON contract.

## Policy

- A supported bundle schema version should verify normally.
- A missing bundle schema version should surface
  `att.verify.schema_version_missing`.
- An unsupported bundle or payload schema version should remain a rejected
  verifier result and surface `att.verify.schema_version_unsupported` in the
  reason list.
- A fail-closed critical/required field should remain a rejected verifier
  result and surface `att.verify.schema_unknown` in the reason list.
- Additive unknown fields are preserved verbatim by the caller and ignored by
  the verifier. They do not affect `ok` when the rest of the bundle is valid.
- `schema_version` compatibility is independent from the verifier reason-code
  taxonomy version documented in `docs/errors.md`.
- `taxonomy_version` pins the shared verifier rejection taxonomy used by both
  `verify --json` and `verify --explain`.
- `reason_code` is the top-level machine-readable primary rejection code, or
  `null` on pass.
- `anchoring` is an additive advisory object. It is always present and carries
  `anchoring_status ∈ {verified, quarantined, absent}` plus a nullable
  `quarantine_reason`. By default, quarantined anchoring is advisory only;
  pass `--strict-anchoring` to turn it into a hard failure.
- `explanation[]` is the additive operator-facing companion surface. Each
  item carries `primary_reason`, `pointer`, and `message`; successful results
  use a single compact summary item, while rejected results mirror the
  ordered reason list.
- The verifier reason-code taxonomy is additive-only, and code values are not
  reused within a stable taxonomy version.
- Consumers should keep branching on exit code first, then inspect `result`
  and `reasons[]` for diagnostics.
- `verify --explain` stays aligned with the same JSON contract and does not
  introduce a new schema or a new bundle policy.
- When `--explain` is combined with `--json`, the payload remains valid JSON
  and exposes both `explanation[]` and the per-reason `explanation` field for
  callers that already inspect `reasons[]`.

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
