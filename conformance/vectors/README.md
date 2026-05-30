<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Forward-Compatible Additive Field Conformance

This directory pins the top-level additive-optional forward-compatibility rule:

- `additive_optional_pass` carries an unknown top-level field (`future_field`)
  that is neither required nor fail-closed. Verifiers must preserve the bundle
  and report PASS.
- `critical_required_fail` carries a `critical_`-prefixed top-level field.
  Verifiers must fail closed with `att.verify.schema_unknown`.

The positive vector is intentionally paired with the critical-field negative
guard so future changes cannot weaken the verifier's forward-compatibility
boundary without breaking this fixture set.

Relevant issue trail:

- #185 – landed the additive forward-compatible `schema_version` rules
- #292, #280, #275 – consolidated into this positive-path vector
- #363 – this positive acceptance vector and its documentation pin
