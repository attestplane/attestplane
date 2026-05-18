# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""in-toto Statement v1 + DSSE serialization for Attestplane evidence.

Implements the competitive_positioning_upgrade_plan_20260517.md
Track 1 (tickets #29 + #30): Attestplane evidence bundles serialize as
in-toto Statement v1 envelopes with a custom predicateType under
``https://attestplane.io/v1/agent-runtime-event``, optionally wrapped
in DSSE (Dead Simple Signing Envelope).

This makes every Attestplane chain natively consumable by:

- ``cosign verify-blob`` and the broader Sigstore tooling
- ``slsa-verifier`` and SLSA Provenance-aware tooling
- GUAC ingestion pipelines
- Any tool that already speaks in-toto's predicate / subject model

References:

- in-toto Attestation Framework v1:
  https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md
- DSSE v1: https://github.com/secure-systems-lab/dsse
- SLSA Provenance v1 (a sibling predicate using the same envelope):
  https://slsa.dev/spec/v1.0/provenance

The predicateType is registered by Attestplane Pte. Ltd. and does NOT
require OpenSSF / SLSA blessing per the
``competitive_positioning_upgrade_plan_20260517.md`` § 7 risk
register.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Final

PREDICATE_TYPE_V1: Final[str] = "https://attestplane.io/v1/agent-runtime-event"
"""URL identifying the v1 Attestplane in-toto predicate type."""

DSSE_PAYLOAD_TYPE: Final[str] = "application/vnd.in-toto+json"
"""DSSE payloadType for an in-toto Statement; matches the in-toto spec."""

STATEMENT_TYPE: Final[str] = "https://in-toto.io/Statement/v1"
"""``_type`` value for an in-toto Statement v1."""


class IntotoError(Exception):
    """Base class for in-toto / DSSE serialization errors."""


def proof_bundle_to_in_toto_statement(bundle: dict[str, Any]) -> dict[str, Any]:
    """Convert an Attestplane proof bundle to an in-toto Statement v1.

    The Statement's ``subject`` references the chain head hash:
    ``[{ "name": chain_id, "digest": { "sha256": head_hash_hex } }]``.

    The ``predicate`` carries the substantive Attestplane evidence:
    chain metadata, full events array, verification report, framework
    mappings, forbidden_fields, and (if present) the optional anchor
    references. Downstream tools that understand in-toto Statements
    can index by subject digest; tools that understand the Attestplane
    predicate type can extract the full chain.

    :param bundle: an Attestplane proof bundle dict as produced by
        :class:`~attestplane.proof_bundle.ProofBundleBuilder.build`.
    :returns: a dict satisfying the in-toto Statement v1 schema.
    """
    if not isinstance(bundle, dict):
        raise IntotoError("bundle must be a dict")
    cm = bundle.get("chain_metadata")
    if not isinstance(cm, dict):
        raise IntotoError("bundle.chain_metadata missing or not a dict")

    chain_id = cm.get("chain_id")
    head_hash_hex = cm.get("head_hash_hex")
    if not chain_id or not head_hash_hex:
        raise IntotoError(
            "bundle.chain_metadata must include chain_id and head_hash_hex"
        )

    return {
        "_type": STATEMENT_TYPE,
        "subject": [
            {
                "name": chain_id,
                "digest": {"sha256": head_hash_hex},
            }
        ],
        "predicateType": PREDICATE_TYPE_V1,
        "predicate": {
            "chain_metadata": cm,
            "events": bundle.get("events", []),
            "verification_report": bundle.get("verification_report"),
            "framework_mappings": bundle.get("framework_mappings", []),
            "forbidden_fields": bundle.get("forbidden_fields", []),
        },
    }


def statement_to_dsse_envelope(
    statement: dict[str, Any],
    *,
    signatures: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Wrap an in-toto Statement in a DSSE envelope.

    The envelope's ``payload`` is the canonical JSON of the Statement
    encoded as base64, and ``payloadType`` is
    ``application/vnd.in-toto+json``. Signatures are optional in v1;
    callers that have a signing key can populate them, otherwise the
    envelope ships unsigned (still useful for in-toto-aware tooling
    that performs transparency-log lookups by payload digest).

    :param statement: the dict produced by :func:`proof_bundle_to_in_toto_statement`.
    :param signatures: optional list of DSSE signature dicts; each is
        ``{"keyid": str, "sig": base64-encoded bytes}``.
    :returns: a DSSE envelope dict.
    """
    payload_bytes = canonical_json_bytes(statement)
    payload_b64 = base64.standard_b64encode(payload_bytes).decode("ascii")
    return {
        "payloadType": DSSE_PAYLOAD_TYPE,
        "payload": payload_b64,
        "signatures": signatures if signatures is not None else [],
    }


def canonical_json_bytes(value: Any) -> bytes:
    """Return the canonical JSON bytes used as DSSE payload.

    Uses sorted keys + compact separators; matches the conventions
    documented in the in-toto Statement spec and the DSSE
    "PAE" pre-authentication encoding requirements (the DSSE PAE
    happens at sign time, not here; this function just produces the
    inner payload bytes).
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE v1 Pre-Authentication Encoding (PAE).

    Per https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
    the bytes signed are::

        "DSSEv1" SP LEN(payloadType) SP payloadType SP LEN(payload) SP payload

    where ``SP`` is a single ASCII space (0x20) and ``LEN`` is the
    ASCII-decimal length. Signers and verifiers must encode this
    consistently or signatures will not verify. The intent of PAE is
    to prevent length-extension and field-confusion attacks where the
    same bytes could be parsed as a different payload type.

    :param payload_type: the DSSE ``payloadType`` URI
        (e.g. ``application/vnd.in-toto+json``).
    :param payload: the raw payload bytes (NOT base64; the caller must
        base64-decode :class:`statement_to_dsse_envelope`'s output
        before calling this).
    :returns: the PAE bytes ready to be signed or verified.
    """
    pt_bytes = payload_type.encode("utf-8")
    return (
        b"DSSEv1 "
        + str(len(pt_bytes)).encode("ascii")
        + b" "
        + pt_bytes
        + b" "
        + str(len(payload)).encode("ascii")
        + b" "
        + payload
    )


def dsse_envelope_to_statement(envelope: dict[str, Any]) -> dict[str, Any]:
    """Inverse of :func:`statement_to_dsse_envelope`. Validates payloadType."""
    if not isinstance(envelope, dict):
        raise IntotoError("envelope must be a dict")
    payload_type = envelope.get("payloadType")
    if payload_type != DSSE_PAYLOAD_TYPE:
        raise IntotoError(
            f"unexpected payloadType: {payload_type!r}; "
            f"expected {DSSE_PAYLOAD_TYPE!r}"
        )
    payload_b64 = envelope.get("payload")
    if not isinstance(payload_b64, str):
        raise IntotoError("envelope.payload must be a base64 string")
    try:
        payload_bytes = base64.standard_b64decode(payload_b64)
    except Exception as exc:
        raise IntotoError(f"failed to base64-decode payload: {exc}") from exc
    try:
        statement = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise IntotoError(f"payload is not valid JSON: {exc.msg}") from exc
    if not isinstance(statement, dict):
        raise IntotoError("payload JSON must be an object")
    return statement


__all__ = [
    "DSSE_PAYLOAD_TYPE",
    "PREDICATE_TYPE_V1",
    "STATEMENT_TYPE",
    "IntotoError",
    "canonical_json_bytes",
    "dsse_envelope_to_statement",
    "proof_bundle_to_in_toto_statement",
    "statement_to_dsse_envelope",
]
