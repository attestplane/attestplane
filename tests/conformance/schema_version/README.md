<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Schema Version Conformance

This directory pins the `schema_version` forward-compatibility rule set.

- `additive_minor_ok` and `additive_with_unknown_field_ok` must verify as
  valid. They lock the additive-optional path introduced in #185: unknown
  optional fields under `schema_version` may be preserved and must not fail
  verification.
- `unknown_required_field` must continue to fail with the schema-unknown
  quarantine path.
- `missing`, `unknown_major`, and `major_version_ahead` must continue to
  reject unsupported or missing `schema_version` values.

The positive vector is intentionally paired with the required-field and major
version negatives so future changes cannot weaken the verifier's
forward-compatibility boundary without breaking this fixture set.

Relevant issue trail:

- #185 - landed the additive forward-compatible `schema_version` rules
- #173 / #210 - the negative/positive gap this fixture set closes
- #363 - this positive acceptance vector and its documentation pin
