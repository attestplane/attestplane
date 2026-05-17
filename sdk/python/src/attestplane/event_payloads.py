# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Event-payload TypedDicts + validators per ADR-0009 Mode A.6.

Each TypedDict here describes the **payload slot** of an `AuditEvent`
for one v1 ``event_type`` (per :mod:`attestplane.event_types` /
ADR-0008). The substrate's `ChainedEvent` shape stays frozen — INV 2.
Payload schemas are versioned independently of `chain.schema_version`
/ `anchor_schema_version` / `signature_schema_version` /
`reason_code_schema_version`.

Each payload schema also defines a small ``validate_*()`` function
that rejects malformed payloads (wrong types, missing required fields,
forbidden field names per ADR-0004 § 2 column 3). Validators are
intentionally cheap (~ regex + dict-key checks) so adapters can call
them on every translation step without measurable overhead.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Final, Literal, NotRequired, TypedDict

# --- Shared validation primitives ------------------------------------------

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

# Per ADR-0004 § 2 column 3 + ADR-0009 § 1 Mode A.6 redaction policy.
# Payload field names that MUST NEVER appear at the root of any event
# payload. Substrate is advisory at the SDK boundary — adapters and
# verifiers call these checks; the hash-chain core stays
# taxonomy-agnostic per ADR-0008.
FORBIDDEN_PAYLOAD_FIELDS: Final[frozenset[str]] = frozenset({
    "signature",
    "private_key",
    "secret",
    "token",
    "auth_header",
    "session_token",
    "capability",
    "capability_required",
    "budget",
    "budget_cap",
    "quota",
    "scope_expression",
    "scope_body",
    "hmac",
    "hmac_canonical_payload",
    "policy_expression_body",
    "expression",
})


class _PayloadValidationError(ValueError):
    """Raised when a payload fails a validator's invariant check."""


def _require_iso_utc(value: Any, field: str) -> None:
    """Reject anything not parseable as an RFC-3339 UTC datetime."""
    if not isinstance(value, str):
        raise _PayloadValidationError(
            f"{field}: must be ISO-8601 string, got {type(value).__name__}"
        )
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise _PayloadValidationError(
            f"{field}: not valid ISO-8601: {value!r} ({exc})"
        ) from exc
    if dt.tzinfo is None:
        raise _PayloadValidationError(
            f"{field}: must be UTC-aware (use 'Z' or '+00:00' suffix)"
        )


def _reject_forbidden_fields(payload: dict[str, Any], event_type: str) -> None:
    """Reject any root-level forbidden field per ADR-0004 § 2 redaction."""
    hits = sorted(set(payload.keys()) & FORBIDDEN_PAYLOAD_FIELDS)
    if hits:
        raise _PayloadValidationError(
            f"{event_type}: payload contains forbidden field(s) "
            f"{hits} per ADR-0004 § 2 redaction policy"
        )


# --- lease_lifecycle_event payload ----------------------------------------

LeaseLifecycle = Literal["granted", "consumed", "expired", "revoked"]
"""The four observed lifecycle transitions per ADR-0009 A.7 schema."""


class LeaseLifecycleEventPayload(TypedDict, total=False):
    """Payload-shape for the ``lease_lifecycle_event`` event_type.

    Schema-shape re-issue (Mode A.6 per ADR-0009 § 1) of fields
    originally observed at
    ``~/aios/crates/aios-sdk-evidence/src/artifact.rs`` and
    ``~/aios/schemas/lease/lease.schema.json``. Authority-bearing
    fields (``signature``, ``capability_required``, ``budget_cap``,
    ``hmac``) are explicitly NOT absorbed.

    Required fields: ``lease_event_schema_version`` (must equal 1),
    ``lease_id_hash`` (64-hex SHA-256 of opaque lease id),
    ``lifecycle`` (one of the four enum values), ``observed_at``
    (RFC-3339 UTC).
    """

    # Required
    lease_event_schema_version: Literal[1]
    lease_id_hash: str
    lifecycle: LeaseLifecycle
    observed_at: str
    # Optional caller-asserted correlation refs
    grantor_runtime_id: NotRequired[str]
    tenant_id_ref: NotRequired[str]
    step_id_ref: NotRequired[str]
    run_id_ref: NotRequired[str]
    artifact_hash_ref: NotRequired[str]
    reason_code: NotRequired[str]
    reason_text: NotRequired[str]


_REQUIRED_LEASE_KEYS: Final[frozenset[str]] = frozenset({
    "lease_event_schema_version",
    "lease_id_hash",
    "lifecycle",
    "observed_at",
})
_LIFECYCLE_VALUES: Final[frozenset[str]] = frozenset({
    "granted", "consumed", "expired", "revoked",
})


def validate_lease_lifecycle_event_payload(payload: dict[str, Any]) -> None:
    """Raise :class:`ValueError` if ``payload`` violates A.7 invariants.

    Checked invariants (mirror schemas/v1/lease_lifecycle_event.schema.json):

    - ``lease_event_schema_version == 1``
    - all required fields present
    - ``lease_id_hash`` matches ``^[0-9a-f]{64}$``
    - ``lifecycle`` ∈ {granted, consumed, expired, revoked}
    - ``observed_at`` parses as RFC-3339 UTC
    - ``artifact_hash_ref`` (if present) matches the 64-hex pattern
    - no forbidden field per ADR-0004 § 2 redaction
    """
    if not isinstance(payload, dict):
        raise _PayloadValidationError(
            f"lease_lifecycle_event payload must be dict, got {type(payload).__name__}"
        )
    _reject_forbidden_fields(payload, "lease_lifecycle_event")
    missing = _REQUIRED_LEASE_KEYS - set(payload.keys())
    if missing:
        raise _PayloadValidationError(
            f"lease_lifecycle_event: missing required fields {sorted(missing)}"
        )
    if payload["lease_event_schema_version"] != 1:
        raise _PayloadValidationError(
            "lease_lifecycle_event: lease_event_schema_version must be 1, "
            f"got {payload['lease_event_schema_version']!r}"
        )
    lease_id_hash = payload["lease_id_hash"]
    if not isinstance(lease_id_hash, str) or not _HEX64.match(lease_id_hash):
        raise _PayloadValidationError(
            f"lease_lifecycle_event: lease_id_hash must be 64-hex string, "
            f"got {lease_id_hash!r}"
        )
    lifecycle = payload["lifecycle"]
    if lifecycle not in _LIFECYCLE_VALUES:
        raise _PayloadValidationError(
            f"lease_lifecycle_event: lifecycle must be one of "
            f"{sorted(_LIFECYCLE_VALUES)}, got {lifecycle!r}"
        )
    _require_iso_utc(payload["observed_at"], "lease_lifecycle_event.observed_at")

    artifact_ref = payload.get("artifact_hash_ref")
    if artifact_ref is not None and (
        not isinstance(artifact_ref, str) or not _HEX64.match(artifact_ref)
    ):
        raise _PayloadValidationError(
            f"lease_lifecycle_event: artifact_hash_ref (if present) must be "
            f"64-hex string, got {artifact_ref!r}"
        )

    for opt_field in (
        "grantor_runtime_id", "tenant_id_ref", "step_id_ref",
        "run_id_ref", "reason_code", "reason_text",
    ):
        v = payload.get(opt_field)
        if v is not None and not isinstance(v, str):
            raise _PayloadValidationError(
                f"lease_lifecycle_event.{opt_field}: must be string or absent, "
                f"got {type(v).__name__}"
            )


# --- policy_check_event payload --------------------------------------------

PolicyDecision = Literal["allow", "deny", "abstain", "require_approval"]
"""Observed decision outcomes per ADR-0009 A.8 schema."""

PolicyEffect = Literal["INFO", "WARN", "BLOCK"]
"""Severity classification matching AIOS `severity` field set."""


class PolicyCheckEventPayload(TypedDict, total=False):
    """Payload-shape for the ``policy_check_event`` event_type.

    Schema-shape re-issue (Mode A.6) of fields originally observed at
    ``~/aios/schemas/policy/policy.schema.json``. Authority lifecycle
    fields (`expression` body / `PolicyUpdateCandidate` / `activated_at`
    / `deprecated_at`) are explicitly NOT absorbed — ADR-0004 § 2
    case #10 keeps expression as hash only.

    Required: ``policy_event_schema_version=1``, ``policy_id``,
    ``rule_id``, ``decision``, ``observed_at``.
    """

    # Required
    policy_event_schema_version: Literal[1]
    policy_id: str
    rule_id: str
    decision: PolicyDecision
    observed_at: str
    # Optional caller-asserted refs
    policy_version: NotRequired[int]
    kind: NotRequired[str]
    effect: NotRequired[PolicyEffect]
    expression_hash: NotRequired[str]
    evidence_refs: NotRequired[list[str]]
    reason_code: NotRequired[str]
    reason_text: NotRequired[str]


_REQUIRED_POLICY_KEYS: Final[frozenset[str]] = frozenset({
    "policy_event_schema_version",
    "policy_id",
    "rule_id",
    "decision",
    "observed_at",
})
_DECISION_VALUES: Final[frozenset[str]] = frozenset({
    "allow", "deny", "abstain", "require_approval",
})
_EFFECT_VALUES: Final[frozenset[str]] = frozenset({"INFO", "WARN", "BLOCK"})


def validate_policy_check_event_payload(payload: dict[str, Any]) -> None:
    """Raise :class:`ValueError` if ``payload`` violates A.8 invariants.

    Checked invariants (mirror schemas/v1/policy_check_event.schema.json):

    - ``policy_event_schema_version == 1``
    - all required fields present + non-empty strings where required
    - ``decision`` ∈ {allow, deny, abstain, require_approval}
    - ``effect`` (if present) ∈ {INFO, WARN, BLOCK}
    - ``expression_hash`` (if present) matches 64-hex
    - ``evidence_refs`` (if present) is a list of 64-hex strings
    - ``observed_at`` parses as RFC-3339 UTC
    - no forbidden field per ADR-0004 § 2 redaction
    - **`expression` field is forbidden** (only `expression_hash`
      permitted per ADR-0004 § 2 case #10)
    """
    if not isinstance(payload, dict):
        raise _PayloadValidationError(
            f"policy_check_event payload must be dict, got {type(payload).__name__}"
        )
    _reject_forbidden_fields(payload, "policy_check_event")
    missing = _REQUIRED_POLICY_KEYS - set(payload.keys())
    if missing:
        raise _PayloadValidationError(
            f"policy_check_event: missing required fields {sorted(missing)}"
        )
    if payload["policy_event_schema_version"] != 1:
        raise _PayloadValidationError(
            "policy_check_event: policy_event_schema_version must be 1, "
            f"got {payload['policy_event_schema_version']!r}"
        )
    for str_field in ("policy_id", "rule_id"):
        v = payload[str_field]
        if not isinstance(v, str) or not v:
            raise _PayloadValidationError(
                f"policy_check_event.{str_field}: must be non-empty string, "
                f"got {v!r}"
            )
    decision = payload["decision"]
    if decision not in _DECISION_VALUES:
        raise _PayloadValidationError(
            f"policy_check_event: decision must be one of "
            f"{sorted(_DECISION_VALUES)}, got {decision!r}"
        )
    _require_iso_utc(payload["observed_at"], "policy_check_event.observed_at")

    if "policy_version" in payload:
        pv = payload["policy_version"]
        if not isinstance(pv, int) or isinstance(pv, bool) or pv < 1:
            raise _PayloadValidationError(
                "policy_check_event.policy_version: must be integer >= 1, "
                f"got {pv!r}"
            )
    effect = payload.get("effect")
    if effect is not None and effect not in _EFFECT_VALUES:
        raise _PayloadValidationError(
            f"policy_check_event.effect: must be one of "
            f"{sorted(_EFFECT_VALUES)} or absent, got {effect!r}"
        )
    expr_hash = payload.get("expression_hash")
    if expr_hash is not None and (
        not isinstance(expr_hash, str) or not _HEX64.match(expr_hash)
    ):
        raise _PayloadValidationError(
            f"policy_check_event.expression_hash: must be 64-hex string, "
            f"got {expr_hash!r}"
        )
    refs = payload.get("evidence_refs")
    if refs is not None:
        if not isinstance(refs, list):
            raise _PayloadValidationError(
                f"policy_check_event.evidence_refs: must be list, "
                f"got {type(refs).__name__}"
            )
        if len(refs) > 256:
            raise _PayloadValidationError(
                f"policy_check_event.evidence_refs: max 256 entries, got {len(refs)}"
            )
        seen: set[str] = set()
        for i, ref in enumerate(refs):
            if not isinstance(ref, str) or not _HEX64.match(ref):
                raise _PayloadValidationError(
                    f"policy_check_event.evidence_refs[{i}]: must be 64-hex string, "
                    f"got {ref!r}"
                )
            if ref in seen:
                raise _PayloadValidationError(
                    f"policy_check_event.evidence_refs: duplicate entry {ref!r}"
                )
            seen.add(ref)

    for opt_field in ("kind", "reason_code", "reason_text"):
        v = payload.get(opt_field)
        if v is not None and not isinstance(v, str):
            raise _PayloadValidationError(
                f"policy_check_event.{opt_field}: must be string or absent, "
                f"got {type(v).__name__}"
            )


# --- replay_event payload --------------------------------------------------


class ReplayEventPayload(TypedDict, total=False):
    """Payload-shape for the ``replay_event`` event_type.

    Schema-shape re-issue (Mode A.6) of ADR-0009 A.9 — fields
    originally observed at ``~/aios/crates/aios-sdk-evidence/src/replay.rs``
    + ``~/aios/schemas/replay/replay_proof.schema.json``.

    Records that an external runner performed a deterministic replay
    and observed the four boolean outcomes. Attestplane substrate
    does NOT re-execute the workload — the booleans are caller-asserted.

    The ``deterministic_result`` field MUST equal the logical AND of
    ``input_hash_match``, ``artifact_hash_match``, ``audit_chain_match``.
    Validators enforce this cross-check.
    """

    # Required
    replay_event_schema_version: Literal[1]
    replay_run_id: str
    original_run_id: str
    input_hash_match: bool
    artifact_hash_match: bool
    audit_chain_match: bool
    deterministic_result: bool
    observed_at: str
    # Optional
    snapshot_id_ref: NotRequired[str]
    diff_summary_hash: NotRequired[str]
    reason_code: NotRequired[str]
    reason_text: NotRequired[str]


_REQUIRED_REPLAY_KEYS: Final[frozenset[str]] = frozenset({
    "replay_event_schema_version",
    "replay_run_id",
    "original_run_id",
    "input_hash_match",
    "artifact_hash_match",
    "audit_chain_match",
    "deterministic_result",
    "observed_at",
})


def validate_replay_event_payload(payload: dict[str, Any]) -> None:
    """Raise :class:`ValueError` if ``payload`` violates A.9 invariants.

    Invariants:

    - ``replay_event_schema_version == 1``
    - all required fields present
    - the four booleans are actually booleans (not 0/1, not strings)
    - ``deterministic_result == (input_hash_match and artifact_hash_match
      and audit_chain_match)`` — the AND cross-check
    - ``replay_run_id`` / ``original_run_id`` non-empty strings
    - ``snapshot_id_ref`` (if present) non-empty string
    - ``diff_summary_hash`` (if present) matches 64-hex
    - ``observed_at`` parses as RFC-3339 UTC
    - no forbidden field per ADR-0004 § 2 redaction
    """
    if not isinstance(payload, dict):
        raise _PayloadValidationError(
            f"replay_event payload must be dict, got {type(payload).__name__}"
        )
    _reject_forbidden_fields(payload, "replay_event")
    missing = _REQUIRED_REPLAY_KEYS - set(payload.keys())
    if missing:
        raise _PayloadValidationError(
            f"replay_event: missing required fields {sorted(missing)}"
        )
    if payload["replay_event_schema_version"] != 1:
        raise _PayloadValidationError(
            "replay_event: replay_event_schema_version must be 1, "
            f"got {payload['replay_event_schema_version']!r}"
        )
    for str_field in ("replay_run_id", "original_run_id"):
        v = payload[str_field]
        if not isinstance(v, str) or not v:
            raise _PayloadValidationError(
                f"replay_event.{str_field}: must be non-empty string, got {v!r}"
            )

    # Booleans must be strict bool (not int/str). bool is subclass of int in
    # Python so we must check `type(v) is bool` not `isinstance(v, bool)`
    # — actually isinstance is fine; we want to reject int/str specifically.
    bool_fields = (
        "input_hash_match",
        "artifact_hash_match",
        "audit_chain_match",
        "deterministic_result",
    )
    for bf in bool_fields:
        v = payload[bf]
        # bool is a subclass of int; we need strict bool only.
        if not isinstance(v, bool):
            raise _PayloadValidationError(
                f"replay_event.{bf}: must be boolean, got {type(v).__name__}"
            )

    # AND cross-check (the load-bearing invariant per AIOS ReplayProof spec).
    expected_det = (
        payload["input_hash_match"]
        and payload["artifact_hash_match"]
        and payload["audit_chain_match"]
    )
    if payload["deterministic_result"] != expected_det:
        raise _PayloadValidationError(
            "replay_event.deterministic_result: must equal logical AND of "
            "input_hash_match, artifact_hash_match, audit_chain_match "
            f"(got {payload['deterministic_result']!r}, expected {expected_det!r})"
        )

    _require_iso_utc(payload["observed_at"], "replay_event.observed_at")

    if "snapshot_id_ref" in payload:
        sid = payload["snapshot_id_ref"]
        if not isinstance(sid, str) or not sid:
            raise _PayloadValidationError(
                f"replay_event.snapshot_id_ref: must be non-empty string, got {sid!r}"
            )

    diff_hash = payload.get("diff_summary_hash")
    if diff_hash is not None and (
        not isinstance(diff_hash, str) or not _HEX64.match(diff_hash)
    ):
        raise _PayloadValidationError(
            f"replay_event.diff_summary_hash: must be 64-hex string, got {diff_hash!r}"
        )

    for opt_field in ("reason_code", "reason_text"):
        v = payload.get(opt_field)
        if v is not None and not isinstance(v, str):
            raise _PayloadValidationError(
                f"replay_event.{opt_field}: must be string or absent, "
                f"got {type(v).__name__}"
            )


__all__ = [
    "FORBIDDEN_PAYLOAD_FIELDS",
    "LeaseLifecycle",
    "LeaseLifecycleEventPayload",
    "PolicyCheckEventPayload",
    "PolicyDecision",
    "PolicyEffect",
    "ReplayEventPayload",
    "validate_lease_lifecycle_event_payload",
    "validate_policy_check_event_payload",
    "validate_replay_event_payload",
]
