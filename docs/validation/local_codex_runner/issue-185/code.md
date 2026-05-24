# Issue 185 Code Evidence

Plan ID: `961921d4a1b1325d`

Implemented locally without web search, browser tools, external advisory
services, publishing, tagging, merging, or remote pushes.

## Runtime Changes

- Added `schema_version` to proof bundles and enforced `MAJOR.MINOR` parsing in
  the Python verifier and CLI.
- Rejects unsupported major versions and missing schema version metadata with
  dedicated reason labels.
- Accepts future minor versions with additive top-level fields and records the
  forward-compatibility signal in structured JSON output as
  `schema_version_forward_compat: true`.
- Added `--explain` output for the informational forward-compatibility path
  without changing rejection semantics.

## Schema And Docs

- Updated the v1 proof-bundle schema to require `schema_version`.
- Added `docs/schema/schema-version-policy.md`.
- Updated the verifier JSON docs and release-note delta to describe the policy
  and the migration note that older bundles continue to verify.
- Added a short schema README cross-reference and release-note link coverage.

## Test Surface

- Added a dedicated schema-version policy test for the Python SDK path.
- Added a conformance matrix for missing version, unsupported major, and
  unknown-field handling.
- Added negative vectors for the schema-version policy cases.
- Updated CLI and verifier tests for the new reason labels and JSON fields.
- Added TypeScript parity coverage for the required `schema_version` field and
  forward-compatibility result flag.
- Brought the legacy minimum-schema negative bundle fixtures up to the new
  top-level `schema_version` contract so they continue to exercise their
  intended signature-shape failures.
- Refreshed `sdk/python/tests/conformance/FIXTURE_HASHES.lock` after the fixture
  updates and the new schema-version vectors landed.

## Scope Confirmation

- No merge, tag, publish, or remote-push action was taken.
- No release gate was weakened.
- No bundle re-issuance was required.
