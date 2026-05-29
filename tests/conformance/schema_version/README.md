<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Schema-Version Conformance Policy

The `additive_optional_pass` vector documents the forward-compatible rule for
`schema_version=1`: unknown additive-optional fields are accepted when the rest
of the proof bundle is valid.

The companion `unknown_required_field` vector keeps the boundary pinned: a
required-field or `critical_`-prefixed change still fails closed with
`att.verify.schema_unknown`.

This corpus is additive-only. Do not bump `schema_version` for optional field
additions.
