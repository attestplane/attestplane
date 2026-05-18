# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "release/artifacts/v0.0.2-alpha.manifest.json"
CHECKER_PATH = REPO_ROOT / "scripts/release/check_release_artifact_manifest.py"
CHECKSUM_PATH = REPO_ROOT / "scripts/release/generate_checksums.py"


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


checker = load_script(CHECKER_PATH, "check_release_artifact_manifest")
checksums = load_script(CHECKSUM_PATH, "generate_checksums")


def manifest_copy() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def write_manifest(tmp_path: Path, manifest: dict[str, object]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_release_artifact_manifest_valid() -> None:
    manifest = manifest_copy()
    assert checker.validate_manifest(manifest, MANIFEST_PATH) == []


def test_release_artifact_manifest_missing_schema_version_fails(tmp_path: Path) -> None:
    manifest = manifest_copy()
    manifest.pop("schema_version")
    path = write_manifest(tmp_path, manifest)
    assert checker.run(argparse.Namespace(manifests=[path])) == 1


def test_published_artifact_requiring_checksum_without_checksum_fails(tmp_path: Path) -> None:
    manifest = manifest_copy()
    artifact = {
        "checksum_required": True,
        "kind": "python_wheel",
        "name": "python-wheel",
        "notes": "Synthetic published wheel for checker regression.",
        "published": True,
        "required": True,
        "signature_required": False,
    }
    manifest["artifacts"] = [artifact]
    manifest["checksums"] = []
    path = write_manifest(tmp_path, manifest)
    errors = checker.validate_manifest(manifest, path)
    assert any("published artifact requiring checksum has no checksum entry" in error for error in errors)


def test_signature_required_without_signature_fails(tmp_path: Path) -> None:
    manifest = manifest_copy()
    artifact = dict(manifest["artifacts"][1])  # type: ignore[index]
    artifact["published"] = True
    artifact["signature_required"] = True
    manifest["artifacts"] = [artifact]
    manifest["checksums"] = [{"artifact": artifact["name"], "sha256": "0" * 64}]
    manifest["signatures"] = []
    path = write_manifest(tmp_path, manifest)
    errors = checker.validate_manifest(manifest, path)
    assert any("signature_required=true but no signature entry exists" in error for error in errors)


def test_forbidden_supply_chain_claim_outside_no_go_fails(tmp_path: Path) -> None:
    manifest = manifest_copy()
    manifest["notes"] = "SLSA L3 completed"
    path = write_manifest(tmp_path, manifest)
    errors = checker.validate_manifest(manifest, path)
    assert any("forbidden phrase appears outside no_go_claims" in error for error in errors)


def test_checksum_generation_is_deterministic(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("attestplane\n", encoding="utf-8")
    first = checksums.build_report([artifact], tmp_path)
    second = checksums.build_report([artifact], tmp_path)
    assert first == second
    entry = first["checksums"][0]
    assert entry["name"] == "artifact.txt"
    assert entry["sha256"] == "537023571ff1c2cd92ac6f0f9a4bd43da6a9eed37acbd109796f4615a4a50c2a"
