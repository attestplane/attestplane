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
import subprocess
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
PRODUCT_DELTA_BYPASS_LABELS = frozenset({"release-hotfix", "security-patch", "test-only"})
PRODUCT_IMPLEMENTATION_PREFIXES = (
    "sdk/python/src/attestplane/",
    "sdk/typescript/src/",
    "scripts/observability/",
)
PRODUCT_IMPLEMENTATION_FILES = frozenset(
    {
        "scripts/release/plan_to_issues.py",
    }
)
PRODUCT_SUPPORT_PREFIXES = (
    "sdk/python/tests/",
    "sdk/typescript/tests/",
    "sdk/python/conformance/",
    "sdk/typescript/conformance/",
    "schemas/",
    "conformance/",
)
VERSION_ONLY_FILES = frozenset(
    {
        "sdk/python/src/attestplane/__init__.py",
        "sdk/typescript/src/index_version.ts",
        "sdk/python/pyproject.toml",
        "sdk/python/uv.lock",
        "sdk/typescript/package.json",
        "sdk/typescript/package-lock.json",
    }
)
SUPPORT_ONLY_PREFIXES = (
    ".github/",
    "docs/",
    "release/",
    "scripts/release/",
)


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


@dataclass(frozen=True)
class ProductDeltaVerification:
    allowed: bool
    reason: str
    product_files: list[str]
    product_support_files: list[str]
    support_only_files: list[str]
    ignored_files: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "product_files": self.product_files,
            "product_support_files": self.product_support_files,
            "support_only_files": self.support_only_files,
            "ignored_files": self.ignored_files,
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


def normalize_path(path: str) -> str:
    normalized = path.strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def product_delta_bypassed(labels: list[str], env: Mapping[str, str]) -> bool:
    if truthy(env.get("ATTESTPLANE_PRODUCT_DELTA_BYPASS", "")):
        return True
    normalized_labels = {label.strip().lower() for label in labels if label.strip()}
    return bool(PRODUCT_DELTA_BYPASS_LABELS & normalized_labels)


def _has_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def classify_product_delta(
    changed_files: list[str],
    *,
    labels: list[str],
    env: Mapping[str, str] = os.environ,
) -> ProductDeltaVerification:
    product_files: list[str] = []
    product_support_files: list[str] = []
    support_only_files: list[str] = []
    ignored_files: list[str] = []

    for raw_path in changed_files:
        path = normalize_path(raw_path)
        if not path:
            continue
        if path in VERSION_ONLY_FILES:
            ignored_files.append(path)
        elif path in PRODUCT_IMPLEMENTATION_FILES or _has_prefix(path, PRODUCT_IMPLEMENTATION_PREFIXES):
            product_files.append(path)
        elif _has_prefix(path, PRODUCT_SUPPORT_PREFIXES):
            product_support_files.append(path)
        elif _has_prefix(path, SUPPORT_ONLY_PREFIXES):
            support_only_files.append(path)
        else:
            support_only_files.append(path)

    product_files.sort()
    product_support_files.sort()
    support_only_files.sort()
    ignored_files.sort()

    if product_files:
        return ProductDeltaVerification(
            allowed=True,
            reason="product_implementation_delta",
            product_files=product_files,
            product_support_files=product_support_files,
            support_only_files=support_only_files,
            ignored_files=ignored_files,
        )
    if product_support_files:
        if product_delta_bypassed(labels, env):
            return ProductDeltaVerification(
                allowed=True,
                reason="product_support_delta_bypassed",
                product_files=product_files,
                product_support_files=product_support_files,
                support_only_files=support_only_files,
                ignored_files=ignored_files,
            )
        return ProductDeltaVerification(
            allowed=True,
            reason="product_support_delta",
            product_files=product_files,
            product_support_files=product_support_files,
            support_only_files=support_only_files,
            ignored_files=ignored_files,
        )
    if product_delta_bypassed(labels, env):
        return ProductDeltaVerification(
            allowed=True,
            reason="product_delta_bypassed",
            product_files=product_files,
            product_support_files=product_support_files,
            support_only_files=support_only_files,
            ignored_files=ignored_files,
        )
    return ProductDeltaVerification(
        allowed=False,
        reason="product_delta_required_without_product_change",
        product_files=product_files,
        product_support_files=product_support_files,
        support_only_files=support_only_files,
        ignored_files=ignored_files,
    )


def changed_files_between(base_ref: str, head_ref: str) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}..{head_ref}"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


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
    major, minor, patch = parse_release_tag(release_tag)
    if channel not in {"alpha", "beta", "rc", "latest"}:
        raise ValueError(f"unsupported release channel: {channel}")

    if audit_disabled(env):
        return ReleaseGateDecision(track="fast", audit_required=False, reasons=["audit_disabled"])

    reasons: list[str] = []
    if major >= 1 and minor == 0 and patch == 0:
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


def write_product_delta_github_outputs(product_delta: ProductDeltaVerification) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        handle.write(f"product_delta_allowed={str(product_delta.allowed).lower()}\n")
        handle.write(f"product_delta_reason={product_delta.reason}\n")
        handle.write(f"product_delta_files={','.join(product_delta.product_files)}\n")
        handle.write(f"product_support_files={','.join(product_delta.product_support_files)}\n")


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
    parser.add_argument("--require-product-delta", action="store_true")
    parser.add_argument("--product-delta-base")
    parser.add_argument("--product-delta-head", default="HEAD")
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    labels = parse_labels(args.labels)

    decision = decide_release_gate(
        release_tag=args.release_tag,
        channel=args.channel,
        labels=labels,
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
    product_delta = ProductDeltaVerification(
        allowed=True,
        reason="product_delta_not_required",
        product_files=[],
        product_support_files=[],
        support_only_files=[],
        ignored_files=[],
    )
    if args.require_product_delta:
        if not args.product_delta_base:
            raise SystemExit("--product-delta-base is required when --require-product-delta is set")
        changed_files = changed_files_between(args.product_delta_base, args.product_delta_head)
        product_delta = classify_product_delta(changed_files, labels=labels)
        write_product_delta_github_outputs(product_delta)
    if args.json:
        print(
            json.dumps(
                {
                    "decision": decision.as_dict(),
                    "verification": verification.as_dict(),
                    "product_delta": product_delta.as_dict(),
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
            f"audit_gate_reason={verification.reason} "
            f"product_delta_allowed={str(product_delta.allowed).lower()} "
            f"product_delta_reason={product_delta.reason}"
        )
    if args.enforce and not verification.allowed:
        print(
            "::error::release audit gate blocked publication: "
            f"{verification.reason}; reasons={','.join(decision.reasons)}",
            file=sys.stderr,
        )
        return 3
    if args.enforce and not product_delta.allowed:
        print(
            "::error::release product delta gate blocked publication: "
            f"{product_delta.reason}; product_files={','.join(product_delta.product_files)} "
            f"product_support_files={','.join(product_delta.product_support_files)}",
            file=sys.stderr,
        )
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
