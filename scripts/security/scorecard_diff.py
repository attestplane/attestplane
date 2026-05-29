#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Compare normalized OpenSSF Scorecard summaries.

The input format is a small JSON summary file, not the raw GitHub Actions
artifact. The monitor script stores the latest normalized summary on disk and
this module compares it against the previous baseline without making Scorecard a
release gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

SCHEMA = "attestplane.scorecard.summary.v1"
DIFF_SCHEMA = "attestplane.scorecard.diff.v1"
DEFAULT_MEANINGFUL_DROP = 1.0


@dataclass(frozen=True)
class ScorecardCheck:
    name: str
    score: float
    reason: str = ""

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"name": self.name, "score": self.score}
        if self.reason:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class ScorecardSummary:
    schema: str
    repo: str
    score: float
    checks: tuple[ScorecardCheck, ...]
    generated_at: str = ""
    source: str = ""

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema": self.schema,
            "repo": self.repo,
            "score": self.score,
            "checks": [check.as_dict() for check in self.checks],
        }
        if self.generated_at:
            payload["generated_at"] = self.generated_at
        if self.source:
            payload["source"] = self.source
        return payload


@dataclass(frozen=True)
class ScorecardRegression:
    name: str
    baseline_score: float
    current_score: float

    @property
    def drop(self) -> float:
        return self.baseline_score - self.current_score

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "baseline_score": self.baseline_score,
            "current_score": self.current_score,
            "drop": self.drop,
        }


@dataclass(frozen=True)
class ScorecardDiff:
    baseline: ScorecardSummary
    current: ScorecardSummary
    regressions: tuple[ScorecardRegression, ...]
    missing_checks: tuple[str, ...]
    new_checks: tuple[str, ...]
    score_drop: float
    meaningful_regression: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": DIFF_SCHEMA,
            "baseline": self.baseline.as_dict(),
            "current": self.current.as_dict(),
            "regressions": [regression.as_dict() for regression in self.regressions],
            "missing_checks": list(self.missing_checks),
            "new_checks": list(self.new_checks),
            "score_drop": self.score_drop,
            "meaningful_regression": self.meaningful_regression,
        }


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _check_name(raw: dict[str, object]) -> str:
    for key in ("name", "check", "check_name", "rule"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(f"scorecard check is missing a name: {raw!r}")


def _check_score(raw: dict[str, object]) -> float:
    for key in ("score", "value", "normalized_score"):
        value = _coerce_float(raw.get(key))
        if value is not None:
            return value
    result = str(raw.get("result") or raw.get("status") or raw.get("state") or "").strip().lower()
    if result in {"pass", "passed", "success", "succeeded"}:
        return 10.0
    if result in {"fail", "failed", "failure", "error"}:
        return 0.0
    raise ValueError(f"scorecard check is missing a usable score: {raw!r}")


def _check_reason(raw: dict[str, object]) -> str:
    for key in ("reason", "message", "details"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _normalize_checks(raw_checks: object) -> tuple[ScorecardCheck, ...]:
    if not isinstance(raw_checks, list):
        raise ValueError("scorecard summary 'checks' must be a list")
    checks: list[ScorecardCheck] = []
    for raw in raw_checks:
        if not isinstance(raw, dict):
            raise ValueError(f"scorecard check must be a dict: {raw!r}")
        checks.append(
            ScorecardCheck(
                name=_check_name(raw),
                score=_check_score(raw),
                reason=_check_reason(raw),
            ),
        )
    return tuple(checks)


def _summary_score(raw: dict[str, object], checks: tuple[ScorecardCheck, ...]) -> float:
    for key in ("score", "overall_score", "aggregate_score"):
        value = _coerce_float(raw.get(key))
        if value is not None:
            return value
    if checks:
        return round(sum(check.score for check in checks) / len(checks), 2)
    raise ValueError("scorecard summary must include a score or at least one check")


def load_summary(path: Path) -> ScorecardSummary:
    raw = _load_json(path)
    if not isinstance(raw, dict):
        raise ValueError(f"scorecard summary must be a JSON object: {path}")

    schema = str(raw.get("schema") or SCHEMA)
    if schema != SCHEMA:
        raise ValueError(f"scorecard summary schema mismatch: expected {SCHEMA!r}, got {schema!r}")

    checks = _normalize_checks(raw.get("checks", []))
    repo_value = raw.get("repo")
    repo = str(repo_value).strip() if repo_value is not None else ""
    generated_at = str(raw.get("generated_at") or raw.get("generatedAt") or "").strip()
    source = str(raw.get("source") or "").strip()
    score = _summary_score(raw, checks)

    return ScorecardSummary(
        schema=schema,
        repo=repo,
        score=score,
        checks=checks,
        generated_at=generated_at,
        source=source,
    )


def compare_summaries(
    baseline: ScorecardSummary,
    current: ScorecardSummary,
    *,
    meaningful_drop: float = DEFAULT_MEANINGFUL_DROP,
) -> ScorecardDiff:
    baseline_checks = {check.name: check for check in baseline.checks}
    current_checks = {check.name: check for check in current.checks}

    regressions: list[ScorecardRegression] = []
    missing_checks: list[str] = []
    for name, baseline_check in baseline_checks.items():
        current_check = current_checks.get(name)
        if current_check is None:
            missing_checks.append(name)
            continue
        if current_check.score < baseline_check.score:
            regressions.append(
                ScorecardRegression(
                    name=name,
                    baseline_score=baseline_check.score,
                    current_score=current_check.score,
                ),
            )

    new_checks = sorted(name for name in current_checks if name not in baseline_checks)
    score_drop = baseline.score - current.score
    meaningful = bool(missing_checks)
    if score_drop >= meaningful_drop:
        meaningful = True
    if any(regression.drop >= meaningful_drop for regression in regressions):
        meaningful = True
    if any(regression.baseline_score > 0 and regression.current_score <= 0 for regression in regressions):
        meaningful = True

    return ScorecardDiff(
        baseline=baseline,
        current=current,
        regressions=tuple(sorted(regressions, key=lambda item: (-item.drop, item.name))),
        missing_checks=tuple(sorted(missing_checks)),
        new_checks=tuple(new_checks),
        score_drop=round(score_drop, 2),
        meaningful_regression=meaningful,
    )


def _build_report(baseline_path: Path, current_path: Path, meaningful_drop: float) -> ScorecardDiff:
    baseline = load_summary(baseline_path)
    current = load_summary(current_path)
    return compare_summaries(baseline, current, meaningful_drop=meaningful_drop)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument(
        "--meaningful-drop",
        type=float,
        default=DEFAULT_MEANINGFUL_DROP,
        help="Minimum aggregate or per-check score drop to count as a meaningful regression.",
    )
    args = parser.parse_args(argv)

    report = _build_report(args.baseline, args.current, args.meaningful_drop)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 1 if report.meaningful_regression else 0


if __name__ == "__main__":
    raise SystemExit(main())
