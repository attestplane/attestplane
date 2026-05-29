#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Stage a versioned static site for the generated API reference.

The staging helper copies rendered pdoc and typedoc trees into a stable
release-line layout. It rejects prerelease tags so the public ``latest`` path
cannot be repointed to an alpha, beta, or rc build.
"""

from __future__ import annotations

import argparse
import dataclasses
import html
import re
import shutil
from pathlib import Path


_STABLE_TAG_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


@dataclasses.dataclass(frozen=True)
class ReleaseRef:
    tag: str
    major: int
    minor: int
    patch: int

    @property
    def line(self) -> str:
        return f"v{self.major}.{self.minor}"

    @property
    def is_stable(self) -> bool:
        return True


def parse_release_tag(tag: str) -> ReleaseRef:
    match = _STABLE_TAG_RE.fullmatch(tag)
    if match is None:
        raise ValueError(
            "stable API reference publication only accepts suffix-free release tags "
            f"of the form vX.Y.Z, got {tag!r}"
        )
    return ReleaseRef(
        tag=tag,
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
    )


def _redirect_html(title: str, target: str) -> str:
    escaped_target = html.escape(target, quote=True)
    escaped_title = html.escape(title)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f'  <meta http-equiv="refresh" content="0; url={escaped_target}">\n'
        f'  <link rel="canonical" href="{escaped_target}">\n'
        f"  <title>{escaped_title}</title>\n"
        "</head>\n"
        "<body>\n"
        f'  <p>Redirecting to <a href="{escaped_target}">{escaped_target}</a></p>\n'
        "</body>\n"
        "</html>\n"
    )


def _api_landing_html(ref: ReleaseRef) -> str:
    release_root = f"./releases/{ref.tag}/"
    line_root = f"./lines/{ref.line}/"
    latest_root = "./latest/"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        "  <title>Attestplane API reference</title>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        "    <h1>Attestplane API reference</h1>\n"
        f'    <p>Latest stable release: <a href="{html.escape(latest_root, quote=True)}">{html.escape(ref.tag)}</a></p>\n'
        f'    <ul><li><a href="{html.escape(release_root, quote=True)}">Exact release snapshot</a></li>'
        f'<li><a href="{html.escape(line_root, quote=True)}">Stable release line</a></li>'
        f'<li><a href="{html.escape(latest_root, quote=True)}">Latest stable</a></li></ul>\n'
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def _release_landing_html(ref: ReleaseRef) -> str:
    line_root = f"../../lines/{ref.line}/"
    latest_root = "../../latest/"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>Attestplane API reference {html.escape(ref.tag)}</title>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        f"    <h1>Attestplane API reference {html.escape(ref.tag)}</h1>\n"
        f'    <ul><li><a href="./python/">Python SDK</a></li>'
        f'<li><a href="./typescript/">TypeScript SDK</a></li>'
        f'<li><a href="{html.escape(line_root, quote=True)}">Stable release line</a></li>'
        f'<li><a href="{html.escape(latest_root, quote=True)}">Latest stable</a></li></ul>\n'
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def _copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"missing rendered API reference directory: {src}")
    shutil.copytree(src, dst, dirs_exist_ok=True)


def stage_api_reference_site(
    *,
    release_tag: str,
    python_dir: Path,
    typescript_dir: Path,
    site_root: Path,
) -> ReleaseRef:
    ref = parse_release_tag(release_tag)

    release_root = site_root / "api" / "releases" / ref.tag
    line_root = site_root / "api" / "lines" / ref.line
    latest_root = site_root / "api" / "latest"
    api_root = site_root / "api"

    _copy_tree(python_dir, release_root / "python")
    _copy_tree(typescript_dir, release_root / "typescript")

    release_root.mkdir(parents=True, exist_ok=True)
    api_root.mkdir(parents=True, exist_ok=True)

    (site_root / "index.html").write_text(
        _redirect_html("Attestplane API reference", "./api/latest/"),
        encoding="utf-8",
    )
    (api_root / "index.html").write_text(_api_landing_html(ref), encoding="utf-8")
    (release_root / "index.html").write_text(
        _release_landing_html(ref), encoding="utf-8"
    )

    line_root.mkdir(parents=True, exist_ok=True)
    (line_root / "index.html").write_text(
        _redirect_html(
            f"Attestplane API reference {ref.line}",
            f"../../releases/{ref.tag}/",
        ),
        encoding="utf-8",
    )

    latest_root.mkdir(parents=True, exist_ok=True)
    (latest_root / "index.html").write_text(
        _redirect_html(
            f"Attestplane API reference latest stable {ref.tag}",
            f"../releases/{ref.tag}/",
        ),
        encoding="utf-8",
    )

    return ref


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stage a versioned static site for the generated API reference."
    )
    parser.add_argument(
        "--release-tag", required=True, help="Stable release tag, e.g. v1.5.0"
    )
    parser.add_argument(
        "--python-dir", required=True, type=Path, help="Rendered pdoc output"
    )
    parser.add_argument(
        "--typescript-dir", required=True, type=Path, help="Rendered typedoc output"
    )
    parser.add_argument(
        "--site-root", required=True, type=Path, help="Output site root"
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    stage_api_reference_site(
        release_tag=args.release_tag,
        python_dir=args.python_dir,
        typescript_dir=args.typescript_dir,
        site_root=args.site_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
