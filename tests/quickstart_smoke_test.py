# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Smoke coverage for the executable quickstart walkthrough."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs.run_quickstart import (
    QuickstartFailure,
    parse_quickstart_blocks,
    run_quickstart,
)


def test_parse_quickstart_blocks_extracts_marked_blocks_with_line_numbers(tmp_path: Path) -> None:
    doc = tmp_path / "quickstart.md"
    doc.write_text(
        """# Demo

<!-- quickstart-smoke:install -->
```bash
pip install attestplane
```

Some prose.

<!-- quickstart-smoke:python -->
```python
print("hello")
```

```bash
echo "not marked"
```

<!-- quickstart-smoke:verify -->
```bash
$ attestplane inspect chain.jsonl
```
""",
        encoding="utf-8",
    )

    blocks = parse_quickstart_blocks(doc)

    assert [block.label for block in blocks] == ["install", "python", "verify"]
    assert [block.language for block in blocks] == ["bash", "python", "bash"]
    assert [block.start_line for block in blocks] == [4, 11, 20]
    assert [block.end_line for block in blocks] == [6, 13, 22]
    assert blocks[2].code == "$ attestplane inspect chain.jsonl"


def test_run_quickstart_replays_the_real_docs_walkthrough() -> None:
    blocks = run_quickstart(Path("docs/quickstart.md"))

    assert [block.label for block in blocks] == ["install", "python", "inspect"]


def test_quickstart_failure_reports_file_and_line(tmp_path: Path) -> None:
    doc = tmp_path / "quickstart.md"
    doc.write_text(
        """# Demo

<!-- quickstart-smoke:broken -->
```bash
false
```
""",
        encoding="utf-8",
    )

    with pytest.raises(QuickstartFailure) as exc_info:
        run_quickstart(doc)

    message = str(exc_info.value)
    assert f"{doc}:4" in message
    assert "quickstart block 'broken' failed with exit code 1" in message
    assert "command: false" in message
