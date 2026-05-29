# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "docs" / "stage_api_reference_site.py"

spec = importlib.util.spec_from_file_location("stage_api_reference_site", MODULE_PATH)
assert spec is not None
stage_api_reference_site = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["stage_api_reference_site"] = stage_api_reference_site
spec.loader.exec_module(stage_api_reference_site)


def _write_rendered_tree(root: Path, *, label: str) -> None:
    (root / "index.html").write_text(f"<h1>{label}</h1>", encoding="utf-8")
    (root / "nested").mkdir(parents=True, exist_ok=True)
    (root / "nested" / "asset.txt").write_text(label, encoding="utf-8")


def test_parse_release_tag_requires_suffix_free_stable_tag() -> None:
    ref = stage_api_reference_site.parse_release_tag("v1.5.0")

    assert ref.tag == "v1.5.0"
    assert ref.line == "v1.5"
    assert ref.is_stable is True


@pytest.mark.parametrize("tag", ["v1.5.0-rc.1", "v1.5.0-alpha.1", "1.5.0", "v1.5"])
def test_parse_release_tag_rejects_prerelease_and_non_tag_inputs(tag: str) -> None:
    with pytest.raises(ValueError, match="suffix-free release tags"):
        stage_api_reference_site.parse_release_tag(tag)


def test_stage_api_reference_site_writes_exact_release_line_and_latest_aliases(
    tmp_path: Path,
) -> None:
    python_dir = tmp_path / "python"
    typescript_dir = tmp_path / "typescript"
    site_root = tmp_path / "site"
    python_dir.mkdir()
    typescript_dir.mkdir()
    _write_rendered_tree(python_dir, label="python")
    _write_rendered_tree(typescript_dir, label="typescript")

    ref = stage_api_reference_site.stage_api_reference_site(
        release_tag="v1.5.0",
        python_dir=python_dir,
        typescript_dir=typescript_dir,
        site_root=site_root,
    )

    assert ref.tag == "v1.5.0"
    assert "./api/latest/" in (site_root / "index.html").read_text(encoding="utf-8")
    assert (site_root / "api" / "index.html").read_text(encoding="utf-8").count(
        "Exact release snapshot"
    ) == 1
    release_index = (
        site_root / "api" / "releases" / "v1.5.0" / "index.html"
    ).read_text(encoding="utf-8")
    assert "./python/" in release_index
    assert "./typescript/" in release_index
    assert "../../latest/" in release_index
    assert (
        site_root / "api" / "releases" / "v1.5.0" / "python" / "index.html"
    ).read_text(encoding="utf-8") == "<h1>python</h1>"
    assert (
        site_root
        / "api"
        / "releases"
        / "v1.5.0"
        / "typescript"
        / "nested"
        / "asset.txt"
    ).read_text(encoding="utf-8") == "typescript"

    latest_html = (site_root / "api" / "latest" / "index.html").read_text(
        encoding="utf-8"
    )
    line_html = (site_root / "api" / "lines" / "v1.5" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "../releases/v1.5.0/" in latest_html
    assert "../../releases/v1.5.0/" in line_html


def test_stage_api_reference_site_requires_stable_release_tag(tmp_path: Path) -> None:
    python_dir = tmp_path / "python"
    typescript_dir = tmp_path / "typescript"
    site_root = tmp_path / "site"
    python_dir.mkdir()
    typescript_dir.mkdir()
    _write_rendered_tree(python_dir, label="python")
    _write_rendered_tree(typescript_dir, label="typescript")

    with pytest.raises(ValueError, match="suffix-free release tags"):
        stage_api_reference_site.stage_api_reference_site(
            release_tag="v1.5.0-rc.1",
            python_dir=python_dir,
            typescript_dir=typescript_dir,
            site_root=site_root,
        )
