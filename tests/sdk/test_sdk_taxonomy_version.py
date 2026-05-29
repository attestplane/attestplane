# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""SDK regression coverage for resolved verifier taxonomy surfacing."""

from __future__ import annotations

import copy

from attestplane.sdk import ProofBundleBuilder, verify_minimum_bundle
from attestplane.signing import InMemoryKeyProvider, Signer


SUBJECT_DIGEST = "3f551d9" + "0" * 57


def _signer() -> Signer:
    return Signer(
        chain_id="taxonomy-version",
        key_provider=InMemoryKeyProvider(seed=b"\x12" * 32),
    )


def test_verify_minimum_bundle_result_surfaces_taxonomy_version_and_legacy_null() -> None:
    bundle = ProofBundleBuilder.minimal(SUBJECT_DIGEST, _signer())
    legacy_bundle = copy.deepcopy(bundle)
    del legacy_bundle["chain_metadata"]["evidence_taxonomy_version"]

    result = verify_minimum_bundle(bundle)
    legacy_result = verify_minimum_bundle(legacy_bundle)

    assert result.ok is True
    assert result.taxonomy_version == 1
    assert legacy_result.ok is True
    assert legacy_result.taxonomy_version is None
