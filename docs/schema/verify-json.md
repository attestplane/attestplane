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
  `att.verify.schema_version_missing` and use the quarantine exit code.
- An unsupported bundle or payload schema version should remain a rejected
  verifier result, surface `att.verify.schema_version_unsupported` in the
  reason list, and use the quarantine exit code.
- A fail-closed critical/required field should remain a rejected verifier
  result, surface `att.verify.schema_unknown` in the reason list, and use
  the quarantine exit code.
- Additive unknown fields are preserved verbatim by the caller and ignored by
  the verifier. They do not affect `ok` when the rest of the bundle is valid.
- `schema_version` compatibility is independent from the verifier reason-code
  taxonomy version documented in `docs/errors.md`.
- `taxonomy_version` pins the shared verifier rejection taxonomy used by both
  `verify --json` and `verify --explain`.
- `reason_code` is the top-level machine-readable primary rejection code, or
  `null` on pass.
- `anchoring.status` is an additive status enum that consumers can branch on
  without parsing the free-form reason list.
- `anchoring.quarantined` is the stable boolean companion to the exit code;
  it is `true` when the bundle was fail-closed into quarantine and `false`
  otherwise.
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
- Quarantined bundles map to exit code `2`. Hard verifier failures continue
  to map to exit code `1`, and malformed input that cannot be parsed or read
  continues to map to exit code `3`.
- When `--explain` is combined with `--json`, the payload remains valid JSON
  and exposes both `explanation[]` and the per-reason `explanation` field for
  callers that already inspect `reasons[]`.
- Malformed input that cannot be parsed as JSON or read from disk uses the
  usage-error exit code, distinct from quarantine.

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
