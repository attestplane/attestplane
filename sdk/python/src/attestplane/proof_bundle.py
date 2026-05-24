# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Proof-bundle export and auditor-export builders.

A proof bundle is the v1 wire-format that a substrate operator hands to a
verifier, auditor, or regulator. Its shape is locked by
``schemas/v1/proof_bundle.schema.json``; this module produces dicts that
satisfy the schema.

Public surface:

- :class:`ProofBundleBuilder` — accumulates events + metadata; emits a
  dict ready to JSON-encode.
- :func:`build_auditor_export` — derives the auditor-friendly summary
  from a proof bundle.
- :data:`DEFAULT_FORBIDDEN_FIELDS` — the canonical redaction floor seeded
  from AIOS's customer attestation template.

The builders never look at event payloads beyond what the schema
demands. Payload-level redaction is the adapter's responsibility per
ADR-0004 § 4; this module trusts the input and produces the wire
artifact.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, Literal

from attestplane.hashchain import SCHEMA_VERSION as _CHAIN_SCHEMA_VERSION
from attestplane.hashchain import chain_extend, genesis_head, head_of, verify_chain
from attestplane.retention import validate_retention_proof
from attestplane.storage.jsonl import _serialize_event as _serialize_chained_event
from attestplane.types import ChainedEvent, EventDraft
from attestplane.verify_errors import VERIFY_BUNDLE_SCHEMA_INCOMPLETE, VERIFY_REQUIRED_FIELDS_MISSING, VerifyErrorCode


_BUNDLE_SCHEMA_MAJOR = 1
_BUNDLE_SCHEMA_MINOR = 7
_BUNDLE_SCHEMA_VERSION = f"{_BUNDLE_SCHEMA_MAJOR}.{_BUNDLE_SCHEMA_MINOR}"


def _sdk_version() -> str:
    """Resolve the SDK version lazily to avoid a circular import on package init."""
    from attestplane import __version__ as v
    return v


def _serialize_signature_record(record: Any) -> dict[str, Any]:
    """Wire-format encoding of a :class:`~attestplane.signing.SignatureRecord`.

    Convention (parallels :func:`_serialize_chained_event`):

    - Fixed-length crypto values use hex (event_hash, signature).
    - Variable-length binary blobs use base64 (public_key_der,
      signing_cert_chain, signed_payload).
    - Datetimes use the substrate's RFC 3339 µs-Z form.
    - Enums + strings + ints pass through as-is.
    """
    from base64 import standard_b64encode
    return {
        "signature_schema_version": record.signature_schema_version,
        "signed_seq": record.signed_seq,
        "signed_event_hash_hex": record.signed_event_hash.hex(),
        "signature_hex": record.signature.hex(),
        "key_id": record.key_id,
        "public_key_der_b64": standard_b64encode(record.public_key_der).decode("ascii"),
        "signing_cert_chain_b64": [
            standard_b64encode(c).decode("ascii") for c in record.signing_cert_chain
        ],
        "signed_at": record.signed_at.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        "signature_mode": record.signature_mode,
        "signed_payload_b64": standard_b64encode(record.signed_payload).decode("ascii"),
    }


def deserialize_signature_record(raw: dict[str, Any]) -> Any:
    """Inverse of :func:`_serialize_signature_record`.

    Returns a :class:`~attestplane.signing.SignatureRecord` (typed as
    Any because the signing module is an optional import). Raises
    :class:`ValueError` on malformed input.
    """
    from base64 import standard_b64decode
    from datetime import UTC

    try:
        from attestplane.signing import SignatureRecord
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "deserialize_signature_record requires attestplane[signing]"
        ) from exc

    required = {
        "signature_schema_version", "signed_seq", "signed_event_hash_hex",
        "signature_hex", "key_id", "public_key_der_b64",
        "signing_cert_chain_b64", "signed_at", "signature_mode",
        "signed_payload_b64",
    }
    missing = required - set(raw.keys())
    if missing:
        raise ValueError(
            f"deserialize_signature_record: missing fields {sorted(missing)}"
        )

    ts_text = raw["signed_at"]
    if ts_text.endswith("Z"):
        signed_at = datetime.strptime(ts_text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    else:
        signed_at = datetime.fromisoformat(ts_text)

    return SignatureRecord(
        signature_schema_version=int(raw["signature_schema_version"]),
        signed_seq=int(raw["signed_seq"]),
        signed_event_hash=bytes.fromhex(raw["signed_event_hash_hex"]),
        signature=bytes.fromhex(raw["signature_hex"]),
        key_id=str(raw["key_id"]),
        public_key_der=standard_b64decode(raw["public_key_der_b64"]),
        signing_cert_chain=tuple(
            standard_b64decode(c) for c in raw["signing_cert_chain_b64"]
        ),
        signed_at=signed_at,
        signature_mode=raw["signature_mode"],
        signed_payload=standard_b64decode(raw["signed_payload_b64"]),
    )

DEFAULT_FORBIDDEN_FIELDS: Final[tuple[str, ...]] = (
    "customer_names",
    "person_names",
    "pii",
    "raw_documents",
    "contracts",
    "scripts",
    "tickets",
    "emails",
    "secrets",
    "tokens",
    "jwts",
    "private_keys",
    "raw_audit_payloads",
)
"""The thirteen-term redaction floor. Producers MAY add more; MUST NOT remove."""

_VERIFICATION_METHOD = Literal["canonical-bytes-walk", "canonical-bytes-walk+anchor"]
_LOWER_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ProofBundleError(Exception):
    """Base class for SDK proof-bundle construction and strict verification errors."""

    error_code: VerifyErrorCode

    def __init__(self, message: str, *, error_code: VerifyErrorCode) -> None:
        super().__init__(message)
        self.error_code = error_code


class EmptyProofBundleError(ProofBundleError):
    """Strict SDK verification rejected a proof bundle with no events."""

    def __init__(
        self,
        message: str = "proof bundle must contain at least one event",
        *,
        error_code: VerifyErrorCode = VERIFY_REQUIRED_FIELDS_MISSING,
    ) -> None:
        super().__init__(message, error_code=error_code)


class IncompleteProofBundleError(ProofBundleError):
    """Strict SDK construction or verification rejected an incomplete proof bundle."""

    def __init__(
        self,
        message: str = "proof bundle lacks the minimum signed-attestation schema",
        *,
        error_code: VerifyErrorCode = VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
    ) -> None:
        super().__init__(message, error_code=error_code)


@dataclass(frozen=True, slots=True)
class FrameworkMapping:
    """A single framework-coverage claim attached to a bundle."""

    obligation_id: str
    evidence_event_indexes: tuple[int, ...]
    implementation_status_at_bundle_time: Literal[
        "mapping_target", "designed_toward", "field_supported", "verified_in_test"
    ]


@dataclass
class ProofBundleBuilder:
    """Accumulate events + metadata into a proof bundle dict.

    Typical flow::

        builder = ProofBundleBuilder(
            chain_id="my-chain",
            producer_runtime="my-runtime v1.0.0",
        )
        builder.extend(events)
        bundle = builder.build()
        json.dump(bundle, file)

    The builder is **not** thread-safe; create one per bundle build.
    """

    chain_id: str
    producer_runtime: str
    events: list[ChainedEvent] = field(default_factory=list)
    framework_mappings: list[FrameworkMapping] = field(default_factory=list)
    forbidden_fields: tuple[str, ...] = DEFAULT_FORBIDDEN_FIELDS
    anchor_ref: str | None = None
    signatures: list[Any] = field(default_factory=list)
    """Optional list of :class:`~attestplane.signing.SignatureRecord`
    instances accumulated via :meth:`extend_signatures`. Defaults to
    empty; populated via T5 of the ADR-0005 plan. Typed as ``list[Any]``
    to avoid pulling in the ``[signing]`` extras transitively when only
    chain bundles are needed."""
    retention_proofs: list[dict[str, Any]] = field(default_factory=list)
    """Optional ADR-0015 commit-then-redact proof markers.

    These markers are strictly additive. They prove shape and references only;
    they do not claim GDPR compliance or legal sufficiency.
    """

    @classmethod
    def minimal(
        cls,
        subject_digest: str,
        signer: Any,
        *,
        extra_payload: dict[str, Any] | None = None,
        now: datetime | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        """Return a minimum-valid signed proof bundle for ``subject_digest``.

        ``subject_digest`` must be a lowercase SHA-256 hex digest. It is stored
        as the event ``matched_input_ref`` and in the event payload, while the
        signature covers the canonical bundle event digest required by strict
        proof-bundle schema verification.

        The helper canonicalizes or constrains the values it owns before emit:
        it requires lowercase 64-hex ``subject_digest`` text, merges optional
        ``extra_payload`` into a single Python mapping with no duplicate JSON
        keys, routes the event through ``chain_extend`` so payload strings must
        already be NFC and integers must be signed-int64 safe, emits UTC
        microsecond ``Z`` timestamps, serializes events with sorted canonical
        storage keys, and signs the canonical event digest used by strict
        minimum-bundle verification.

        The helper does not repair malformed raw JSON received by a verifier.
        Strict verifiers must still reject duplicate raw JSON keys before dict
        collapse, BOM/trailing bytes around canonical JSON input, hand-crafted
        signature or metadata closure drift, non-NFC strings, unsafe integer
        payloads, and timestamp text outside the accepted strict shape.

        Stability guarantee for v1.7.x: this method remains additive, returns a
        v1 proof-bundle dict with one event and at least one syntactically valid
        per-event signature, and the returned shape stays valid for
        ``verify_proof_bundle(..., require_non_empty=True,
        require_signed_attestation=True)``. Existing public symbols are not
        removed or renamed by this helper.
        """
        if not isinstance(subject_digest, str) or _LOWER_HEX64.fullmatch(subject_digest) is None:
            raise IncompleteProofBundleError("subject_digest must be lowercase 64-hex SHA-256")
        if not hasattr(signer, "sign_event"):
            raise IncompleteProofBundleError("signer must provide sign_event(event)")
        if extra_payload is not None and not isinstance(extra_payload, dict):
            raise IncompleteProofBundleError("extra_payload must be a JSON object")
        if extra_payload is not None and "subject_digest" in extra_payload:
            raise IncompleteProofBundleError("extra_payload must not override subject_digest")

        actual_now = now if now is not None else datetime.now(UTC)
        payload = {"subject_digest": subject_digest, **(extra_payload or {})}
        event = chain_extend(
            genesis_head(),
            EventDraft(
                event_type="evidence_event",
                actor="attestplane.sdk",
                payload=payload,
                matched_input_ref=subject_digest,
            ),
            now=actual_now,
            event_id=event_id,
        )
        try:
            records = signer.sign_event(event)
        except Exception as exc:
            raise IncompleteProofBundleError(f"signer failed to sign minimal bundle event: {exc}") from exc
        if not records:
            raise IncompleteProofBundleError("signer returned no signature records")

        chain_id = str(getattr(signer, "_chain_id", "attestplane-sdk-minimal"))
        builder = cls(chain_id=chain_id, producer_runtime="attestplane-sdk-minimal")
        builder.extend([event])
        builder.extend_signatures(list(records))
        return builder.build(now=actual_now)

    def extend(self, events: list[ChainedEvent]) -> None:
        self.events.extend(events)

    def add_framework_mapping(self, mapping: FrameworkMapping) -> None:
        for idx in mapping.evidence_event_indexes:
            if not 0 <= idx < len(self.events):
                raise ValueError(
                    f"framework_mapping for {mapping.obligation_id!r} references "
                    f"event index {idx} but bundle has only {len(self.events)} events"
                )
        self.framework_mappings.append(mapping)

    def extend_signatures(self, records: list[Any]) -> None:
        """Add :class:`~attestplane.signing.SignatureRecord` instances.

        Lightly typed as ``list[Any]`` so this method works for callers
        without the ``[signing]`` extras installed; runtime type checks
        on serialisation catch malformed entries.
        """
        # Late validation: every entry must look like a SignatureRecord
        # (duck-typed; full type would require the [signing] extras).
        for r in records:
            if not all(hasattr(r, attr) for attr in (
                "signature_schema_version", "signed_seq", "signed_event_hash",
                "signature", "key_id", "public_key_der", "signing_cert_chain",
                "signed_at", "signature_mode", "signed_payload",
            )):
                raise ValueError(
                    f"extend_signatures: object missing SignatureRecord fields: "
                    f"{type(r).__name__}"
                )
        self.signatures.extend(records)

    def extend_retention_proofs(self, records: list[dict[str, Any]]) -> None:
        """Add commit-then-redact proof markers.

        The verifier later checks that marker hashes reference events present in
        the bundle. This method validates marker shape before serialization.
        """
        for record in records:
            validate_retention_proof(record)
        self.retention_proofs.extend(records)

    def build(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Produce the bundle dict.

        Runs :func:`~attestplane.hashchain.verify_chain` on the accumulated
        events and embeds the result as ``verification_report``. The
        bundle is buildable for a broken chain (the report will reflect
        ``ok=False``); downstream verifiers see the same report.

        Auto-populates ADR-0012 ``policy_trace_refs`` by walking
        ``self.events`` once and collecting ``event_hash_hex`` of any
        ``policy_check_event``. Absent (not empty list) when no
        policy_check_event rows are present.
        """
        actual_now = now if now is not None else datetime.now(UTC)
        result = verify_chain(self.events)
        head = head_of(self.events)
        ts = actual_now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

        # ADR-0012 P1.2: auto-derive policy_trace_refs (chain-seq-ordered hex hashes
        # for every policy_check_event). Absent when empty per ADR-0012 § 1.
        from attestplane.event_types import POLICY_CHECK_EVENT
        policy_trace_refs = [
            ev.event_hash.hex()
            for ev in self.events
            if ev.event.event_type == POLICY_CHECK_EVENT
        ]

        return {
            "bundle_version": 1,
            "schema_version": _BUNDLE_SCHEMA_VERSION,
            "chain_metadata": {
                "chain_id": self.chain_id,
                "schema_version": _CHAIN_SCHEMA_VERSION,
                "genesis_hash_hex": "00" * 32,
                "head_hash_hex": head.event_hash.hex(),
                "head_seq": head.seq,
                "producer_runtime": self.producer_runtime,
                "evidence_taxonomy_version": 1,
                **({"anchor_ref": self.anchor_ref} if self.anchor_ref else {}),
            },
            "events": [_serialize_chained_event(ev) for ev in self.events],
            "verification_report": {
                "ok": result.ok,
                "first_bad_index": result.first_bad_index,
                "reason": result.reason,
                "verified_at": ts,
                "verifier_version": _sdk_version(),
                "verification_method": "canonical-bytes-walk",
            },
            "framework_mappings": [
                {
                    "obligation_id": m.obligation_id,
                    "evidence_event_indexes": list(m.evidence_event_indexes),
                    "implementation_status_at_bundle_time":
                        m.implementation_status_at_bundle_time,
                }
                for m in self.framework_mappings
            ],
            "forbidden_fields": list(self.forbidden_fields),
            # ADR-0012 P1.2: additive policy_trace_refs (absent when empty).
            **(
                {"policy_trace_refs": policy_trace_refs}
                if policy_trace_refs
                else {}
            ),
            # T5 of ADR-0005 plan: additive `signatures` field. Only
            # emitted when ≥ 1 SignatureRecord has been added; absent
            # otherwise to keep existing tests + consumers untouched.
            **(
                {"signatures": [_serialize_signature_record(r) for r in self.signatures]}
                if self.signatures
                else {}
            ),
            **(
                {"retention_proofs": list(self.retention_proofs)}
                if self.retention_proofs
                else {}
            ),
        }


def build_auditor_export(
    bundle: dict[str, Any],
    *,
    framework_coverage_registries: list[Any] | None = None,
    redaction_status: Literal[
        "enforced_by_adapter", "enforced_by_producer", "unenforced"
    ] = "enforced_by_producer",
    consent_status: Literal[
        "consent_present", "consent_absent", "consent_not_applicable"
    ] = "consent_not_applicable",
    legal_disclaimer: str | None = None,
) -> dict[str, Any]:
    """Build the auditor-friendly export from a proof bundle.

    Strict subset of the input: no event payloads. The
    ``framework_coverage`` rollup is computed by walking
    ``bundle["events"]`` and grouping by framework + article based on
    obligation_ids mentioned in ``bundle["framework_mappings"]``. If
    ``framework_coverage_registries`` is provided, the rollup also lists
    obligation_ids from those registries that are NOT covered by any
    event — surfacing absence per the schema description.
    """
    events = bundle["events"]
    mappings = bundle.get("framework_mappings", [])

    # Event-type histogram (the auditor's at-a-glance distribution).
    histogram: Counter[str] = Counter()
    for ev in events:
        histogram[ev["event"]["event_type"]] += 1

    # Time range — earliest and latest timestamps in the chain.
    if events:
        timestamps = [ev["event"]["timestamp"] for ev in events]
        time_range = {
            "earliest": min(timestamps),
            "latest": max(timestamps),
        }
    else:
        sentinel = bundle["verification_report"]["verified_at"]
        time_range = {"earliest": sentinel, "latest": sentinel}

    covered_obligation_ids = {m["obligation_id"] for m in mappings}

    # Group coverage by (framework, article) — pulled from the registries
    # if available, otherwise inferred from the obligation_ids' dotted
    # prefix structure.
    coverage_rows: list[dict[str, Any]] = []
    if framework_coverage_registries:
        for registry in framework_coverage_registries:
            by_article: dict[str, list[Any]] = {}
            for entry in registry.entries:
                by_article.setdefault(entry.article, []).append(entry)
            for article, entries in sorted(by_article.items()):
                with_evidence = sorted(
                    e.obligation_id for e in entries
                    if e.obligation_id in covered_obligation_ids
                )
                without_evidence = sorted(
                    e.obligation_id for e in entries
                    if e.obligation_id not in covered_obligation_ids
                )
                coverage_rows.append({
                    "framework": registry.framework,
                    "article": article,
                    "obligation_ids_with_evidence": with_evidence,
                    "obligation_ids_without_evidence": without_evidence,
                })

    default_disclaimer = (
        "This export is a technical chain-integrity and framework-coverage summary. "
        "It is not a compliance opinion. Consult qualified counsel for any "
        "regulatory determination."
    )

    return {
        "export_version": 1,
        "chain_summary": {
            "chain_id": bundle["chain_metadata"]["chain_id"],
            "head_hash_hex": bundle["chain_metadata"]["head_hash_hex"],
            "event_count": len(events),
            "time_range": time_range,
            "producer_runtime": bundle["chain_metadata"]["producer_runtime"],
            "event_type_histogram": dict(histogram),
            "anchor_status": "unanchored",
        },
        "verification_status": {
            "ok": bundle["verification_report"]["ok"],
            "first_bad_index": bundle["verification_report"]["first_bad_index"],
            "reason": bundle["verification_report"]["reason"],
            "verified_at": bundle["verification_report"]["verified_at"],
            "verifier_version": bundle["verification_report"]["verifier_version"],
            "verification_method": bundle["verification_report"]["verification_method"],
        },
        "framework_coverage": coverage_rows,
        "redaction_policy": {
            "forbidden_fields": list(bundle["forbidden_fields"]),
            "redaction_status": redaction_status,
            "consent_status": consent_status,
        },
        "legal_disclaimer": legal_disclaimer if legal_disclaimer is not None else default_disclaimer,
    }


def bundle_to_in_toto_statement(bundle: dict[str, Any]) -> dict[str, Any]:
    """Convenience: convert a built bundle dict to an in-toto Statement v1.

    Thin re-export of
    :func:`attestplane.intoto.proof_bundle_to_in_toto_statement` placed
    here so callers who already import ``attestplane.proof_bundle``
    don't need a second import for the common case.
    """
    from attestplane.intoto import proof_bundle_to_in_toto_statement
    return proof_bundle_to_in_toto_statement(bundle)


def bundle_to_dsse_envelope(
    bundle: dict[str, Any],
    *,
    signatures: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Convenience: convert a built bundle dict to a DSSE envelope.

    Equivalent to ``statement_to_dsse_envelope(bundle_to_in_toto_statement(b))``;
    bundled here as the single-call path most adapters will use.
    """
    from attestplane.intoto import (
        proof_bundle_to_in_toto_statement,
        statement_to_dsse_envelope,
    )
    statement = proof_bundle_to_in_toto_statement(bundle)
    return statement_to_dsse_envelope(statement, signatures=signatures)


__all__ = [
    "DEFAULT_FORBIDDEN_FIELDS",
    "EmptyProofBundleError",
    "FrameworkMapping",
    "IncompleteProofBundleError",
    "ProofBundleError",
    "ProofBundleBuilder",
    "build_auditor_export",
    "bundle_to_dsse_envelope",
    "bundle_to_in_toto_statement",
    "deserialize_signature_record",
]
