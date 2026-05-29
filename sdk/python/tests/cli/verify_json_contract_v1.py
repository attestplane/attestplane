# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Versioned golden fixture for ``attestplane verify --json`` contract v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PASS_FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"
FAIL_FIXTURE = ROOT / "fixtures" / "reject" / "canonicalization-edge.json"
UNKNOWN_REQUIRED_FIXTURE = ROOT / "tests" / "conformance" / "schema_version" / "unknown_required_field" / "bundle.json"

VERIFY_JSON_CONTRACT_V1: dict[str, Any] = {
    "schema_version": 1,
    "exit_codes": {
        "success": 0,
        "verification_failure": 1,
        "quarantined": 3,
        "usage_error": 2,
    },
    "cases": {
        "accept": {
            "fixture": str(PASS_FIXTURE.relative_to(ROOT)),
            "payload": {
                "bundle": {
                    "digest": "d4d37025f7452ad2525d6b37c898bf08cd335db3e7983ce04e242e898b77b2cb",
                    "schema_version": 1,
                },
                "exit_code": 0,
                "reason_code": None,
                "reasons": [],
                "result": "pass",
                "schema_version": 1,
                "taxonomy_version": 1,
            },
        },
        "verification_failure": {
            "fixture": str(FAIL_FIXTURE.relative_to(ROOT)),
            "payload": {
                "bundle": {
                    "digest": "914bdd3745f9566e4cf0c3c2dd2747b701f50ad4cb3dc0eeede5f16207748ffd",
                    "schema_version": 1,
                },
                "exit_code": 1,
                "reason_code": "att.verify.canonical_mismatch",
                "reasons": [
                    {
                        "code": "att.verify.canonical_mismatch",
                        "message": "canonicalization failed",
                        "path": "/events/0/event/payload/artifact_ref",
                    },
                ],
                "result": "fail",
                "schema_version": 1,
                "taxonomy_version": 1,
            },
        },
        "unknown_required_field": {
            "fixture": str(UNKNOWN_REQUIRED_FIXTURE.relative_to(ROOT)),
            "payload": {
                "bundle": {
                    "digest": "769cb4926ffdc6404ed733ceb54e5d1cac0aa9e60b15a32d8ea3d1ff3b59f56d",
                    "schema_version": 1,
                },
                "exit_code": 1,
                "reason_code": "att.verify.schema_unknown",
                "reasons": [
                    {
                        "code": "att.verify.schema_unknown",
                        "message": "bundle metadata closure failed",
                        "path": "/chain_metadata/critical_future_field",
                    },
                ],
                "result": "fail",
                "schema_version": 1,
                "taxonomy_version": 1,
            },
        },
    },
}


def render_verify_json_payload(payload: dict[str, Any]) -> str:
    """Render a payload with the canonical byte-stable CLI formatting."""

    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
