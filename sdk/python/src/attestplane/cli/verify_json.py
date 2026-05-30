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
    VERIFY_IO_ERROR,
    VERIFY_REQUIRED_FIELDS_MISSING,
    VERIFY_SCHEMA_ERROR,
)
from attestplane.verify_reason_codes import (
    VERIFY_REASON_ANCHOR_INVALID,
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_REQUIRED_FIELD_MISSING,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_UNKNOWN,
    VERIFY_REASON_SCHEMA_VERSION_MISSING,
    VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
    VERIFY_REASON_SIGNATURE_INVALID,
    VERIFY_REASON_SIGNATURE_MISSING,
    VERIFY_REASON_STRUCTURE_INVALID,
    VerifyReasonCodeV1,
    format_verify_taxonomy_version,
    resolve_verify_taxonomy_version,
    verify_reason_code_explanation,
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
        reason["explanation"] = verify_reason_code_explanation(code)
    return reason


def _explanation_entry(
    primary_reason: VerifyReasonCodeV1 | None,
    pointer: str,
    message: str,
) -> dict[str, Any]:
    return {
        "primary_reason": primary_reason,
        "pointer": pointer,
        "message": message,
    }


def _bundle_signer_subject(bundle: dict[str, Any]) -> str:
    signatures = bundle.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        return "none"
    first = signatures[0]
    if not isinstance(first, dict):
        return "unknown"
    key_id = first.get("key_id")
    if isinstance(key_id, str) and key_id:
        return f"key_id:{key_id}"
    signed_event_hash_hex = first.get("signed_event_hash_hex")
    if isinstance(signed_event_hash_hex, str) and signed_event_hash_hex:
        return f"subject_hash:{signed_event_hash_hex}"
    return "unknown"


def _bundle_schema_version(bundle: dict[str, Any]) -> str:
    chain_metadata = bundle.get("chain_metadata")
    if not isinstance(chain_metadata, dict):
        return "unknown"
    schema_version = chain_metadata.get("schema_version")
    if isinstance(schema_version, int):
        return str(schema_version)
    return "unknown"


def _bundle_anchor_state(bundle: dict[str, Any]) -> str:
    explicit = _bundle_explicit_anchoring_state(bundle)
    if explicit is not None:
        return explicit
    chain_metadata = bundle.get("chain_metadata")
    if not isinstance(chain_metadata, dict):
        return "unknown"
    anchor_ref = chain_metadata.get("anchor_ref")
    return "present" if isinstance(anchor_ref, str) and anchor_ref else "absent"


def _bundle_explicit_anchoring_state(bundle: dict[str, Any] | None) -> str | None:
    if not isinstance(bundle, dict):
        return None
    anchoring = bundle.get("anchoring")
    if not isinstance(anchoring, dict):
        return None
    status = anchoring.get("status")
    quarantined = anchoring.get("quarantined")
    if status not in {"anchored", "quarantined", "unanchored"}:
        return None
    if not isinstance(quarantined, bool):
        return None
    return str(status)


def _bundle_anchor_ref_present(bundle: dict[str, Any] | None) -> bool:
    if not isinstance(bundle, dict):
        return False
    chain_metadata = bundle.get("chain_metadata")
    if not isinstance(chain_metadata, dict):
        return False
    anchor_ref = chain_metadata.get("anchor_ref")
    return isinstance(anchor_ref, str) and bool(anchor_ref)


def _anchoring_payload(bundle: dict[str, Any] | None, *, exit_code: int) -> dict[str, Any]:
    if exit_code == 2:
        status = "quarantined"
        quarantined = True
    else:
        explicit = _bundle_explicit_anchoring_state(bundle)
        if explicit is not None:
            status = explicit
        else:
            status = "anchored" if _bundle_anchor_ref_present(bundle) else "unanchored"
        quarantined = False
    return {
        "anchoring": {
            "status": status,
            "quarantined": quarantined,
        }
    }


def _verify_success_summary(bundle: dict[str, Any]) -> str:
    return (
        f"signer_subject={_bundle_signer_subject(bundle)} "
        f"schema_version={_bundle_schema_version(bundle)} "
        f"taxonomy_version={format_verify_taxonomy_version(resolve_verify_taxonomy_version())} "
        f"anchor={_bundle_anchor_state(bundle)}"
    )


def _verify_explanations(
    result: Any | None,
    *,
    bundle: dict[str, Any] | None = None,
    explain: bool = False,
) -> list[dict[str, Any]]:
    if not explain or result is None:
        return []
    if result.ok:
        if bundle is None:
            return [
                _explanation_entry(
                    None,
                    "/",
                    f"signer_subject=unknown schema_version=unknown "
                    f"taxonomy_version={format_verify_taxonomy_version()} anchor=unknown",
                )
            ]
        return [_explanation_entry(None, "/", _verify_success_summary(bundle))]

    explanations: list[dict[str, Any]] = []
    for reason in _bundle_failure_reason(result, explain=explain):
        explanations.append(
            _explanation_entry(
                reason["code"],
                reason["path"],
                str(reason["message"]),
            )
        )
    return explanations


def _schema_path_from_bundle_error(text: str) -> str:
    if "anchoring" in text:
        return "/anchoring"
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
    bundle: dict[str, Any] | None = None,
    stderr_code: str | None = None,
    explanation: list[dict[str, Any]] | None = None,
) -> VerifyJsonOutcome:
    payload = {
        "schema_version": VERIFY_RESULT_SCHEMA_VERSION,
        "result": "fail",
        "exit_code": exit_code,
        "reason_code": reason["code"],
        "taxonomy_version": resolve_verify_taxonomy_version(),
        "reasons": [reason],
        "bundle": {
            "schema_version": VERIFY_BUNDLE_SCHEMA_VERSION,
            "digest": bundle_digest,
        },
        **_anchoring_payload(bundle, exit_code=exit_code),
    }
    if explanation is not None:
        payload["explanation"] = explanation
    return VerifyJsonOutcome(
        payload=payload,
        exit_code=exit_code,
        stderr_code=stderr_code,
    )


def _json_pass(
    *,
    bundle_digest: str,
    bundle: dict[str, Any] | None = None,
    explanation: list[dict[str, Any]] | None = None,
) -> VerifyJsonOutcome:
    payload = {
        "schema_version": VERIFY_RESULT_SCHEMA_VERSION,
        "result": "pass",
        "exit_code": 0,
        "reason_code": None,
        "taxonomy_version": resolve_verify_taxonomy_version(),
        "reasons": [],
        "bundle": {
            "schema_version": VERIFY_BUNDLE_SCHEMA_VERSION,
            "digest": bundle_digest,
        },
        **_anchoring_payload(bundle, exit_code=0),
    }
    if explanation is not None:
        payload["explanation"] = explanation
    return VerifyJsonOutcome(
        payload=payload,
        exit_code=0,
        stderr_code=None,
    )


def verify_result_exit_code(result: Any | None) -> int:
    """Map a verifier result to the stable CLI exit-code contract.

    - 0: success
    - 1: verification failure
    - 2: quarantine / fail-closed bundle contract rejection
    - 3: usage, I/O, or malformed-input failure
    """
    if result is None:
        return 1
    if getattr(result, "ok", False):
        return 0
    if getattr(result, "anchoring_quarantined", False):
        return 2
    return 1


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
    bundle: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if result is None:
        return []

    reasons: list[dict[str, str]] = []

    if not getattr(result, "taxonomy_version_ok", True):
        reasons.append(
            _reason_entry(
                VERIFY_REASON_SCHEMA_VERSION_UNSUPPORTED,
                "/taxonomy_version",
                summary="taxonomy version pin failed",
                detail=getattr(result, "taxonomy_version_reason", None),
                explain=explain,
            )
        )

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

    if _bundle_explicit_anchoring_state(bundle) == "quarantined":
        reasons.append(
            _reason_entry(
                VERIFY_REASON_ANCHOR_INVALID,
                "/anchoring",
                summary="anchor verification quarantined",
                detail="bundle.anchoring.status=quarantined",
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
    require_taxonomy_version: int | None,
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
            exit_code=3,
            bundle=None,
            stderr_code=VERIFY_IO_ERROR,
            explanation=(
                [_explanation_entry(VERIFY_REASON_SCHEMA_INVALID, "/", f"cannot read {bundle_path}: {exc}")]
                if explain
                else None
            ),
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
            exit_code=3,
            bundle=None,
            stderr_code=VERIFY_SCHEMA_ERROR,
            explanation=(
                [_explanation_entry(VERIFY_REASON_SCHEMA_INVALID, "/", f"bundle is not valid UTF-8: {exc}")]
                if explain
                else None
            ),
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
            exit_code=3,
            bundle=None,
            stderr_code=VERIFY_SCHEMA_ERROR,
            explanation=([_explanation_entry(VERIFY_REASON_STRUCTURE_INVALID, path, message)] if explain else None),
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
            exit_code=3,
            bundle=None,
            stderr_code=VERIFY_SCHEMA_ERROR,
            explanation=(
                [_explanation_entry(VERIFY_REASON_SCHEMA_INVALID, "/", f"{bundle_path}: not valid JSON: {exc.msg}")]
                if explain
                else None
            ),
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
            bundle=bundle if isinstance(bundle, dict) else None,
            stderr_code=VERIFY_SCHEMA_ERROR,
            explanation=(
                [
                    _explanation_entry(
                        VERIFY_REASON_SCHEMA_INVALID,
                        "/",
                        f"bundle must be a JSON object, got {type(bundle).__name__}",
                    )
                ]
                if explain
                else None
            ),
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
            bundle=bundle,
            explanation=(
                [_explanation_entry(VERIFY_REASON_CANONICAL_MISMATCH, path, str(canonical_exc))] if explain else None
            ),
        )

    try:
        result = verify_proof_bundle(
            bundle,
            require_non_empty=require_non_empty,
            require_signed_attestation=require_signed_attestation,
            require_taxonomy_version=require_taxonomy_version,
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
            bundle=bundle,
            stderr_code=VERIFY_SCHEMA_ERROR,
            explanation=([_explanation_entry(code, path, str(exc))] if explain else None),
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
            bundle=bundle,
            explanation=([_explanation_entry(VERIFY_REASON_CANONICAL_MISMATCH, path, str(exc))] if explain else None),
        )

    if result.ok:
        return _json_pass(
            bundle_digest=bundle_digest,
            bundle=bundle,
            explanation=_verify_explanations(result, bundle=bundle, explain=explain) or None,
        )

    reasons = _bundle_failure_reason(result, explain=explain, bundle=bundle)
    exit_code = verify_result_exit_code(result)
    if result.error_code in {
        VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
        VERIFY_REQUIRED_FIELDS_MISSING,
    }:
        stderr_code = result.error_code
    else:
        stderr_code = None

    return VerifyJsonOutcome(
        payload={
            "schema_version": VERIFY_RESULT_SCHEMA_VERSION,
            "result": "fail",
            "exit_code": exit_code,
            "reason_code": result.primary_reason,
            "taxonomy_version": resolve_verify_taxonomy_version(),
            "reasons": reasons,
            "bundle": {
                "schema_version": VERIFY_BUNDLE_SCHEMA_VERSION,
                "digest": bundle_digest,
            },
            **_anchoring_payload(bundle, exit_code=exit_code),
            **({"explanation": _verify_explanations(result, bundle=bundle, explain=explain)} if explain else {}),
        },
        exit_code=exit_code,
        stderr_code=stderr_code,
    )


__all__ = [
    "VERIFY_BUNDLE_SCHEMA_VERSION",
    "VERIFY_RESULT_SCHEMA_VERSION",
    "VerifyJsonOutcome",
    "build_verify_json_outcome",
    "verify_result_exit_code",
]
