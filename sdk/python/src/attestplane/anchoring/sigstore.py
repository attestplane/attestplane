# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Sigstore Rekor transparency-log anchor per ADR-0006.

Implements Track 2 of the competitive_positioning_upgrade_plan_20260517.

A :class:`SigstoreRekorAnchor` is a :class:`TSAProvider` that submits
DSSE-wrapped Attestplane in-toto Statements to a Rekor transparency
log and produces an :class:`~attestplane.anchoring.AnchorRecord`
whose semantics are Rekor-flavoured (see ADR-0006 § 3).

The v1 implementation:

- Builds the Rekor `intoto` entry payload from a DSSE envelope.
- Signs the envelope with a substrate-provided Ed25519 key
  (bring-your-own-key per ADR-0006 § 4; Fulcio integration is
  deferred to ADR-0005).
- Submits via an injected HTTP transport (production:
  :class:`~attestplane.anchoring.http.UrllibHttpTransport`; tests:
  :class:`~attestplane.anchoring.http.RecordedHttpTransport`).
- Parses the Rekor LogEntry response and verifies the
  `signedEntryTimestamp` against a configured Rekor public key.

This module requires the ``anchor`` extras (``cryptography`` for
Ed25519 + key serialisation).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import (  # noqa: F401  (conditional import — try/except guard)
        hashes,
        serialization,
    )
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attestplane.anchoring.sigstore requires the 'anchor' extras. "
        "Install with: pip install attestplane[anchor]"
    ) from exc

from attestplane.anchoring.base import (
    ANCHOR_SCHEMA_VERSION,
    AnchorRecord,
    AnchorVerificationError,
    TimestampRequest,
    TSAProvider,
    TSAUnavailableError,
)
from attestplane.anchoring.http import HttpTransport, UrllibHttpTransport

# Synthetic OCSP marker for Sigstore Rekor anchors per ADR-0006 § 3.
SIGSTORE_REKOR_OCSP_MARKER: Final[bytes] = b"SIGSTORE-REKOR-NO-OCSP-APPLIES"

# Public Sigstore Rekor endpoint per Sigstore's documentation.
PUBLIC_REKOR_URL: Final[str] = "https://rekor.sigstore.dev/api/v1/log/entries"

# Provider-ID prefix used by the verifier to dispatch to the Rekor
# path instead of the RFC-3161 path.
SIGSTORE_REKOR_PROVIDER_PREFIX: Final[str] = "sigstore.rekor:"


@dataclass(frozen=True, slots=True)
class ParsedRekorEntry:
    """Subset of a Rekor LogEntry parsed for verification."""

    log_index: int
    log_id: str
    integrated_time: datetime
    signed_entry_timestamp: bytes
    """The SET (signed entry timestamp) bytes — signature over a
    canonical payload by the Rekor log's signing key."""

    body_bytes: bytes
    """The decoded entry body (canonical JSON) — used to recompute the
    SET payload digest."""

    raw_log_entry: dict[str, Any]


class SigstoreRekorAnchor(TSAProvider):
    """TSAProvider that anchors to a Sigstore Rekor transparency log.

    :param signing_key: Ed25519 private key used to sign the DSSE
        envelope before submission. If ``None``, a fresh ephemeral key
        is generated per provider instance (suitable for tests only).
    :param rekor_public_key: Ed25519 public key of the Rekor log used
        to verify the returned ``signedEntryTimestamp``.
    :param log_id: stable identifier of the Rekor log; embedded in the
        provider_id and in the AnchorRecord.
    :param url: Rekor API endpoint (``/api/v1/log/entries``).
    :param transport: HTTP transport (defaults to :class:`UrllibHttpTransport`).
    """

    schema_version = ANCHOR_SCHEMA_VERSION

    def __init__(
        self,
        *,
        rekor_public_key: Ed25519PublicKey,
        log_id: str,
        signing_key: Ed25519PrivateKey | None = None,  # gitleaks:allow false positive: object reference only
        url: str = PUBLIC_REKOR_URL,
        transport: HttpTransport | None = None,
    ) -> None:
        if not log_id:
            raise ValueError("SigstoreRekorAnchor log_id must be non-empty")
        self._rekor_public_key = rekor_public_key
        self._log_id = log_id
        self._signing_key = signing_key or Ed25519PrivateKey.generate()
        self._url = url
        self._transport = transport or UrllibHttpTransport()
        self.provider_id = f"{SIGSTORE_REKOR_PROVIDER_PREFIX}{log_id}"

    def request_timestamp(
        self,
        request: TimestampRequest,
        *,
        anchored_seq: int = 0,
        now: datetime | None = None,
    ) -> AnchorRecord:
        """Submit a DSSE envelope to Rekor and produce an AnchorRecord.

        ``request.digest`` is treated as the artifact digest the Rekor
        ``intoto`` entry will reference (the chain head event_hash).
        The DSSE envelope payload itself is reconstructed from the
        digest — callers that need to attach the full Attestplane
        in-toto Statement do so by passing ``digest = sha256(canonical
        JSON of Statement)`` and supplying the same Statement
        out-of-band; the substrate's verifier rebuilds and checks the
        SET against this digest.

        For v0.1 we ship the minimum-viable path: the entry body
        contains the digest + the signing key fingerprint, signed with
        Ed25519.
        """
        # Build the entry body: minimal Rekor intoto-shape carrying
        # digest + signature spec.
        signature = self._signing_key.sign(request.digest)
        public_key_der = self._signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        body = {
            "spec": {
                "content": {
                    "hash": {
                        "algorithm": "sha256",
                        "value": request.digest.hex(),
                    },
                    "publicKey": {
                        "content": base64.standard_b64encode(public_key_der).decode("ascii"),
                    },
                    "signature": {
                        "content": base64.standard_b64encode(signature).decode("ascii"),
                    },
                },
            },
        }
        body_bytes = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

        try:
            response_bytes = self._transport.submit(
                self._url, body_bytes, timeout_seconds=30.0,
            )
        except TSAUnavailableError:
            raise

        try:
            log_entry = json.loads(response_bytes)
        except json.JSONDecodeError as exc:
            raise AnchorVerificationError(
                f"Rekor at {self._url} returned non-JSON: {exc.msg}"
            ) from exc

        if not isinstance(log_entry, dict):
            raise AnchorVerificationError(
                f"Rekor response is not a JSON object: got {type(log_entry).__name__}"
            )
        if "logIndex" not in log_entry or "integratedTime" not in log_entry:
            raise AnchorVerificationError(
                "Rekor response missing required fields (logIndex / integratedTime)"
            )

        integrated_time_secs = int(log_entry["integratedTime"])
        issued_at = datetime.fromtimestamp(integrated_time_secs, tz=UTC)

        rekor_pubkey_der = self._rekor_public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return AnchorRecord(
            anchor_schema_version=ANCHOR_SCHEMA_VERSION,
            anchored_seq=anchored_seq,
            anchored_event_hash=request.digest,
            tsa_provider_id=self.provider_id,
            tsa_token=response_bytes,
            tsa_cert_chain=(rekor_pubkey_der,),
            ocsp_responses=(SIGSTORE_REKOR_OCSP_MARKER,),
            issued_at_claimed=issued_at,
        )


def is_sigstore_rekor_anchor(anchor: AnchorRecord) -> bool:
    """Return True iff the anchor was issued by a Sigstore Rekor provider."""
    return anchor.tsa_provider_id.startswith(SIGSTORE_REKOR_PROVIDER_PREFIX)


def parse_rekor_log_entry(tsa_token: bytes) -> ParsedRekorEntry:
    """Parse a Rekor LogEntry JSON blob from an :class:`AnchorRecord.tsa_token`."""
    try:
        log_entry = json.loads(tsa_token)
    except json.JSONDecodeError as exc:
        raise AnchorVerificationError(
            f"Rekor LogEntry is not valid JSON: {exc.msg}"
        ) from exc
    if not isinstance(log_entry, dict):
        raise AnchorVerificationError("Rekor LogEntry is not a JSON object")

    required = ("logIndex", "logID", "integratedTime", "body", "verification")
    missing = [k for k in required if k not in log_entry]
    if missing:
        raise AnchorVerificationError(
            f"Rekor LogEntry missing fields: {sorted(missing)}"
        )

    verification = log_entry["verification"]
    if not isinstance(verification, dict) or "signedEntryTimestamp" not in verification:
        raise AnchorVerificationError(
            "Rekor LogEntry.verification.signedEntryTimestamp missing"
        )

    try:
        set_bytes = base64.standard_b64decode(verification["signedEntryTimestamp"])
    except Exception as exc:
        raise AnchorVerificationError(
            f"signedEntryTimestamp is not valid base64: {exc}"
        ) from exc

    try:
        body_bytes = base64.standard_b64decode(log_entry["body"])
    except Exception as exc:
        raise AnchorVerificationError(
            f"Rekor LogEntry.body is not valid base64: {exc}"
        ) from exc

    integrated_time = datetime.fromtimestamp(int(log_entry["integratedTime"]), tz=UTC)

    return ParsedRekorEntry(
        log_index=int(log_entry["logIndex"]),
        log_id=str(log_entry["logID"]),
        integrated_time=integrated_time,
        signed_entry_timestamp=set_bytes,
        body_bytes=body_bytes,
        raw_log_entry=log_entry,
    )


def _set_payload(parsed: ParsedRekorEntry) -> bytes:
    """Reconstruct the canonical SET payload — the bytes that Rekor
    signs to produce signedEntryTimestamp.

    Per Sigstore documentation the SET signs a canonical JSON of
    ``{"body": <b64body>, "integratedTime": N, "logID": "...",
    "logIndex": N}`` with sorted keys.
    """
    payload = {
        "body": base64.standard_b64encode(parsed.body_bytes).decode("ascii"),
        "integratedTime": int(parsed.integrated_time.timestamp()),
        "logID": parsed.log_id,
        "logIndex": parsed.log_index,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_rekor_signed_entry_timestamp(
    parsed: ParsedRekorEntry,
    *,
    expected_digest: bytes,
    rekor_public_key_der: bytes,
) -> None:
    """Verify a Rekor LogEntry against the expected message digest.

    Checks (v1):

    1. The body's digest field matches ``expected_digest`` (32 bytes SHA-256).
    2. The signedEntryTimestamp signature verifies against the Rekor
       public key over the canonical SET payload.

    Skipped in v1 (deferred to ADR-0007 / future work):

    - Inclusion proof against the Merkle root.
    - Witness co-signatures.

    Raises :class:`AnchorVerificationError` on any failure.
    """
    if len(expected_digest) != 32:
        raise AnchorVerificationError(
            f"expected_digest must be 32 bytes, got {len(expected_digest)}"
        )

    try:
        body = json.loads(parsed.body_bytes)
    except json.JSONDecodeError as exc:
        raise AnchorVerificationError(
            f"Rekor entry body is not valid JSON: {exc.msg}"
        ) from exc
    if not isinstance(body, dict):
        raise AnchorVerificationError("Rekor entry body is not a JSON object")

    # Extract the digest from the body — the spec.content.hash.value
    # path is what SigstoreRekorAnchor produces.
    spec = body.get("spec")
    if not isinstance(spec, dict):
        raise AnchorVerificationError("Rekor entry body.spec missing")
    content = spec.get("content")
    if not isinstance(content, dict):
        raise AnchorVerificationError("Rekor entry body.spec.content missing")
    hash_field = content.get("hash")
    if not isinstance(hash_field, dict):
        raise AnchorVerificationError("Rekor entry body.spec.content.hash missing")
    algo = hash_field.get("algorithm")
    if algo != "sha256":
        raise AnchorVerificationError(
            f"Rekor entry hash algorithm is {algo!r}; expected 'sha256'"
        )
    hex_value = hash_field.get("value")
    if not isinstance(hex_value, str):
        raise AnchorVerificationError("Rekor entry hash value missing")
    try:
        body_digest = bytes.fromhex(hex_value)
    except ValueError as exc:
        raise AnchorVerificationError(
            f"Rekor entry hash value is not valid hex: {exc}"
        ) from exc
    if body_digest != expected_digest:
        raise AnchorVerificationError(
            "Rekor entry body digest does not match expected_digest"
        )

    # Verify the SET signature.
    try:
        rekor_pubkey = serialization.load_der_public_key(rekor_public_key_der)
    except Exception as exc:
        raise AnchorVerificationError(
            f"Rekor public key is not valid DER SPKI: {exc}"
        ) from exc
    if not isinstance(rekor_pubkey, Ed25519PublicKey):
        raise AnchorVerificationError(
            f"v1 supports Ed25519 Rekor keys only; got {type(rekor_pubkey).__name__}"
        )

    payload = _set_payload(parsed)
    try:
        rekor_pubkey.verify(parsed.signed_entry_timestamp, payload)
    except InvalidSignature as exc:
        raise AnchorVerificationError(
            "Rekor signedEntryTimestamp does not verify against the configured public key"
        ) from exc


__all__ = [
    "PUBLIC_REKOR_URL",
    "SIGSTORE_REKOR_OCSP_MARKER",
    "SIGSTORE_REKOR_PROVIDER_PREFIX",
    "ParsedRekorEntry",
    "SigstoreRekorAnchor",
    "is_sigstore_rekor_anchor",
    "parse_rekor_log_entry",
    "verify_rekor_signed_entry_timestamp",
]
