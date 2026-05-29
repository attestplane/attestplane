#!/usr/bin/env python3.11
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
"""Display the current autodev Temporal pipeline status table."""

import os
import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "autodev_state.db"
DB_PATH = Path(os.environ.get("AUTODEV_DB_PATH", DEFAULT_DB_PATH))

TABLE_COLUMNS = ("issue_number", "stage", "pr_number", "branch", "updated_at")


def _format_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _print_table(rows: list[sqlite3.Row]) -> None:
    data = [
        {column: _format_value(row[column]) for column in TABLE_COLUMNS}
        for row in rows
    ]
    widths = {
        column: max(len(column), *(len(row[column]) for row in data))
        for column in TABLE_COLUMNS
    }

    header = " | ".join(column.ljust(widths[column]) for column in TABLE_COLUMNS)
    print(header)
    for row in data:
        print(" | ".join(row[column].ljust(widths[column]) for column in TABLE_COLUMNS))


def main() -> int:
    if not DB_PATH.exists():
        print(f"autodev state database not found: {DB_PATH}")
        return 0

    try:
        with sqlite3.connect(DB_PATH) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT issue_number, stage, pr_number, branch, updated_at
                FROM pipeline_runs
                ORDER BY updated_at DESC, issue_number DESC
                """
            ).fetchall()
    except sqlite3.Error as exc:
        print(f"unable to read autodev state database: {exc}")
        return 0

    _print_table(rows)
    if not rows:
        print("No pipeline runs found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
