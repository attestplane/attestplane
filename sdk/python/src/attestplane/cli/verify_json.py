# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Structured JSON output for ``attestplane verify --json``."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from attestplane.canonical import CanonicalizationError
from attestplane.hashchain import hash_event
from attestplane.storage.jsonl import _deserialize_event as _deserialize_chained_event
from attestplane.verifier import BundleSchemaError, classify_bundle_schema_error, verify_proof_bundle
from attestplane.verify_errors import (
    VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
    VERIFY_REQUIRED_FIELDS_MISSING,
    VERIFY_SCHEMA_ERROR,
)
from attestplane.verify_reason_codes import (
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_CODE_DESCRIPTIONS,
    VERIFY_REASON_REQUIRED_FIELD_MISSING,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    VERIFY_REASON_SIGNATURE_INVALID,
    VERIFY_REASON_SIGNATURE_MISSING,
    VERIFY_REASON_STRUCTURE_INVALID,
    VerifyReasonCodeV1,
)

VERIFY_RESULT_SCHEMA_VERSION: int = 1
VERIFY_BUNDLE_SCHEMA_VERSION: int = 1


class _DuplicateKeyError(ValueError):
    """Raised when a raw JSON object repeats a key."""


@dataclass(frozen=True, slots=True)
class VerifyJsonOutcome:
    payload: dict[str, Any]
    exit_code: int
    stderr_code: str | None


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise _DuplicateKeyError(f"duplicate JSON key: {key}")
        seen.add(key)
        out[key] = value
    return out


def _canonical_path_to_pointer(path_text: str) -> str:
    if not path_text.startswith("$"):
        return "/"
    text = path_text[1:]
    parts: list[str] = []
    token = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == ".":
            if token:
                parts.append(token)
                token = ""
            i += 1
            continue
        if ch == "[":
            if token:
                parts.append(token)
                token = ""
            end = text.find("]", i)
            if end < 0:
                break
            parts.append(text[i + 1 : end])
            i = end + 1
            continue
        token += ch
        i += 1
    if token:
        parts.append(token)
    return "/" + "/".join(part for part in parts if part)


def _canonicalization_path(exc: CanonicalizationError, *, event_index: int | None) -> str:
    message = str(exc)
    inner = _canonical_path_to_pointer(message.split(":", 1)[0])
    prefix = "/events"
    if event_index is not None:
        prefix = f"/events/{event_index}/event"
    if inner == "/":
        return prefix
    return f"{prefix}{inner}"


def _reason_entry(
    code: VerifyReasonCodeV1,
    path: str,
    *,
    summary: str,
    detail: str | None,
    explain: bool,
) -> dict[str, Any]:
    message = detail if explain and detail else summary
    reason: dict[str, Any] = {
        "code": code,
        "path": path,
        "message": message,
    }
    if explain:
        reason["explanation"] = VERIFY_REASON_CODE_DESCRIPTIONS[code]
    return reason


def _schema_path_from_bundle_error(text: str) -> str:
    if "chain_metadata.schema_version" in text:
        return "/chain_metadata/schema_version"
    if "chain_metadata" in text:
        return "/chain_metadata"
    if "verification_report" in text:
        return "/verification_report"
    if "forbidden_fields" in text:
        return "/forbidden_fields"
    if "events[" in text or text.startswith("events must"):
        return "/events"
    if "bundle_version" in text:
        return "/bundle_version"
    if "signatures" in text:
        return "/signatures"
    if "policy_trace_refs" in text:
        return "/policy_trace_refs"
    if "retention_proofs" in text:
        return "/retention_proofs"
    return "/"


def _schema_reason_for_bundle_error(exc: BaseException) -> tuple[VerifyReasonCodeV1, str]:
    code = classify_bundle_schema_error(exc)
    text = str(exc)
    path = _schema_path_from_bundle_error(text)
    if code == VERIFY_REASON_SCHEMA_VERSION_MISSING and path == "/":
        path = "/chain_metadata/schema_version"
    return code, path


def _json_failure(
    *,
    bundle_digest: str,
    reason: dict[str, Any],
    exit_code: int,
    stderr_code: str | None = None,
) -> VerifyJsonOutcome:
    return VerifyJsonOutcome(
        payload={
            "schema_version": VERIFY_RESULT_SCHEMA_VERSION,
            "result": "fail",
            "exit_code": exit_code,
            "reasons": [reason],
            "bundle": {
                "schema_version": VERIFY_BUNDLE_SCHEMA_VERSION,
                "digest": bundle_digest,
            },
        },
        exit_code=exit_code,
        stderr_code=stderr_code,
    )


def _json_pass(*, bundle_digest: str) -> VerifyJsonOutcome:
    return VerifyJsonOutcome(
        payload={
            "schema_version": VERIFY_RESULT_SCHEMA_VERSION,
            "result": "pass",
            "exit_code": 0,
            "reasons": [],
            "bundle": {
                "schema_version": VERIFY_BUNDLE_SCHEMA_VERSION,
                "digest": bundle_digest,
            },
        },
        exit_code=0,
        stderr_code=None,
    )


def _bundle_digest(raw_bytes: bytes) -> str:
    return _sha256_hex(raw_bytes)


def _canonicalization_probe(bundle: dict[str, Any]) -> tuple[int | None, CanonicalizationError | None]:
    events = bundle.get("events")
    if not isinstance(events, list):
        return None, None
    for index, raw in enumerate(events):
        try:
            chained = _deserialize_chained_event(raw)
        except Exception:
            return None, None
        try:
            hash_event(chained.event)
        except CanonicalizationError as exc:
            return index, exc
    return None, None


def _bundle_failure_reason(
    result: Any | None,
    *,
    explain: bool,
) -> list[dict[str, Any]]:
    if result is None:
        return []

    reasons: list[dict[str, str]] = []

    if not result.chain_result.ok or not result.agreement:
        reasons.append(
            _reason_entry(
                VERIFY_REASON_CANONICAL_MISMATCH,
                "/events",
                summary="chain verification failed",
                detail=result.chain_result.reason,
                explain=explain,
            )
        )

    if not result.signed_attestation_schema_ok:
        code = result.primary_reason or VERIFY_REASON_SIGNATURE_INVALID
        if code not in {
            VERIFY_REASON_REQUIRED_FIELD_MISSING,
            VERIFY_REASON_SIGNATURE_INVALID,
            VERIFY_REASON_SIGNATURE_MISSING,
        }:
            code = VERIFY_REASON_SIGNATURE_INVALID
        path = "/signatures"
        detail = result.signed_attestation_schema_reason
        if detail and detail.startswith("events must contain"):
            path = "/events"
        reasons.append(
            _reason_entry(
                code,
                path,
                summary="signed-attestation schema failed",
                detail=detail,
                explain=explain,
            )
        )

    if not result.metadata_ok:
        code = VERIFY_REASON_STRUCTURE_INVALID
        path = "/verification_report"
        detail = result.metadata_reason
        if detail is not None:
            if "schema_version is missing" in detail:
                code = VERIFY_REASON_SCHEMA_VERSION_MISSING
                path = "/chain_metadata/schema_version"
            elif "schema_version must be an integer" in detail:
                code = VERIFY_REASON_SCHEMA_INVALID
                path = "/chain_metadata/schema_version"
            elif detail.startswith("chain_metadata.schema_version="):
                code = VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED
                path = "/chain_metadata/schema_version"
            elif "unknown required field" in detail:
                code = VERIFY_REASON_SCHEMA_UNKNOWN
                match = re.match(
                    r"^(chain_metadata|verification_report)\.([^. ]+) is an unknown required field$",
                    detail,
                )
                if match is not None:
                    path = f"/{match.group(1)}/{match.group(2)}"
                elif detail.startswith("chain_metadata."):
                    path = "/chain_metadata"
                elif detail.startswith("verification_report."):
                    path = "/verification_report"
            elif detail.startswith("chain_metadata."):
                path = "/chain_metadata"
            else:
                path = "/verification_report"
        reasons.append(
            _reason_entry(
                code,
                path,
                summary="bundle metadata closure failed",
                detail=detail,
                explain=explain,
            )
        )

    if not result.policy_trace_refs_ok:
        reasons.append(
            _reason_entry(
                VERIFY_REASON_STRUCTURE_INVALID,
                "/policy_trace_refs",
                summary="policy trace refs failed",
                detail=result.policy_trace_refs_reason,
                explain=explain,
            )
        )

    if not result.retention_proofs_ok:
        reasons.append(
            _reason_entry(
                VERIFY_REASON_STRUCTURE_INVALID,
                "/retention_proofs",
                summary="retention proof validation failed",
                detail=result.retention_proofs_reason,
                explain=explain,
            )
        )

    if not reasons:
        reasons.append(
            _reason_entry(
                VERIFY_REASON_STRUCTURE_INVALID,
                "/",
                summary="verification failed",
                detail="verification failed",
                explain=explain,
            )
        )
    return reasons


def build_verify_json_outcome(
    bundle_path: Path,
    *,
    require_non_empty: bool,
    require_signed_attestation: bool,
    explain: bool,
) -> VerifyJsonOutcome:
    try:
        raw_bytes = bundle_path.read_bytes()
    except FileNotFoundError as exc:
        digest = _bundle_digest(str(bundle_path).encode("utf-8"))
        return _json_failure(
            bundle_digest=digest,
            reason=_reason_entry(
                VERIFY_REASON_SCHEMA_INVALID,
                "/",
                summary=f"cannot read {bundle_path}: {exc}",
                detail=str(exc),
                explain=explain,
            ),
            exit_code=1,
        )

    bundle_digest = _bundle_digest(raw_bytes)

    try:
        bundle = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except UnicodeDecodeError as exc:
        return _json_failure(
            bundle_digest=bundle_digest,
            reason=_reason_entry(
                VERIFY_REASON_SCHEMA_INVALID,
                "/",
                summary="bundle is not valid UTF-8",
                detail=str(exc),
                explain=explain,
            ),
            exit_code=2,
            stderr_code=VERIFY_SCHEMA_ERROR,
        )
    except _DuplicateKeyError as exc:
        message = str(exc)
        path = "/"
        match = re.search(r"duplicate JSON key: (.+)$", message)
        if match is not None:
            path = f"/{match.group(1)}"
        return _json_failure(
            bundle_digest=bundle_digest,
            reason=_reason_entry(
                VERIFY_REASON_STRUCTURE_INVALID,
                path,
                summary="duplicate JSON key rejected",
                detail=message,
                explain=explain,
            ),
            exit_code=2,
            stderr_code=VERIFY_SCHEMA_ERROR,
        )
    except json.JSONDecodeError as exc:
        return _json_failure(
            bundle_digest=bundle_digest,
            reason=_reason_entry(
                VERIFY_REASON_SCHEMA_INVALID,
                "/",
                summary=f"not valid JSON: {exc.msg}",
                detail=f"{bundle_path}: not valid JSON: {exc.msg}",
                explain=explain,
            ),
            exit_code=2,
            stderr_code=VERIFY_SCHEMA_ERROR,
        )

    if not isinstance(bundle, dict):
        return _json_failure(
            bundle_digest=bundle_digest,
            reason=_reason_entry(
                VERIFY_REASON_SCHEMA_INVALID,
                "/",
                summary=f"bundle must be a JSON object, got {type(bundle).__name__}",
                detail=f"bundle must be a JSON object, got {type(bundle).__name__}",
                explain=explain,
            ),
            exit_code=2,
            stderr_code=VERIFY_SCHEMA_ERROR,
        )

    canonical_index, canonical_exc = _canonicalization_probe(bundle)
    if canonical_exc is not None:
        path = _canonicalization_path(canonical_exc, event_index=canonical_index)
        return _json_failure(
            bundle_digest=bundle_digest,
            reason=_reason_entry(
                VERIFY_REASON_CANONICAL_MISMATCH,
                path,
                summary="canonicalization failed",
                detail=str(canonical_exc),
                explain=explain,
            ),
            exit_code=1,
        )

    try:
        result = verify_proof_bundle(
            bundle,
            require_non_empty=require_non_empty,
            require_signed_attestation=require_signed_attestation,
        )
    except BundleSchemaError as exc:
        code, path = _schema_reason_for_bundle_error(exc)
        return _json_failure(
            bundle_digest=bundle_digest,
            reason=_reason_entry(
                code,
                path,
                summary="bundle schema validation failed",
                detail=str(exc),
                explain=explain,
            ),
            exit_code=2,
            stderr_code=VERIFY_SCHEMA_ERROR,
        )
    except CanonicalizationError as exc:
        path = "/events"
        return _json_failure(
            bundle_digest=bundle_digest,
            reason=_reason_entry(
                VERIFY_REASON_CANONICAL_MISMATCH,
                path,
                summary="canonicalization failed",
                detail=str(exc),
                explain=explain,
            ),
            exit_code=1,
        )

    if result.ok:
        return _json_pass(bundle_digest=bundle_digest)

    reasons = _bundle_failure_reason(result, explain=explain)
    if result.error_code in {
        VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
        VERIFY_REQUIRED_FIELDS_MISSING,
    }:
        exit_code = 2
        stderr_code = result.error_code
    else:
        exit_code = 1
        stderr_code = None

    return VerifyJsonOutcome(
        payload={
            "schema_version": VERIFY_RESULT_SCHEMA_VERSION,
            "result": "fail",
            "exit_code": exit_code,
            "reasons": reasons,
            "bundle": {
                "schema_version": VERIFY_BUNDLE_SCHEMA_VERSION,
                "digest": bundle_digest,
            },
        },
        exit_code=exit_code,
        stderr_code=stderr_code,
    )


__all__ = [
    "VERIFY_BUNDLE_SCHEMA_VERSION",
    "VERIFY_RESULT_SCHEMA_VERSION",
    "VerifyJsonOutcome",
    "build_verify_json_outcome",
]
