# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""RFC-3161 TimeStampResp parsing and signature verification.

Two public functions:

- :func:`parse_timestamp_response` — extract a :class:`ParsedTimestamp`
  from a DER-encoded :class:`asn1crypto.tsp.TimeStampResp` blob.
- :func:`verify_timestamp_token` — given a parsed token, the expected
  message digest, the leaf cert (DER), and a list of trust-root certs
  (DER), check that the TSA signature is valid, the messageImprint
  matches, and the leaf chains to a trust root.

This module requires the ``anchor`` extras (``cryptography`` and
``asn1crypto``). Pure attestplane installs (substrate-only) do not
import it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

try:
    from asn1crypto import algos, cms, tsp, x509 as asn1_x509
    from cryptography import x509
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attestplane.anchoring.rfc3161 requires the 'anchor' extras. "
        "Install with: pip install attestplane[anchor]"
    ) from exc

from attestplane.anchoring.base import AnchorVerificationError

ID_CT_TST_INFO_OID: Final[str] = "tst_info"


@dataclass(frozen=True, slots=True)
class ParsedTimestamp:
    """Subset of a TSTInfo extracted from an RFC-3161 token."""

    policy_oid: str
    hash_algorithm: str
    message_imprint: bytes
    gen_time: datetime
    serial_number: int
    nonce: int | None
    leaf_cert_der: bytes
    signed_attrs_der: bytes
    signature: bytes
    digest_algorithm_oid: str
    signature_algorithm_oid: str


def parse_timestamp_response(response_der: bytes) -> ParsedTimestamp:
    """Parse a DER-encoded :class:`asn1crypto.tsp.TimeStampResp`.

    Raises :class:`AnchorVerificationError` for any structural defect
    (non-granted PKI status, missing token, wrong content type, etc.).
    """
    try:
        response = tsp.TimeStampResp.load(response_der)
    except Exception as exc:
        raise AnchorVerificationError(
            f"timestamp response is not valid DER: {exc}"
        ) from exc

    status = response["status"]["status"].native
    if status not in ("granted", "granted_with_mods"):
        fail_info = response["status"].get("fail_info")
        raise AnchorVerificationError(
            f"TSA refused request: status={status}"
            + (f", fail_info={fail_info.native if fail_info else 'n/a'}"
               if fail_info is not None else "")
        )

    token: cms.ContentInfo = response["time_stamp_token"]
    if token["content_type"].native != "signed_data":
        raise AnchorVerificationError(
            f"timestamp token content_type is not signed_data: "
            f"{token['content_type'].native}"
        )

    signed_data: cms.SignedData = token["content"]
    encap = signed_data["encap_content_info"]
    if encap["content_type"].native != ID_CT_TST_INFO_OID:
        raise AnchorVerificationError(
            f"encapsulated content_type is not tst_info: "
            f"{encap['content_type'].native}"
        )

    inner_octets = encap["content"]
    if inner_octets is None:
        raise AnchorVerificationError("encap_content_info has no content")
    tst_info_der = inner_octets.contents if hasattr(inner_octets, "contents") else inner_octets.native
    if isinstance(tst_info_der, str):
        # asn1crypto returns hex sometimes; force bytes via parsed()
        tst_info_der = inner_octets.parsed.dump()
    try:
        tst_info = tsp.TSTInfo.load(tst_info_der)
    except Exception:
        # Try one more fallback via .parsed
        tst_info = inner_octets.parsed

    message_imprint = tst_info["message_imprint"]
    hash_algo = message_imprint["hash_algorithm"]["algorithm"].native
    hashed = bytes(message_imprint["hashed_message"].native)
    gen_time: datetime = tst_info["gen_time"].native
    if gen_time.tzinfo is None:
        gen_time = gen_time.replace(tzinfo=UTC)

    try:
        nonce_native = tst_info["nonce"].native
        nonce = int(nonce_native) if nonce_native is not None else None
    except KeyError:
        nonce = None

    # Extract the leaf cert.
    try:
        certs = signed_data["certificates"]
    except KeyError:
        certs = None
    if certs is None or len(certs) == 0:
        raise AnchorVerificationError("signed_data has no certificates")
    cert_choice = certs[0]
    leaf_asn1 = cert_choice.chosen if hasattr(cert_choice, "chosen") else cert_choice
    if not isinstance(leaf_asn1, asn1_x509.Certificate):
        raise AnchorVerificationError(
            f"first certificate is not a Certificate: {type(leaf_asn1).__name__}"
        )
    leaf_cert_der = leaf_asn1.dump()

    # Extract the signer info — there must be exactly one.
    signer_infos = signed_data["signer_infos"]
    if len(signer_infos) != 1:
        raise AnchorVerificationError(
            f"expected exactly one SignerInfo, got {len(signer_infos)}"
        )
    signer_info: cms.SignerInfo = signer_infos[0]

    signed_attrs = signer_info["signed_attrs"]
    if signed_attrs is None or len(signed_attrs) == 0:
        raise AnchorVerificationError("SignerInfo has no signed attributes")

    # Re-serialize signed_attrs as a DER SET OF (tag 0x31). asn1crypto's
    # native dump uses IMPLICIT [0] context tag (0xA0) for SignerInfo
    # inclusion; CMS signature input is over the SET-tagged form.
    attrs_bytes = bytearray(signed_attrs.dump())
    if attrs_bytes and attrs_bytes[0] in (0xA0, 0xA1):
        attrs_bytes[0] = 0x31
    signed_attrs_der = bytes(attrs_bytes)

    signature = bytes(signer_info["signature"].native)
    digest_algo_oid = signer_info["digest_algorithm"]["algorithm"].native
    sig_algo_oid = signer_info["signature_algorithm"]["algorithm"].native

    return ParsedTimestamp(
        policy_oid=tst_info["policy"].native or "",
        hash_algorithm=hash_algo,
        message_imprint=hashed,
        gen_time=gen_time,
        serial_number=int(tst_info["serial_number"].native),
        nonce=nonce,
        leaf_cert_der=leaf_cert_der,
        signed_attrs_der=signed_attrs_der,
        signature=signature,
        digest_algorithm_oid=digest_algo_oid,
        signature_algorithm_oid=sig_algo_oid,
    )


def verify_timestamp_token(
    parsed: ParsedTimestamp,
    *,
    expected_digest: bytes,
    trust_roots_der: list[bytes],
    verification_time: datetime | None = None,
) -> None:
    """Validate the parsed token against the expected message and trust roots.

    Raises :class:`AnchorVerificationError` on any failure.

    What this function checks:

    1. ``message_imprint`` matches ``expected_digest`` (32 bytes
       SHA-256).
    2. ``hash_algorithm`` is SHA-256.
    3. ``signature`` over ``signed_attrs_der`` verifies against the
       leaf cert's public key (RSA PKCS1v15 + SHA-256).
    4. The leaf cert chains to one of ``trust_roots_der`` (single hop;
       intermediate chains land in a future PR).
    5. ``verification_time`` (or now) is within the leaf cert's
       ``not_valid_before`` / ``not_valid_after`` window.

    What this function does NOT yet check:

    - OCSP / CRL freshness of the leaf cert.
    - Validity of the trust root itself (assumed by configuration).
    - Multi-hop intermediate chains (single-hop only in v1; suffices
      for our :class:`~attestplane.anchoring.testing.TestTSAAuthority`
      and most real TSAs).
    - eIDAS qualified-TSA list integration (eIDAS specific, deferred).
    """
    if len(expected_digest) != 32:
        raise AnchorVerificationError(
            f"expected_digest must be 32 bytes, got {len(expected_digest)}"
        )
    if parsed.hash_algorithm != "sha256":
        raise AnchorVerificationError(
            f"unexpected message-imprint hash algorithm: {parsed.hash_algorithm}"
        )
    if parsed.message_imprint != expected_digest:
        raise AnchorVerificationError(
            "message_imprint does not match expected digest"
        )

    # Load the leaf cert and verify the signature using cryptography.
    try:
        leaf = x509.load_der_x509_certificate(parsed.leaf_cert_der)
    except Exception as exc:
        raise AnchorVerificationError(f"leaf cert is not valid DER: {exc}") from exc

    public_key = leaf.public_key()
    if not isinstance(public_key, RSAPublicKey):
        raise AnchorVerificationError(
            f"v1 supports RSA leaf keys only; got {type(public_key).__name__}"
        )

    try:
        public_key.verify(
            parsed.signature,
            parsed.signed_attrs_der,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature as exc:
        raise AnchorVerificationError(
            "TSA signature does not verify against leaf cert"
        ) from exc

    # Check time validity.
    actual_when = verification_time or datetime.now(UTC)
    not_before = leaf.not_valid_before_utc
    not_after = leaf.not_valid_after_utc
    if actual_when < not_before:
        raise AnchorVerificationError(
            f"verification_time {actual_when} precedes leaf cert not_before {not_before}"
        )
    if actual_when > not_after:
        raise AnchorVerificationError(
            f"verification_time {actual_when} exceeds leaf cert not_after {not_after}"
        )

    # Check chain to trust root by issuer DN matching + signature.
    issuer_dn = leaf.issuer
    issuer_match = None
    for root_der in trust_roots_der:
        try:
            root = x509.load_der_x509_certificate(root_der)
        except Exception:
            continue
        if root.subject == issuer_dn:
            issuer_match = root
            break
    if issuer_match is None:
        raise AnchorVerificationError(
            "leaf cert issuer DN does not match any configured trust root"
        )

    root_key = issuer_match.public_key()
    if not isinstance(root_key, RSAPublicKey):
        raise AnchorVerificationError(
            f"v1 supports RSA root keys only; got {type(root_key).__name__}"
        )
    try:
        root_key.verify(
            leaf.signature,
            leaf.tbs_certificate_bytes,
            padding.PKCS1v15(),
            leaf.signature_hash_algorithm or hashes.SHA256(),
        )
    except InvalidSignature as exc:
        raise AnchorVerificationError(
            "leaf cert signature does not verify against the matched trust root"
        ) from exc


__all__ = [
    "ID_CT_TST_INFO_OID",
    "ParsedTimestamp",
    "parse_timestamp_response",
    "verify_timestamp_token",
]
