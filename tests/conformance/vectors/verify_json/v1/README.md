# `verify --json` v1 Contract Fixtures

These fixtures pin the current v1 `attestplane verify --json` contract for CI
consumers.

The checked-in examples cover:

- one success case
- one rejection case

The stable top-level fields are:

- `schema_version`
- `verdict`
- `result`
- `exit_code`
- `reason_code`
- `taxonomy_version`
- `reasons`
- `bundle`

The contract is additive at the top level: new optional top-level keys may be
added in future releases, but removing or renaming the stable fields above
must be treated as a breaking change.
