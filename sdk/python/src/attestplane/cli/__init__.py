# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""``attestplane`` CLI entry-point.

Exported function :func:`main` is wired up via the ``[project.scripts]``
table in ``pyproject.toml``::

    attestplane verify <bundle.json>              # chain/report-oriented check
    attestplane verify-proofbundle <bundle.json>  # alpha local JSON verifier report
    attestplane inspect <chain.jsonl>             # print a chain summary
    attestplane export <chain.jsonl>              # build a proof bundle from a JSONL chain
"""

from attestplane.cli.main import main

__all__ = ["main"]
