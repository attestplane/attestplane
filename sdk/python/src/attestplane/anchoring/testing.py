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

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

# core is needed for OCSP construction; pulled below alongside other
# asn1crypto imports.

try:
    from typing import Literal

    from asn1crypto import algos, cms, core, tsp
    from asn1crypto import ocsp as asn1_ocsp  # noqa: F401  (conditional import — try/except guard)
    from asn1crypto import x509 as asn1_x509
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
    from cryptography.hazmat.primitives.asymmetric.rsa import (
        RSAPrivateKey,
        RSAPublicKey,  # noqa: F401  (conditional import — try/except guard)
    )
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "attestplane.anchoring.testing requires the 'anchor' extras. Install with: pip install attestplane[anchor]"
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
    """Bundled CA + leaf material exposed by :class:`TestTSAAuthority`.

    For multi-tier authorities, ``intermediate_certs_der`` contains the
    chain from leaf-issuer back to the cert just below the root, in
    that order (leaf's direct issuer first, root's direct child last).
    For the default 2-tier authority this tuple is empty.
    """

    root_cert_der: bytes
    leaf_cert_der: bytes
    leaf_key_der: bytes
    not_valid_before: datetime
    not_valid_after: datetime
    intermediate_certs_der: tuple[bytes, ...] = ()


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
        intermediate_count: int = 0,
        leaf_key_type: str = "rsa",
    ) -> None:
        if leaf_key_type not in ("rsa", "ec"):
            raise ValueError(f"leaf_key_type must be 'rsa' or 'ec', got {leaf_key_type!r}")
        actual_now = now or datetime.now(UTC)
        self._issued_at_authority = actual_now
        self._cert_validity = timedelta(days=cert_validity_days)
        self._root_validity = timedelta(days=cert_validity_days * 10)
        self._common_name = common_name
        self._leaf_key_type = leaf_key_type

        self._root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._root_cert = self._build_root_cert(self._root_key, actual_now)

        # Optional intermediate CA chain. Each intermediate is signed by
        # the previous tier (root → I1 → I2 → ...). The leaf cert is then
        # signed by the deepest intermediate. The two-tier default
        # (intermediate_count == 0) signs the leaf directly with the root.
        self._intermediate_keys: list[RSAPrivateKey] = []
        self._intermediate_certs: list[x509.Certificate] = []
        prev_key = self._root_key
        prev_cert = self._root_cert
        for tier in range(intermediate_count):
            inter_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            inter_cert = self._build_intermediate_cert(
                inter_key,
                prev_key,
                prev_cert,
                tier=tier,
                now=actual_now,
                path_length=intermediate_count - tier - 1,
            )
            self._intermediate_keys.append(inter_key)
            self._intermediate_certs.append(inter_cert)
            prev_key = inter_key
            prev_cert = inter_cert

        # Leaf key: either RSA-2048 (default, mirrors what most TSAs used
        # historically) or NIST P-256 EC (FreeTSA after its 2026 cert
        # rotation; many modern TSAs are migrating to EC for efficiency).
        self._leaf_key: RSAPrivateKey | EllipticCurvePrivateKey
        if leaf_key_type == "ec":
            self._leaf_key = ec.generate_private_key(ec.SECP256R1())
        else:
            self._leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._leaf_cert = self._build_leaf_cert(
            self._leaf_key,
            prev_key,
            prev_cert,
            actual_now,
        )

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
            intermediate_certs_der=tuple(c.public_bytes(serialization.Encoding.DER) for c in self._intermediate_certs),
        )

    def sign_timestamp_response(
        self,
        request_digest: bytes,
        *,
        gen_time: datetime,
        serial_number: int = 1,
        nonce: bytes | None = None,
        signer_digest_algorithm: Literal["sha256", "sha384", "sha512"] = "sha256",
    ) -> bytes:
        """Build a real RFC-3161 ``TimeStampResp`` DER blob.

        The response contains a ``TimeStampToken`` (CMS SignedData) whose
        ``eContentType`` is ``id-ct-TSTInfo``. The token is signed by the
        leaf cert's private key. The signature is real RSA-PKCS1v15 or
        ECDSA with the selected CMS signer digest. The TSTInfo
        messageImprint remains SHA-256 because Attestplane anchors
        SHA-256 chain heads.

        :param request_digest: 32-byte SHA-256 digest from the
            substrate.
        :param gen_time: the genTime to embed in the TSTInfo.
        :param serial_number: TSA-assigned serial; must be unique.
        :param nonce: optional nonce echoed from the request.
        :param signer_digest_algorithm: CMS SignerInfo digest used to
            sign ``signed_attrs``. Live TSAs may use SHA-512 while the
            messageImprint remains SHA-256.
        """
        if len(request_digest) != 32:
            raise ValueError("request_digest must be 32 bytes (SHA-256)")
        if gen_time.tzinfo is None or gen_time.utcoffset() != UTC.utcoffset(None):
            raise ValueError("gen_time must be UTC-aware")
        if signer_digest_algorithm not in {"sha256", "sha384", "sha512"}:
            raise ValueError("unsupported signer_digest_algorithm")

        tst_info = tsp.TSTInfo(
            {
                "version": "v1",
                "policy": "1.2.3.4.5",  # placeholder OID for the test authority
                "message_imprint": tsp.MessageImprint(
                    {
                        "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
                        "hashed_message": request_digest,
                    }
                ),
                "serial_number": serial_number,
                "gen_time": gen_time,
                **({"nonce": int.from_bytes(nonce, "big")} if nonce else {}),
            }
        )
        tst_info_der = tst_info.dump()

        # Build the CMS SignedData wrapping the TSTInfo.
        leaf_der = self._leaf_cert.public_bytes(serialization.Encoding.DER)
        leaf_asn1 = asn1_x509.Certificate.load(leaf_der)

        signed_attrs = cms.CMSAttributes(
            [
                cms.CMSAttribute(
                    {
                        "type": "content_type",
                        "values": [cms.ContentType("tst_info")],
                    }
                ),
                cms.CMSAttribute(
                    {
                        "type": "message_digest",
                        "values": [_digest(tst_info_der, signer_digest_algorithm)],
                    }
                ),
                cms.CMSAttribute(
                    {
                        "type": "signing_time",
                        "values": [cms.Time({"utc_time": gen_time})],
                    }
                ),
            ]
        )

        # Sign the DER encoding of the SET OF attributes (per CMS rules).
        signed_attrs_der = signed_attrs.dump()
        # CMS requires the signed attributes to be IMPLICIT-tagged in the
        # final SignerInfo but signed as a full SET. asn1crypto handles
        # this via SignedAttributes' DER serialisation:
        signed_bytes = bytearray(signed_attrs_der)
        signed_bytes[0] = 0x31  # SET tag (asn1crypto sometimes emits IMPLICIT)
        signer_hash = _hash_algorithm(signer_digest_algorithm)

        if isinstance(self._leaf_key, EllipticCurvePrivateKey):
            signature = self._leaf_key.sign(
                bytes(signed_bytes),
                ec.ECDSA(signer_hash),
            )
            sig_alg_name = f"{signer_digest_algorithm}_ecdsa"
        else:
            signature = self._leaf_key.sign(
                bytes(signed_bytes),
                padding.PKCS1v15(),
                signer_hash,
            )
            sig_alg_name = "rsassa_pkcs1v15"

        signer_info = cms.SignerInfo(
            {
                "version": "v1",
                "sid": cms.SignerIdentifier(
                    {
                        "issuer_and_serial_number": cms.IssuerAndSerialNumber(
                            {
                                "issuer": leaf_asn1.issuer,
                                "serial_number": leaf_asn1.serial_number,
                            }
                        ),
                    }
                ),
                "digest_algorithm": algos.DigestAlgorithm({"algorithm": signer_digest_algorithm}),
                "signed_attrs": signed_attrs,
                "signature_algorithm": algos.SignedDigestAlgorithm(
                    {
                        "algorithm": sig_alg_name,
                    }
                ),
                "signature": signature,
            }
        )

        signed_data = cms.SignedData(
            {
                "version": "v3",
                "digest_algorithms": [algos.DigestAlgorithm({"algorithm": signer_digest_algorithm})],
                "encap_content_info": cms.EncapsulatedContentInfo(
                    {
                        "content_type": "tst_info",
                        "content": core.ParsableOctetString(tst_info_der),
                    }
                ),
                "certificates": [cms.CertificateChoices({"certificate": leaf_asn1})],
                "signer_infos": [signer_info],
            }
        )

        token = cms.ContentInfo(
            {
                "content_type": "signed_data",
                "content": signed_data,
            }
        )

        timestamp_response = tsp.TimeStampResp(
            {
                "status": tsp.PKIStatusInfo({"status": "granted"}),
                "time_stamp_token": token,
            }
        )

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
        payload = b"ATTESTPLANE-TEST-OCSP-V1|" + gen_time.strftime("%Y%m%dT%H%M%SZ").encode("ascii") + b"|status=good"
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

        # The OCSP responder is the leaf's direct issuer per RFC-6960
        # § 2.6 (authorized-by-being-the-issuer mode). For the two-tier
        # default chain (root → leaf) this is the root; for a multi-tier
        # chain with intermediates the deepest intermediate signs.
        if self._intermediate_certs:
            issuer_cert = self._intermediate_certs[-1]
            issuer_key = self._intermediate_keys[-1]
        else:
            issuer_cert = self._root_cert
            issuer_key = self._root_key
        issuer_der = issuer_cert.public_bytes(serialization.Encoding.DER)
        issuer_asn1 = asn1_x509.Certificate.load(issuer_der)

        # Build the issuer-name-hash and issuer-key-hash that
        # OCSP CertID requires. Per RFC-6960, issuerKeyHash is the SHA-1
        # of the BIT STRING value of subjectPublicKey (the raw bits,
        # excluding tag + length + unused-bits prefix).
        issuer_name_hash = _sha1(issuer_asn1["tbs_certificate"]["subject"].dump())
        spki = issuer_asn1["tbs_certificate"]["subject_public_key_info"]
        # asn1crypto exposes the raw key bytes via .contents on the BIT STRING.
        # Strip the leading "unused bits" byte (always 0x00 for full octets).
        bit_string_bytes = spki["public_key"].contents
        if bit_string_bytes and bit_string_bytes[0] == 0:
            bit_string_bytes = bit_string_bytes[1:]
        issuer_key_hash = _sha1(bit_string_bytes)

        cert_id = asn1_ocsp.CertId(
            {
                "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha1"}),
                "issuer_name_hash": issuer_name_hash,
                "issuer_key_hash": issuer_key_hash,
                "serial_number": leaf_asn1.serial_number,
            }
        )

        if revoked:
            cert_status = asn1_ocsp.CertStatus(
                {
                    "revoked": asn1_ocsp.RevokedInfo(
                        {
                            "revocation_time": gen_time,
                            "revocation_reason": "unspecified",
                        }
                    ),
                }
            )
        else:
            cert_status = asn1_ocsp.CertStatus({"good": core.Null()})

        single_response = asn1_ocsp.SingleResponse(
            {
                "cert_id": cert_id,
                "cert_status": cert_status,
                "this_update": gen_time,
                "next_update": actual_next,
            }
        )

        tbs = asn1_ocsp.ResponseData(
            {
                "responder_id": asn1_ocsp.ResponderId(
                    name="by_name",
                    value=issuer_asn1["tbs_certificate"]["subject"],
                ),
                "produced_at": gen_time,
                "responses": [single_response],
            }
        )
        tbs_der = tbs.dump()
        signature = issuer_key.sign(
            tbs_der,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

        basic_response = asn1_ocsp.BasicOCSPResponse(
            {
                "tbs_response_data": tbs,
                "signature_algorithm": algos.SignedDigestAlgorithm(
                    {
                        "algorithm": "rsassa_pkcs1v15",
                    }
                ),
                "signature": signature,
            }
        )

        full = asn1_ocsp.OCSPResponse(
            {
                "response_status": "successful",
                "response_bytes": asn1_ocsp.ResponseBytes(
                    {
                        "response_type": "basic_ocsp_response",
                        "response": core.ParsableOctetString(basic_response.dump()),
                    }
                ),
            }
        )
        der_bytes: bytes = full.dump()
        return der_bytes

    # --- Internal cert construction ---

    def _build_root_cert(self, key: RSAPrivateKey, now: datetime) -> x509.Certificate:
        name = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, "Attestplane Test Root CA"),
            ]
        )
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

    def _build_intermediate_cert(
        self,
        inter_key: RSAPrivateKey,
        signer_key: RSAPrivateKey,
        signer_cert: x509.Certificate,
        *,
        tier: int,
        now: datetime,
        path_length: int,
    ) -> x509.Certificate:
        name = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, f"Attestplane Test Intermediate CA T{tier}"),
            ]
        )
        builder = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(signer_cert.subject)
            .public_key(inter_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            # Intermediate validity is between leaf and root: longer than
            # leaf, shorter than root.
            .not_valid_after(now + self._cert_validity * 5)
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=path_length),
                critical=True,
            )
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
        return builder.sign(signer_key, hashes.SHA256())

    def _build_leaf_cert(
        self,
        leaf_key: RSAPrivateKey | EllipticCurvePrivateKey,
        signer_key: RSAPrivateKey,
        signer_cert: x509.Certificate,
        now: datetime,
    ) -> x509.Certificate:
        leaf_name = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, self._common_name),
            ]
        )
        builder = (
            x509.CertificateBuilder()
            .subject_name(leaf_name)
            .issuer_name(signer_cert.subject)
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
        return builder.sign(signer_key, hashes.SHA256())


def _sha256(data: bytes) -> bytes:
    from hashlib import sha256

    digest: bytes = sha256(data).digest()
    return digest


def _digest(data: bytes, algorithm: str) -> bytes:
    from hashlib import sha256, sha384, sha512

    if algorithm == "sha256":
        digest: bytes = sha256(data).digest()
        return digest
    if algorithm == "sha384":
        digest = sha384(data).digest()
        return digest
    if algorithm == "sha512":
        digest = sha512(data).digest()
        return digest
    raise ValueError(f"unsupported digest algorithm: {algorithm}")


def _hash_algorithm(algorithm: str) -> hashes.HashAlgorithm:
    if algorithm == "sha256":
        return hashes.SHA256()
    if algorithm == "sha384":
        return hashes.SHA384()
    if algorithm == "sha512":
        return hashes.SHA512()
    raise ValueError(f"unsupported digest algorithm: {algorithm}")


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


class TestRekorAuthority:
    """In-process synthetic Rekor log for tests.

    Generates a fresh Ed25519 keypair to represent the Rekor log's
    signing key, then issues real signed LogEntry responses matching
    the public Sigstore Rekor v1 shape (subset). Used by the
    Sigstore anchor's tests and as a building block for the
    nightly-Rekor CI workflow.

    Pure in-process; no network. Submitted entry bodies are signed
    by the authority's log key over the canonical SET payload defined
    in :mod:`attestplane.anchoring.sigstore`.
    """

    __test__ = False

    def __init__(
        self,
        *,
        log_id: str = "attestplane.test.rekor",
        now: datetime | None = None,
    ) -> None:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        self._log_id = log_id
        self._log_key = Ed25519PrivateKey.generate()
        self._index = 0
        self._fixed_time = now

    @property
    def log_id(self) -> str:
        return self._log_id

    @property
    def public_key(self) -> Any:
        return self._log_key.public_key()

    @property
    def public_key_der(self) -> bytes:
        return self._log_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def issue_log_entry(
        self,
        body_bytes: bytes,
        *,
        now: datetime | None = None,
    ) -> bytes:
        """Issue a synthetic Rekor LogEntry JSON for the given body.

        :param body_bytes: the entry body bytes (canonical JSON of the
            spec); same bytes the substrate's SigstoreRekorAnchor
            produces.
        :param now: integratedTime; defaults to constructor fixed_time
            or wall-clock UTC.
        :returns: JSON-encoded LogEntry bytes, ready to be embedded in
            an :class:`AnchorRecord.tsa_token`.
        """
        import base64
        import json

        actual_now = now or self._fixed_time or datetime.now(UTC)
        integrated_time = int(actual_now.timestamp())
        self._index += 1

        # Build the SET payload and sign it.
        set_payload = {
            "body": base64.standard_b64encode(body_bytes).decode("ascii"),
            "integratedTime": integrated_time,
            "logID": self._log_id,
            "logIndex": self._index,
        }
        set_payload_bytes = json.dumps(set_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        set_signature = self._log_key.sign(set_payload_bytes)

        log_entry = {
            "logIndex": self._index,
            "logID": self._log_id,
            "integratedTime": integrated_time,
            "body": base64.standard_b64encode(body_bytes).decode("ascii"),
            "verification": {
                "signedEntryTimestamp": base64.standard_b64encode(set_signature).decode("ascii"),
            },
        }
        return json.dumps(log_entry, sort_keys=True, separators=(",", ":")).encode("utf-8")


__all__ = [
    "TestRekorAuthority",
    "TestTSAAuthority",
    "TestTSAMaterials",
    "TestTSAProvider",
]
