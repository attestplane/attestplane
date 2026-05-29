<!-- SPDX-FileCopyrightText: 2026 The Attestplane Authors -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# additive_with_unknown_field_ok

This fixture pins the #185 forward-compatible schema_version rule for an
additive optional field.

- `chain_metadata.future_metadata_field` is intentionally unknown to the
  current schema, but it is additive and optional, so the verifier must accept
  the bundle as valid.
- The companion negative fixture
  [`../unknown_required_field/bundle.json`](../unknown_required_field/bundle.json)
  keeps the breaking path covered: `chain_metadata.critical_future_field` is
  structural/required and must still reject.
- This closes the #173 / #210 documentation gap while staying aligned with the
  negative vectors already landed in #184 / #198.

