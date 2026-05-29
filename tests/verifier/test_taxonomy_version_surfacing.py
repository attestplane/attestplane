# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from attestplane.cli.main import main
from attestplane.verifier import verify_proof_bundle

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "positive" / "minimal.json"


def _run(argv: list[str], capsys) -> tuple[int, str, str]:
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_taxonomy_version_is_threaded_across_sdk_json_and_explain(capsys) -> None:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = verify_proof_bundle(bundle)

    assert result.taxonomy_version == 1

    rc, stdout, stderr = _run(["verify", "--json", str(FIXTURE)], capsys)
    assert rc == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["taxonomy_version"] == result.taxonomy_version

    rc, stdout, stderr = _run(["verify", "--explain", str(FIXTURE)], capsys)
    assert rc == 0
    assert stderr == ""
    assert f"taxonomy_version={result.taxonomy_version}" in stdout

    rc, stdout, stderr = _run(["verify", "--json", "--explain", str(FIXTURE)], capsys)
    assert rc == 0
    assert stderr == ""
    explain_payload = json.loads(stdout)
    assert explain_payload["taxonomy_version"] == result.taxonomy_version
    explanation = explain_payload["explanation"]
    assert isinstance(explanation, list)
    assert explanation
    assert f"taxonomy_version={result.taxonomy_version}" in explanation[0]["message"]
