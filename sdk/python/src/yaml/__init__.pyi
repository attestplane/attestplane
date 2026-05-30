# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Minimal PyYAML type stubs for local mypy runs."""


class YAMLError(Exception): ...


def safe_load(stream: object) -> object: ...
