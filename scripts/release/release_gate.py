#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Decide whether a release should use fast track or audit track.

Fast track remains the default unless a high-risk release signal is present.
When enforcement is enabled, audit-track releases must carry an explicit
verified audit plan URL before publication can continue.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
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


@dataclass(frozen=True)
class AuditVerification:
    allowed: bool
    reason: str
    audit_plan_url: str

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "audit_plan_url": self.audit_plan_url,
        }


def parse_release_tag(release_tag: str) -> tuple[int, int, int]:
    match = TAG_RE.fullmatch(release_tag)
    if match is None:
        raise ValueError("release tag must match vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH-(alpha|beta|rc).N")
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def audit_disabled(env: Mapping[str, str]) -> bool:
    return env.get("ATTESTPLANE_RELEASE_AUDIT", "").strip().lower() in {"0", "false", "no", "off"}


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


def validate_audit_verification(
    decision: ReleaseGateDecision,
    *,
    audit_verified: bool,
    audit_plan_url: str,
) -> AuditVerification:
    normalized_plan_url = audit_plan_url.strip()
    if not decision.audit_required:
        return AuditVerification(allowed=True, reason="audit_not_required", audit_plan_url=normalized_plan_url)
    if audit_verified and normalized_plan_url:
        return AuditVerification(allowed=True, reason="audit_verified", audit_plan_url=normalized_plan_url)
    return AuditVerification(
        allowed=False,
        reason="audit_required_without_verified_plan",
        audit_plan_url=normalized_plan_url,
    )


def write_github_outputs(decision: ReleaseGateDecision, verification: AuditVerification) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        handle.write(f"track={decision.track}\n")
        handle.write(f"audit_required={str(decision.audit_required).lower()}\n")
        handle.write(f"reasons={','.join(decision.reasons)}\n")
        handle.write(f"audit_gate_allowed={str(verification.allowed).lower()}\n")
        handle.write(f"audit_gate_reason={verification.reason}\n")
        handle.write(f"audit_plan_url={verification.audit_plan_url}\n")


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
    parser.add_argument("--audit-verified", default="false")
    parser.add_argument("--audit-plan-url", default="")
    parser.add_argument("--enforce", action="store_true")
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
    verification = validate_audit_verification(
        decision,
        audit_verified=truthy(args.audit_verified),
        audit_plan_url=args.audit_plan_url,
    )
    write_github_outputs(decision, verification)
    if args.json:
        print(
            json.dumps(
                {
                    "decision": decision.as_dict(),
                    "verification": verification.as_dict(),
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "release gate decision: "
            f"track={decision.track} audit_required={str(decision.audit_required).lower()} "
            f"reasons={','.join(decision.reasons)} "
            f"audit_gate_allowed={str(verification.allowed).lower()} "
            f"audit_gate_reason={verification.reason}"
        )
    if args.enforce and not verification.allowed:
        print(
            "::error::release audit gate blocked publication: "
            f"{verification.reason}; reasons={','.join(decision.reasons)}",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
