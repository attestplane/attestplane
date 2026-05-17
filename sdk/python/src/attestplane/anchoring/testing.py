# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""In-process TSA authority for tests and self-contained demos.

:class:`TestTSAAuthority` uses ``cryptography`` to generate a self-
signed root CA, a TSA leaf certificate with the ``TimeStamping``
extended-key-usage, and produce **real** RFC-3161 ``TimeStampResp``
DER bytes that the production verifier path parses byte-for-byte the
same as a response from FreeTSA / DigiCert.

The authority is intentionally **not** wired to any network. It is a
local oracle for tests and for downstream users who want to integrate
the anchorer worker into their own test suites without standing up a
live TSA.

This module imports ``cryptography`` and ``asn1crypto``, which are
optional dependencies; install with ``pip install attestplane[anchor]``.
Importing this module without those installed raises a clear
``ImportError`` at import time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

# core is needed for OCSP construction; pulled below alongside other
# asn1crypto imports.

try:
    from asn1crypto import algos, cms, core, ocsp as asn1_ocsp, tsp, x509 as asn1_x509
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.asymmetric.rsa import (
        RSAPrivateKey,
        RSAPublicKey,
    )
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    from typing import Literal
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attestplane.anchoring.testing requires the 'anchor' extras. "
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


@dataclass(frozen=True)
class TestTSAMaterials:
    """Bundled CA + leaf material exposed by :class:`TestTSAAuthority`."""

    root_cert_der: bytes
    leaf_cert_der: bytes
    leaf_key_der: bytes
    not_valid_before: datetime
    not_valid_after: datetime


class TestTSAAuthority:
    # Tell pytest not to collect this class as a test (the "Test" prefix
    # would otherwise trigger collection-warning noise).
    __test__ = False

    """Self-signed TSA suitable for tests.

    :param now: clock source; defaults to ``datetime.now(UTC)``. Tests
        inject a fixed value for reproducibility.
    :param cert_validity_days: validity window for the leaf cert. The
        root CA is valid 10x as long.
    :param common_name: CN for the leaf cert; embedded in the issued
        anchor's ``tsa_provider_id`` by :class:`TestTSAProvider`.
    """

    def __init__(
        self,
        *,
        now: datetime | None = None,
        cert_validity_days: int = 365,
        common_name: str = "Attestplane Test TSA",
    ) -> None:
        actual_now = now or datetime.now(UTC)
        self._issued_at_authority = actual_now
        self._cert_validity = timedelta(days=cert_validity_days)
        self._root_validity = timedelta(days=cert_validity_days * 10)
        self._common_name = common_name

        self._root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._root_cert = self._build_root_cert(self._root_key, actual_now)

        self._leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._leaf_cert = self._build_leaf_cert(self._leaf_key, actual_now)

    @property
    def common_name(self) -> str:
        return self._common_name

    def materials(self) -> TestTSAMaterials:
        return TestTSAMaterials(
            root_cert_der=self._root_cert.public_bytes(serialization.Encoding.DER),
            leaf_cert_der=self._leaf_cert.public_bytes(serialization.Encoding.DER),
            leaf_key_der=self._leaf_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ),
            not_valid_before=self._leaf_cert.not_valid_before_utc,
            not_valid_after=self._leaf_cert.not_valid_after_utc,
        )

    def sign_timestamp_response(
        self,
        request_digest: bytes,
        *,
        gen_time: datetime,
        serial_number: int = 1,
        nonce: bytes | None = None,
    ) -> bytes:
        """Build a real RFC-3161 ``TimeStampResp`` DER blob.

        The response contains a ``TimeStampToken`` (CMS SignedData) whose
        ``eContentType`` is ``id-ct-TSTInfo``. The token is signed by the
        leaf cert's private key. The signature is real RSA-PKCS1v15 with
        SHA-256.

        :param request_digest: 32-byte SHA-256 digest from the
            substrate.
        :param gen_time: the genTime to embed in the TSTInfo.
        :param serial_number: TSA-assigned serial; must be unique.
        :param nonce: optional nonce echoed from the request.
        """
        if len(request_digest) != 32:
            raise ValueError("request_digest must be 32 bytes (SHA-256)")
        if gen_time.tzinfo is None or gen_time.utcoffset() != UTC.utcoffset(None):
            raise ValueError("gen_time must be UTC-aware")

        tst_info = tsp.TSTInfo({
            "version": "v1",
            "policy": "1.2.3.4.5",  # placeholder OID for the test authority
            "message_imprint": tsp.MessageImprint({
                "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
                "hashed_message": request_digest,
            }),
            "serial_number": serial_number,
            "gen_time": gen_time,
            **({"nonce": int.from_bytes(nonce, "big")} if nonce else {}),
        })
        tst_info_der = tst_info.dump()

        # Build the CMS SignedData wrapping the TSTInfo.
        leaf_der = self._leaf_cert.public_bytes(serialization.Encoding.DER)
        leaf_asn1 = asn1_x509.Certificate.load(leaf_der)

        signed_attrs = cms.CMSAttributes([
            cms.CMSAttribute({
                "type": "content_type",
                "values": [cms.ContentType("tst_info")],
            }),
            cms.CMSAttribute({
                "type": "message_digest",
                "values": [_sha256(tst_info_der)],
            }),
            cms.CMSAttribute({
                "type": "signing_time",
                "values": [cms.Time({"utc_time": gen_time})],
            }),
        ])

        # Sign the DER encoding of the SET OF attributes (per CMS rules).
        signed_attrs_der = signed_attrs.dump()
        # CMS requires the signed attributes to be IMPLICIT-tagged in the
        # final SignerInfo but signed as a full SET. asn1crypto handles
        # this via SignedAttributes' DER serialisation:
        signed_bytes = bytearray(signed_attrs_der)
        signed_bytes[0] = 0x31  # SET tag (asn1crypto sometimes emits IMPLICIT)

        signature = self._leaf_key.sign(
            bytes(signed_bytes),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

        signer_info = cms.SignerInfo({
            "version": "v1",
            "sid": cms.SignerIdentifier({
                "issuer_and_serial_number": cms.IssuerAndSerialNumber({
                    "issuer": leaf_asn1.issuer,
                    "serial_number": leaf_asn1.serial_number,
                }),
            }),
            "digest_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
            "signed_attrs": signed_attrs,
            "signature_algorithm": algos.SignedDigestAlgorithm({
                "algorithm": "rsassa_pkcs1v15",
            }),
            "signature": signature,
        })

        signed_data = cms.SignedData({
            "version": "v3",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": cms.EncapsulatedContentInfo({
                "content_type": "tst_info",
                "content": core.ParsableOctetString(tst_info_der),
            }),
            "certificates": [cms.CertificateChoices({"certificate": leaf_asn1})],
            "signer_infos": [signer_info],
        })

        token = cms.ContentInfo({
            "content_type": "signed_data",
            "content": signed_data,
        })

        timestamp_response = tsp.TimeStampResp({
            "status": tsp.PKIStatusInfo({"status": "granted"}),
            "time_stamp_token": token,
        })

        der_bytes: bytes = timestamp_response.dump()
        return der_bytes

    def issue_ocsp_response(self, *, gen_time: datetime) -> bytes:
        """Issue a placeholder OCSP response (v0.0.1-alpha behaviour).

        Returns a deterministic synthetic byte sequence. The verifier's
        OCSP-validation path recognises this marker and rejects it.

        Production callers should use :meth:`issue_real_ocsp_response`
        instead — that variant produces a real RFC-6960 OCSPResponse
        signed by the root CA.
        """
        if gen_time.tzinfo is None:
            raise ValueError("gen_time must be UTC-aware")
        payload = (
            b"ATTESTPLANE-TEST-OCSP-V1|"
            + gen_time.strftime("%Y%m%dT%H%M%SZ").encode("ascii")
            + b"|status=good"
        )
        return payload

    def issue_real_ocsp_response(
        self,
        *,
        gen_time: datetime,
        next_update: datetime | None = None,
        revoked: bool = False,
    ) -> bytes:
        """Issue a real RFC-6960 OCSPResponse for the leaf cert.

        Signs the response with the root CA key (issuer-signed OCSP
        mode). The response covers exactly one cert: the TSA leaf cert
        produced by this authority.

        :param gen_time: ``produced_at`` and ``this_update`` value.
        :param next_update: ``next_update`` value; defaults to
            ``gen_time + 7 days``.
        :param revoked: if True, returns a "revoked" status (useful for
            tests asserting the verifier rejects revoked anchors).
        """
        if gen_time.tzinfo is None:
            raise ValueError("gen_time must be UTC-aware")

        from asn1crypto import ocsp as asn1_ocsp

        actual_next = next_update if next_update is not None else gen_time + timedelta(days=7)

        leaf_der = self._leaf_cert.public_bytes(serialization.Encoding.DER)
        leaf_asn1 = asn1_x509.Certificate.load(leaf_der)
        root_der = self._root_cert.public_bytes(serialization.Encoding.DER)
        root_asn1 = asn1_x509.Certificate.load(root_der)

        # Build the issuer-name-hash and issuer-key-hash that
        # OCSP CertID requires. Per RFC-6960, issuerKeyHash is the SHA-1
        # of the BIT STRING value of subjectPublicKey (the raw bits,
        # excluding tag + length + unused-bits prefix).
        issuer_name_hash = _sha1(root_asn1["tbs_certificate"]["subject"].dump())
        spki = root_asn1["tbs_certificate"]["subject_public_key_info"]
        # asn1crypto exposes the raw key bytes via .contents on the BIT STRING.
        # Strip the leading "unused bits" byte (always 0x00 for full octets).
        bit_string_bytes = spki["public_key"].contents
        if bit_string_bytes and bit_string_bytes[0] == 0:
            bit_string_bytes = bit_string_bytes[1:]
        issuer_key_hash = _sha1(bit_string_bytes)

        cert_id = asn1_ocsp.CertId({
            "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha1"}),
            "issuer_name_hash": issuer_name_hash,
            "issuer_key_hash": issuer_key_hash,
            "serial_number": leaf_asn1.serial_number,
        })

        if revoked:
            cert_status = asn1_ocsp.CertStatus({
                "revoked": asn1_ocsp.RevokedInfo({
                    "revocation_time": gen_time,
                    "revocation_reason": "unspecified",
                }),
            })
        else:
            cert_status = asn1_ocsp.CertStatus({"good": core.Null()})

        single_response = asn1_ocsp.SingleResponse({
            "cert_id": cert_id,
            "cert_status": cert_status,
            "this_update": gen_time,
            "next_update": actual_next,
        })

        tbs = asn1_ocsp.ResponseData({
            "responder_id": asn1_ocsp.ResponderId(
                name="by_name", value=root_asn1["tbs_certificate"]["subject"],
            ),
            "produced_at": gen_time,
            "responses": [single_response],
        })
        tbs_der = tbs.dump()
        signature = self._root_key.sign(
            tbs_der, padding.PKCS1v15(), hashes.SHA256(),
        )

        basic_response = asn1_ocsp.BasicOCSPResponse({
            "tbs_response_data": tbs,
            "signature_algorithm": algos.SignedDigestAlgorithm({
                "algorithm": "rsassa_pkcs1v15",
            }),
            "signature": signature,
        })

        full = asn1_ocsp.OCSPResponse({
            "response_status": "successful",
            "response_bytes": asn1_ocsp.ResponseBytes({
                "response_type": "basic_ocsp_response",
                "response": core.ParsableOctetString(basic_response.dump()),
            }),
        })
        der_bytes: bytes = full.dump()
        return der_bytes

    # --- Internal cert construction ---

    def _build_root_cert(self, key: RSAPrivateKey, now: datetime) -> x509.Certificate:
        name = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Attestplane Test Root CA"),
        ])
        builder = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + self._root_validity)
            .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
        )
        return builder.sign(key, hashes.SHA256())

    def _build_leaf_cert(self, leaf_key: RSAPrivateKey, now: datetime) -> x509.Certificate:
        leaf_name = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, self._common_name),
        ])
        root_subject = self._root_cert.subject
        builder = (
            x509.CertificateBuilder()
            .subject_name(leaf_name)
            .issuer_name(root_subject)
            .public_key(leaf_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + self._cert_validity)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=True,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]),
                critical=True,
            )
        )
        return builder.sign(self._root_key, hashes.SHA256())


def _sha256(data: bytes) -> bytes:
    from hashlib import sha256
    digest: bytes = sha256(data).digest()
    return digest


def _sha1(data: bytes) -> bytes:
    from hashlib import sha1
    digest: bytes = sha1(data).digest()
    return digest


class TestTSAProvider(TSAProvider):
    __test__ = False

    """Synchronous in-process provider backed by :class:`TestTSAAuthority`.

    This is the production-shape provider you use in tests when the
    :class:`MockTSAProvider` (synthetic bytes) is too weak. The
    TestTSAProvider returns AnchorRecords with **real**
    RFC-3161-conformant ``tsa_token`` bytes that
    :func:`~attestplane.anchoring.rfc3161.parse_timestamp_response`
    can verify with the actual leaf cert.
    """

    schema_version = ANCHOR_SCHEMA_VERSION

    def __init__(
        self,
        authority: TestTSAAuthority,
        *,
        fail_with: Exception | None = None,
        ocsp_mode: Literal["legacy_synthetic", "real"] = "real",
    ) -> None:
        self._authority = authority
        self._fail_with = fail_with
        self._serial = 1
        self._ocsp_mode = ocsp_mode
        self.provider_id = f"test.tsa:{authority.common_name}"

    def request_timestamp(
        self,
        request: TimestampRequest,
        *,
        anchored_seq: int = 0,
        now: datetime | None = None,
    ) -> AnchorRecord:
        if self._fail_with is not None:
            raise self._fail_with
        if request.nonce is not None and len(request.nonce) == 0:
            raise AnchorVerificationError("nonce must be non-empty when provided")
        gen_time = (now or datetime.now(UTC)).replace(microsecond=0)
        if gen_time.tzinfo is None:
            raise TSAUnavailableError("TestTSAProvider requires UTC-aware datetime")
        token_der = self._authority.sign_timestamp_response(
            request.digest,
            gen_time=gen_time,
            serial_number=self._serial,
            nonce=request.nonce,
        )
        self._serial += 1
        materials = self._authority.materials()
        if self._ocsp_mode == "real":
            ocsp = self._authority.issue_real_ocsp_response(gen_time=gen_time)
        else:
            ocsp = self._authority.issue_ocsp_response(gen_time=gen_time)
        return AnchorRecord(
            anchor_schema_version=ANCHOR_SCHEMA_VERSION,
            anchored_seq=anchored_seq,
            anchored_event_hash=request.digest,
            tsa_provider_id=self.provider_id,
            tsa_token=token_der,
            tsa_cert_chain=(materials.leaf_cert_der, materials.root_cert_der),
            ocsp_responses=(ocsp,),
            issued_at_claimed=gen_time,
        )


__all__ = [
    "TestTSAAuthority",
    "TestTSAMaterials",
    "TestTSAProvider",
]
