#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Decide whether a release should use fast track or audit track.

This is a P0 interface layer only. It does not create GitHub issues, call LLMs,
publish packages, or block the existing release train. Fast track remains the
default unless a high-risk release signal is present.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

TAG_RE = re.compile(
    r"^v(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<channel>alpha|beta|rc)\.(?P<ordinal>0|[1-9]\d*))?$"
)
AUDIT_LABELS = frozenset({"audit-required", "security", "compat-break"})
AUDIT_MILESTONES = frozenset({"ga", "ca"})


@dataclass(frozen=True)
class ReleaseGateDecision:
    track: str
    audit_required: bool
    reasons: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "track": self.track,
            "audit_required": self.audit_required,
            "reasons": self.reasons,
        }


def parse_release_tag(release_tag: str) -> tuple[int, int, int]:
    match = TAG_RE.fullmatch(release_tag)
    if match is None:
        raise ValueError("release tag must match vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH-(alpha|beta|rc).N")
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def audit_disabled(env: Mapping[str, str]) -> bool:
    return env.get("ATTESTPLANE_RELEASE_AUDIT", "").strip().lower() in {"0", "false", "no", "off"}


def decide_release_gate(
    *,
    release_tag: str,
    channel: str,
    labels: list[str],
    release_audit: bool,
    milestone: str | None,
    dependency_major_bump: bool,
    env: Mapping[str, str] = os.environ,
) -> ReleaseGateDecision:
    major, _minor, patch = parse_release_tag(release_tag)
    if channel not in {"alpha", "beta", "rc", "latest"}:
        raise ValueError(f"unsupported release channel: {channel}")

    if audit_disabled(env):
        return ReleaseGateDecision(track="fast", audit_required=False, reasons=["audit_disabled"])

    reasons: list[str] = []
    if major >= 1 and patch == 0:
        reasons.append("major_boundary")

    normalized_labels = sorted({label.strip().lower() for label in labels if label.strip()})
    for label in normalized_labels:
        if label in AUDIT_LABELS:
            reasons.append(f"label:{label}")

    if release_audit:
        reasons.append("manual_release_audit")

    if milestone:
        normalized_milestone = milestone.strip().lower()
        if normalized_milestone in AUDIT_MILESTONES:
            reasons.append(f"milestone:{normalized_milestone}")

    if dependency_major_bump:
        reasons.append("dependency_major_bump")

    if reasons:
        return ReleaseGateDecision(track="audit", audit_required=True, reasons=reasons)
    return ReleaseGateDecision(track="fast", audit_required=False, reasons=["default_fast_track"])


def write_github_outputs(decision: ReleaseGateDecision) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        handle.write(f"track={decision.track}\n")
        handle.write(f"audit_required={str(decision.audit_required).lower()}\n")
        handle.write(f"reasons={','.join(decision.reasons)}\n")


def parse_labels(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--labels", default="")
    parser.add_argument("--release-audit", action="store_true")
    parser.add_argument("--milestone")
    parser.add_argument("--dependency-major-bump", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    decision = decide_release_gate(
        release_tag=args.release_tag,
        channel=args.channel,
        labels=parse_labels(args.labels),
        release_audit=args.release_audit,
        milestone=args.milestone,
        dependency_major_bump=args.dependency_major_bump,
    )
    write_github_outputs(decision)
    if args.json:
        print(json.dumps(decision.as_dict(), sort_keys=True))
    else:
        print(
            "release gate decision: "
            f"track={decision.track} audit_required={str(decision.audit_required).lower()} "
            f"reasons={','.join(decision.reasons)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
