# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Digest-level regression guard for the canonicalization golden fixture."""

from __future__ import annotations

import hashlib

from attestplane.canonical import canonicalize
from attestplane.verify_reason_codes import VERIFY_REASON_TAXONOMY_VERSION

from tests.conformance.canonicalization_vectors import (
    emit_positive_canonicalization_bundle,
    load_canonicalization_golden_fixture,
    positive_canonicalization_vectors_by_case,
)


def test_canonical_digest_golden_fixture_matches_expected_hash() -> None:
    fixture = load_canonicalization_golden_fixture()
    vector = positive_canonicalization_vectors_by_case()[fixture["source_positive_case"]]
    bundle = emit_positive_canonicalization_bundle(vector)
    canonical_bytes = canonicalize(bundle)
    expected_bytes = fixture["canonical_bytes_path"].read_bytes()

    assert canonical_bytes == expected_bytes
    assert hashlib.sha256(canonical_bytes).hexdigest() == fixture["canonical_bytes_sha256_hex"]
    assert fixture["generated_under"]["schema_version"] == bundle["chain_metadata"]["schema_version"]
    assert fixture["generated_under"]["taxonomy_version"] == VERIFY_REASON_TAXONOMY_VERSION
