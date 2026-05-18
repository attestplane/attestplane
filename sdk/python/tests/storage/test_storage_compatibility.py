# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest

from attestplane.cli.main import main
from attestplane.storage.jsonl import JsonlStorageBackend

REPO_ROOT = Path(__file__).resolve().parents[4]
MANIFEST = REPO_ROOT / "storage/compat/storage_compatibility_v1.json"
CHECKER = REPO_ROOT / "scripts/storage/check_storage_compatibility.py"
FIXTURES = REPO_ROOT / "storage/compat/fixtures"


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


checker = load_script(CHECKER, "check_storage_compatibility")


def load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def write_manifest(tmp_path: Path, manifest: dict[str, object]) -> Path:
    path = tmp_path / "storage_compatibility.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def copy_fixture(tmp_path: Path, name: str) -> Path:
    dst = tmp_path / name
    shutil.copyfile(FIXTURES / name, dst)
    return dst


def test_storage_compatibility_manifest_checker_passes() -> None:
    assert checker.run(argparse.Namespace(manifest=MANIFEST, repo_root=REPO_ROOT)) == 0


def test_invalid_manifest_fails(tmp_path: Path) -> None:
    manifest = load_manifest()
    manifest["schema_version"] = "wrong"
    path = write_manifest(tmp_path, manifest)
    assert checker.run(argparse.Namespace(manifest=path, repo_root=REPO_ROOT)) == 1


def test_manifest_forbids_multi_writer_overclaim(tmp_path: Path) -> None:
    manifest = load_manifest()
    backend = dict(manifest["storage_backends"][0])  # type: ignore[index]
    backend["multi_writer_safe"] = True
    manifest["storage_backends"] = [backend]
    path = write_manifest(tmp_path, manifest)
    errors = checker.validate_manifest(manifest, path, REPO_ROOT)
    assert any("must not claim multi_writer_safe=true" in error for error in errors)


def test_manifest_forbids_destructive_repair_by_default(tmp_path: Path) -> None:
    manifest = load_manifest()
    migration = dict(manifest["migration_policy"])  # type: ignore[arg-type]
    migration["destructive_repair"] = "enabled_by_default"
    manifest["migration_policy"] = migration
    path = write_manifest(tmp_path, manifest)
    errors = checker.validate_manifest(manifest, path, REPO_ROOT)
    assert any("destructive repair must not be enabled by default" in error for error in errors)


def test_jsonl_valid_fixture_scans_clean(tmp_path: Path) -> None:
    path = copy_fixture(tmp_path, "jsonl_valid_v1.jsonl")
    scan = JsonlStorageBackend(path).scan()
    assert scan.ok is True
    assert len(scan.events) == 1
    assert scan.issues == ()


@pytest.mark.parametrize(
    ("fixture", "expected_kind", "valid_prefix"),
    [
        ("jsonl_partial_tail_v1.jsonl", "partial_trailing_line", 1),
        ("jsonl_malformed_middle_v1.jsonl", "malformed_json", 1),
        ("jsonl_unknown_record_version_v1.jsonl", "unknown_record_version", 0),
    ],
)
def test_jsonl_negative_fixtures_report_stable_issue_codes(
    tmp_path: Path, fixture: str, expected_kind: str, valid_prefix: int
) -> None:
    path = copy_fixture(tmp_path, fixture)
    scan = JsonlStorageBackend(path).scan()
    assert scan.ok is False
    assert len(scan.events) == valid_prefix
    assert scan.issues[0].kind == expected_kind
    assert scan.issues[0].line_no >= 1
    assert scan.issues[0].byte_offset >= 0


def test_export_refuses_corrupt_storage_by_default(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = copy_fixture(tmp_path, "jsonl_partial_tail_v1.jsonl")
    bundle_path = tmp_path / "bundle.json"
    rc = main(["export", str(chain_path), "--out", str(bundle_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["error"] == "storage_corruption"
    assert payload["issue"]["kind"] == "partial_trailing_line"
    assert not bundle_path.exists()


def test_inspect_reports_storage_issue_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chain_path = copy_fixture(tmp_path, "jsonl_malformed_middle_v1.jsonl")
    rc = main(["inspect", str(chain_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["storage_health"] == "corrupt"
    assert payload["issue"]["kind"] == "malformed_json"


def test_doctor_storage_capabilities_remain_alpha_safe(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["storage"]["backend"] == "jsonl"
    assert payload["storage"]["multi_writer_safe"] is False
    assert payload["storage"]["repair_supported"] is False
    assert payload["storage"]["destructive_repair_supported"] is False
