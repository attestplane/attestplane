# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""RFC-6960 OCSP response parsing and signature verification.

Closes the CAdES-A long-term-validation gap for v0.0.2-alpha. The
in-tree :class:`~attestplane.anchoring.testing.TestTSAAuthority` is
extended to produce **real** OCSP responses (instead of the synthetic
byte string used previously), and this module verifies them.

Scope (v1):

- Parse a DER-encoded :class:`asn1crypto.ocsp.OCSPResponse`.
- Reject non-successful response statuses.
- Verify the responder's RSA-PKCS1v15-SHA256 signature over the
  `tbs_response_data` bytes against the embedded responder cert
  (typical for "responder is the issuer" mode) OR against a configured
  responder cert.
- Look up the SingleResponse for the leaf cert by serial-number match.
- Return :class:`ParsedOcsp` with status (good / revoked / unknown),
  thisUpdate, nextUpdate, and the responder cert DER.

Out of scope (deferred):

- Authorized-responder delegation (responder cert distinct from the
  cert issuer, with `id-pkix-ocsp-no-check` and EKU `OCSPSigning`).
- Multi-CertID OCSP responses (we look at the first match only).
- Nonce extension.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

try:
    from asn1crypto import ocsp
    from asn1crypto import x509 as asn1_x509
    from cryptography import x509
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attestplane.anchoring.ocsp requires the 'anchor' extras. "
        "Install with: pip install attestplane[anchor]"
    ) from exc

from attestplane.anchoring.base import AnchorVerificationError

OcspCertStatus = Literal["good", "revoked", "unknown"]


@dataclass(frozen=True, slots=True)
class ParsedOcsp:
    """Extracted fields from a verified OCSP response."""

    cert_status: OcspCertStatus
    this_update: datetime
    next_update: datetime | None
    serial_number: int
    responder_cert_der: bytes
    produced_at: datetime
    revocation_time: datetime | None


def _is_synthetic_legacy(blob: bytes) -> bool:
    """Identify the v0.0.1-alpha placeholder OCSP body so we can ignore it
    cleanly. Returns True if the bytes start with the synthetic marker."""
    return blob.startswith(b"ATTESTPLANE-TEST-OCSP-V1|")


def parse_and_verify_ocsp(
    response_der: bytes,
    *,
    expected_serial: int,
    issuer_cert_der: bytes,
    verification_time: datetime | None = None,
) -> ParsedOcsp:
    """Parse + verify an OCSP response.

    :param response_der: the DER-encoded OCSPResponse bytes.
    :param expected_serial: serial number of the cert whose status we
        want to check (typically the TSA leaf cert).
    :param issuer_cert_der: DER of the cert that signed the leaf
        (typically the root CA in our two-tier chain). The responder
        signature is verified against this issuer's public key when the
        OCSP response is issuer-signed (the common case).
    :param verification_time: time to compare against
        ``this_update``/``next_update``. Defaults to "now".

    Raises :class:`AnchorVerificationError` on any failure.
    """
    if _is_synthetic_legacy(response_der):
        raise AnchorVerificationError(
            "OCSP response is the v0.0.1-alpha synthetic placeholder; "
            "regenerate via TestTSAAuthority.issue_real_ocsp_response()"
        )

    try:
        ocsp_resp = ocsp.OCSPResponse.load(response_der)
    except Exception as exc:
        raise AnchorVerificationError(
            f"OCSP response is not valid DER: {exc}"
        ) from exc

    status = ocsp_resp["response_status"].native
    if status != "successful":
        raise AnchorVerificationError(f"OCSP responder returned status={status}")

    bytes_value = ocsp_resp["response_bytes"]
    if bytes_value["response_type"].native != "basic_ocsp_response":
        raise AnchorVerificationError(
            f"OCSP response type is not basic_ocsp_response: "
            f"{bytes_value['response_type'].native}"
        )
    basic: ocsp.BasicOCSPResponse = bytes_value["response"].parsed

    # Verify signature over tbs_response_data.
    tbs_bytes = basic["tbs_response_data"].dump()
    signature = bytes(basic["signature"].native)
    sig_algo = basic["signature_algorithm"]["algorithm"].native
    if sig_algo not in ("rsassa_pkcs1v15", "sha256_rsa"):
        raise AnchorVerificationError(
            f"v1 supports only RSA-PKCS1v15 OCSP signatures; got {sig_algo}"
        )

    # Responder cert: either embedded in the response, or the issuer.
    embedded_certs = basic["certs"]
    responder_cert_der: bytes
    try:
        issuer_cert = x509.load_der_x509_certificate(issuer_cert_der)
    except Exception as exc:
        raise AnchorVerificationError(
            f"issuer_cert_der is not valid DER: {exc}"
        ) from exc

    if embedded_certs is not None and len(embedded_certs) > 0:
        responder_asn1 = embedded_certs[0]
        if not isinstance(responder_asn1, asn1_x509.Certificate):
            raise AnchorVerificationError("first OCSP-embedded cert is not a Certificate")
        responder_cert_der = responder_asn1.dump()
        responder_cert = x509.load_der_x509_certificate(responder_cert_der)
        responder_key = responder_cert.public_key()
    else:
        responder_cert_der = issuer_cert_der
        responder_key = issuer_cert.public_key()

    if not isinstance(responder_key, RSAPublicKey):
        raise AnchorVerificationError(
            f"v1 supports RSA OCSP signer keys only; got {type(responder_key).__name__}"
        )

    try:
        responder_key.verify(
            signature,
            tbs_bytes,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature as exc:
        raise AnchorVerificationError(
            "OCSP responder signature does not verify"
        ) from exc

    # Find the SingleResponse matching expected_serial.
    responses = basic["tbs_response_data"]["responses"]
    matching = None
    for single in responses:
        cert_id = single["cert_id"]
        if int(cert_id["serial_number"].native) == expected_serial:
            matching = single
            break
    if matching is None:
        raise AnchorVerificationError(
            f"OCSP response contains no entry for serial {expected_serial}"
        )

    cert_status_choice = matching["cert_status"]
    chosen_name = cert_status_choice.name
    if chosen_name == "good":
        cert_status: OcspCertStatus = "good"
        revocation_time = None
    elif chosen_name == "revoked":
        cert_status = "revoked"
        revoked_info = cert_status_choice.chosen
        revocation_time = revoked_info["revocation_time"].native
    elif chosen_name == "unknown":
        cert_status = "unknown"
        revocation_time = None
    else:
        raise AnchorVerificationError(
            f"unexpected OCSP cert_status: {chosen_name}"
        )

    this_update = matching["this_update"].native
    if this_update.tzinfo is None:
        this_update = this_update.replace(tzinfo=UTC)
    next_update_field = matching["next_update"]
    next_update: datetime | None
    if next_update_field is None or next_update_field.native is None:
        next_update = None
    else:
        next_update = next_update_field.native
        if next_update.tzinfo is None:
            next_update = next_update.replace(tzinfo=UTC)

    produced_at = basic["tbs_response_data"]["produced_at"].native
    if produced_at.tzinfo is None:
        produced_at = produced_at.replace(tzinfo=UTC)

    # Freshness check.
    when = verification_time or datetime.now(UTC)
    if when < this_update:
        raise AnchorVerificationError(
            f"verification_time {when} precedes OCSP thisUpdate {this_update}"
        )
    if next_update is not None and when > next_update:
        raise AnchorVerificationError(
            f"verification_time {when} exceeds OCSP nextUpdate {next_update}"
        )

    return ParsedOcsp(
        cert_status=cert_status,
        this_update=this_update,
        next_update=next_update,
        serial_number=expected_serial,
        responder_cert_der=responder_cert_der,
        produced_at=produced_at,
        revocation_time=revocation_time,
    )


__all__ = [
    "OcspCertStatus",
    "ParsedOcsp",
    "parse_and_verify_ocsp",
]
