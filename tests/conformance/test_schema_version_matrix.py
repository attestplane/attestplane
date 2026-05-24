# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from attestplane.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "bundles"


def _load_bundle(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _write_bundle(tmp_path: Path, name: str, bundle: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_future_minor_bundle_accepts_and_sets_forward_compat(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["verify", "--json", str(FIXTURES / "future_minor.json")])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["result"] == "accept"
    assert payload["ok"] is True
    assert payload["schema_version_forward_compat"] is True


@pytest.mark.parametrize(
    ("mutation", "expected_label", "expected_reason"),
    [
        ({"schema_version": "2.0"}, "schema_version_major_unsupported", "att.verify.schema_version_unsupported"),
        ({"schema_version": None}, "schema_version_missing", "att.verify.required_field_missing"),
        ({"extra_top_level_field": {"enabled": True}}, "unknown_field", "att.verify.schema_unknown"),
    ],
)
def test_schema_version_rejections_surface_policy_labels(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutation: dict[str, object],
    expected_label: str,
    expected_reason: str,
) -> None:
    bundle = copy.deepcopy(_load_bundle("valid_signed_attestation.json"))
    if mutation.get("schema_version", "present") is None:
        bundle.pop("schema_version", None)
    elif "schema_version" in mutation:
        bundle["schema_version"] = mutation["schema_version"]
    else:
        bundle["extra_top_level_field"] = mutation["extra_top_level_field"]

    path = _write_bundle(tmp_path, f"{expected_label}.json", bundle)

    rc = main(["verify", "--json", str(path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert payload["result"] == "reject"
    assert payload["ok"] is False
    assert payload["schema_version_forward_compat"] is False
    assert payload["primary_reason"] == expected_reason
    assert expected_label in payload["detail"]


def test_explain_reports_schema_version_policy_labels(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle = copy.deepcopy(_load_bundle("valid_signed_attestation.json"))
    bundle["schema_version"] = "2.0"
    path = _write_bundle(tmp_path, "major-unsupported.json", bundle)

    rc = main(["verify", "--explain", str(path)])
    out = capsys.readouterr().out

    assert rc == 2
    assert "schema_version_major_unsupported" in out
