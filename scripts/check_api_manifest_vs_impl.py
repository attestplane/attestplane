#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Doc-drift baseline: diff the SDK public-API surface against doc references.

Read-only inspection script. Computes two drift sets between the public
Python API exported from ``sdk/python/src/attestplane/__init__.py`` and
the symbols mentioned in the canonical-spec and architecture docs:

- ``drift_out``: symbols documented in ``docs/spec/`` or
  ``docs/architecture/`` that are NOT exported by the SDK. These are
  "stale-doc" hits — docs reference a name the runtime no longer offers.
  Each entry carries a ``class`` field: ``ghost`` (no ``class``/``def``
  for the name anywhere under ``sdk/python/src/attestplane/``) or
  ``unexported`` (a real ``class``/``def`` exists but the name is not
  in ``__all__``).
- ``drift_in``: symbols exported by the SDK that are NOT mentioned in
  any documentation file under ``docs/spec/`` or ``docs/architecture/``.
  Informational only — some helpers are intentionally undocumented.

A ``.api-drift-baseline.json`` file at the repo root (if present) lists
known-stale entries that are accepted as-is. The gate fails non-zero
only when drift_out contains NAMES NOT in the baseline (i.e. new drift).
Cleanup PRs that fix a ghost (docs typo) or add an unexported symbol
to ``__all__`` MUST shrink the baseline by removing the corresponding
entry.

This script NEVER writes under ``docs/spec/`` — the
``aia-12-aligned-profile.md`` profile is frozen and only read here.

Fail-closed: any parser error, missing file, or unexpected schema raises
and the process exits non-zero.

Usage::

    python3 scripts/check_api_manifest_vs_impl.py             # report to stdout
    python3 scripts/check_api_manifest_vs_impl.py --write     # also write JSON
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INIT_PATH = REPO_ROOT / "sdk" / "python" / "src" / "attestplane" / "__init__.py"
SDK_PKG_DIR = REPO_ROOT / "sdk" / "python" / "src" / "attestplane"
DOC_DIRS = (REPO_ROOT / "docs" / "spec", REPO_ROOT / "docs" / "architecture")
REPORTS_DIR = REPO_ROOT / "reports"
REPORT_PATH = REPORTS_DIR / "api-drift.json"
BASELINE_PATH = REPO_ROOT / ".api-drift-baseline.json"
BASELINE_SCHEMA = "attestplane.api-drift-baseline.v1"

# Match a backticked identifier or ``attestplane.X[.Y]`` reference.
# Identifiers are public-API names (no leading underscore).
_IDENT = r"[A-Z_][A-Za-z0-9_]*"
_DOTTED = r"attestplane(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
BACKTICK_IDENT_RE = re.compile(rf"`({_IDENT})`")
DOTTED_RE = re.compile(rf"`?({_DOTTED})`?")


def _literal_string_list(node: ast.AST) -> list[str]:
    if not isinstance(node, ast.List):
        return []
    out: list[str] = []
    for item in node.elts:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            out.append(item.value)
    return out


def extract_public_api(init_path: Path) -> set[str]:
    """Return the union of ``__all__`` entries declared in ``__init__.py``.

    Handles both the top-level ``__all__`` and conditional
    ``__all__.extend([...])`` branches used for optional extras.
    """
    if not init_path.is_file():
        raise FileNotFoundError(f"public-API source missing: {init_path}")
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    symbols: set[str] = set()

    def _visit(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        symbols.update(_literal_string_list(node.value))
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "__all__"
                    and call.func.attr in {"extend", "append"}
                ):
                    for arg in call.args:
                        symbols.update(_literal_string_list(arg))
            elif isinstance(node, ast.If):
                _visit(node.body)
                _visit(node.orelse)
            elif isinstance(node, ast.Try):
                _visit(node.body)
                for handler in node.handlers:
                    _visit(handler.body)
                _visit(node.orelse)
                _visit(node.finalbody)

    _visit(tree.body)
    if not symbols:
        raise RuntimeError(
            f"no __all__ entries extracted from {init_path}; "
            "fail-closed: refusing to compute drift against an empty surface"
        )
    return symbols


def extract_doc_symbols(doc_dirs: tuple[Path, ...]) -> set[str]:
    """Scan markdown files for public-API symbol references.

    Two reference shapes count:
    1. Backticked CamelCase / UPPER_SNAKE identifiers: ```Identifier```.
    2. Dotted ``attestplane.X[.Y]`` references (terminal segment counts).
    """
    seen: set[str] = set()
    for doc_dir in doc_dirs:
        if not doc_dir.is_dir():
            raise FileNotFoundError(f"docs directory missing: {doc_dir}")
        for md in sorted(doc_dir.rglob("*.md")):
            text = md.read_text(encoding="utf-8")
            for m in BACKTICK_IDENT_RE.finditer(text):
                seen.add(m.group(1))
            for m in DOTTED_RE.finditer(text):
                dotted = m.group(1)
                tail = dotted.rsplit(".", 1)[-1]
                seen.add(tail)
    return seen


def compute_drift(
    exported: set[str], documented: set[str]
) -> tuple[set[str], set[str]]:
    """Return ``(drift_out, drift_in)``.

    drift_out: documented but not exported (stale docs).
    drift_in: exported but not documented (informational).
    """
    drift_out = documented - exported
    drift_in = exported - documented
    return drift_out, drift_in


# Tokens that look like public-API names but are language/typing stdlib
# vocabulary or prose meta-references. Excluded from drift-out so the
# gate fires on actual stale public-API references, not on documentation
# discussing typing primitives.
_PROSE_META_NOISE = frozenset(
    {
        "Infinity",
        "None",
        "True",
        "False",
        "TypedDict",
        "UPPER_SNAKE_CASE",
        "KeyObject",
    }
)


def filter_drift_out(drift_out: set[str], exported: set[str]) -> set[str]:
    """Restrict drift-out to plausibly-public-API names.

    Many backticked tokens in docs are unrelated identifiers (e.g.
    ``in-toto``, ``DSSE``, JSON field names) or typing-stdlib prose
    references (``TypedDict``, ``None``). We restrict drift-out to
    references that look like the public-API naming style (CamelCase
    or UPPER_SNAKE longer than three characters) AND that are not on
    the prose-meta noise list.
    """
    out: set[str] = set()
    for name in drift_out:
        if name in exported:
            continue
        if name in _PROSE_META_NOISE:
            continue
        if len(name) <= 3:
            continue
        # CamelCase: starts upper, has at least one lower.
        is_camel = name[0].isupper() and any(c.islower() for c in name)
        # UPPER_SNAKE: all upper with underscore.
        is_upper_snake = name.isupper() and "_" in name
        if is_camel or is_upper_snake:
            out.add(name)
    return out


def load_baseline(baseline_path: Path) -> dict[str, str]:
    """Return ``{name: class}`` from the baseline file, or empty if absent.

    Fail-closed on JSON parse error or unexpected schema. A missing file
    is fine (no baseline = every drift_out entry is "new").
    """
    if not baseline_path.is_file():
        return {}
    raw = baseline_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    schema = data.get("schema")
    if schema != BASELINE_SCHEMA:
        raise RuntimeError(
            f"baseline schema mismatch: expected {BASELINE_SCHEMA!r}, got {schema!r}"
        )
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise RuntimeError("baseline 'entries' must be a list")
    out: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError(f"baseline entry not a dict: {entry!r}")
        name = entry.get("name")
        cls = entry.get("class")
        if not isinstance(name, str) or cls not in {"ghost", "unexported"}:
            raise RuntimeError(f"baseline entry malformed: {entry!r}")
        out[name] = cls
    return out


# Match a top-level (or nested) ``class Name`` / ``def Name`` declaration.
_CLASS_DEF_RE_TPL = r"^[[:space:]]*(class|def)[[:space:]]+{name}\b"


def classify_drift_entry(name: str, sdk_pkg_dir: Path) -> str:
    """Return ``"unexported"`` if a ``class``/``def`` for ``name`` exists
    under ``sdk_pkg_dir``; otherwise ``"ghost"``.

    Pure-Python scan (no subprocess). Stops at first hit.
    """
    pattern = re.compile(rf"^[ \t]*(?:class|def)[ \t]+{re.escape(name)}\b", re.MULTILINE)
    for py in sdk_pkg_dir.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except OSError:
            continue
        if pattern.search(text):
            return "unexported"
    return "ghost"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="also write reports/api-drift.json",
    )
    args = parser.parse_args(argv)

    exported = extract_public_api(INIT_PATH)
    documented = extract_doc_symbols(DOC_DIRS)
    raw_drift_out, drift_in = compute_drift(exported, documented)
    drift_out = filter_drift_out(raw_drift_out, exported)

    baseline = load_baseline(BASELINE_PATH)
    new_drift = drift_out - set(baseline.keys())

    drift_out_entries = [
        {
            "name": name,
            "class": baseline.get(name)
            or classify_drift_entry(name, SDK_PKG_DIR),
        }
        for name in sorted(drift_out)
    ]

    report = {
        "schema": "attestplane.api-drift.v2",
        "init_path": str(INIT_PATH.relative_to(REPO_ROOT)),
        "doc_dirs": [str(p.relative_to(REPO_ROOT)) for p in DOC_DIRS],
        "exported_count": len(exported),
        "documented_count": len(documented),
        "drift_out": drift_out_entries,
        "drift_in": sorted(drift_in),
        "drift_out_count": len(drift_out),
        "drift_in_count": len(drift_in),
        "baseline_count": len(baseline),
        "new_drift": sorted(new_drift),
        "new_drift_count": len(new_drift),
    }

    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    if args.write:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    sys.stderr.write(
        f"summary: baseline={len(baseline)}, "
        f"current_drift={len(drift_out)}, "
        f"new_drift={len(new_drift)}\n"
    )

    if report["new_drift_count"] > 0:
        sys.stderr.write(
            f"FAIL: {report['new_drift_count']} NEW drift-out entries "
            "(symbols documented but not exported by SDK, not in baseline). "
            "See new_drift[] in the JSON report. Either fix the docs reference "
            "(ghost) or add the symbol to __all__ (unexported), or add the "
            "entry to .api-drift-baseline.json if it is a known stale case.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
