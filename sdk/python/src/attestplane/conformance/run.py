# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Local conformance runner used by issue validation."""

from __future__ import annotations

import argparse
import sys

from attestplane.conformance.negative_vectors import (
    assert_negative_vector,
    load_negative_canonicalization_vectors,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m attestplane.conformance.run")
    parser.add_argument(
        "--negative",
        action="store_true",
        help="run the negative canonicalization vector corpus",
    )
    args = parser.parse_args(argv)

    if not args.negative:
        parser.print_help(sys.stderr)
        return 2

    vectors = load_negative_canonicalization_vectors()
    for vector in vectors:
        assert_negative_vector(vector)
        sys.stdout.write(
            f"{vector['case_id']}: {vector['expected']['reason_code']} {vector['expected']['pointer']}\n"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
