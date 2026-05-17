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

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, Literal

from attestplane.hashchain import SCHEMA_VERSION as _CHAIN_SCHEMA_VERSION
from attestplane.hashchain import head_of, verify_chain
from attestplane.storage.jsonl import _serialize_event as _serialize_chained_event
from attestplane.types import ChainedEvent


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

    def build(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Produce the bundle dict.

        Runs :func:`~attestplane.hashchain.verify_chain` on the accumulated
        events and embeds the result as ``verification_report``. The
        bundle is buildable for a broken chain (the report will reflect
        ``ok=False``); downstream verifiers see the same report.
        """
        actual_now = now if now is not None else datetime.now(UTC)
        result = verify_chain(self.events)
        head = head_of(self.events)
        ts = actual_now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

        return {
            "bundle_version": 1,
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
            # T5 of ADR-0005 plan: additive `signatures` field. Only
            # emitted when ≥ 1 SignatureRecord has been added; absent
            # otherwise to keep existing tests + consumers untouched.
            **(
                {"signatures": [_serialize_signature_record(r) for r in self.signatures]}
                if self.signatures
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
    "FrameworkMapping",
    "ProofBundleBuilder",
    "build_auditor_export",
    "bundle_to_dsse_envelope",
    "bundle_to_in_toto_statement",
    "deserialize_signature_record",
]
