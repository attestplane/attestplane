# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""eIDAS qualified-TSA Trusted List integration.

The European Union maintains a "List of Trusted Lists" (LOTL) per
ETSI TS 119 612, signed by the EU Commission. Each member state
publishes its own Trusted List of Trust Service Providers (TSPs),
including qualified Time-Stamping Authorities (qTSAs).

Attestplane v1 ships a **minimal pragmatic loader**:

- Parse an ETSI TS 119 612-shaped Trusted List XML.
- Extract X.509 service-digital-identities (i.e., TSP certs) for
  services whose service type is the qualified-time-stamping URI
  (``http://uri.etsi.org/TrstSvc/Svctype/TSA/QTST``).
- Return the certs as DER bytes, ready to pass as ``trust_roots_der``
  to :func:`~attestplane.anchoring.verify_chain_with_anchors`.

v1 does NOT do:

- Verify the Trusted List's XML signature (caller is expected to
  fetch over HTTPS from a trusted source and validate the signing key
  out-of-band, OR to trust the bundled snapshot).
- Walk the LOTL → member state TL hierarchy (each member-state TL is
  loaded individually by the caller).
- Discriminate qualified-vs-non-qualified status changes over time
  (only "granted" status is loaded).

These are documented gaps; production callers needing eIDAS
qualified-TSA validity guarantees should pair this loader with
out-of-band trust establishment for the LOTL signing key.
"""

from __future__ import annotations

import re
from base64 import b64decode
from dataclasses import dataclass
from typing import Final
from xml.etree import ElementTree as ET

TSL_NS: Final[str] = "http://uri.etsi.org/02231/v2#"
ETSI_QTST_URI: Final[str] = "http://uri.etsi.org/TrstSvc/Svctype/TSA/QTST"
ETSI_TSA_URI: Final[str] = "http://uri.etsi.org/TrstSvc/Svctype/TSA"


@dataclass(frozen=True, slots=True)
class QualifiedTsaEntry:
    """One qualified TSA service entry extracted from a Trusted List."""

    service_name: str
    service_type: str
    """Either ``ETSI_QTST_URI`` (post-eIDAS) or ``ETSI_TSA_URI`` (legacy)."""
    status: str
    cert_der: bytes


class EidasError(Exception):
    """Base class for eIDAS Trusted List loader errors."""


class TrustedListParseError(EidasError):
    """The Trusted List XML could not be parsed."""


def _strip_ws(text: str) -> str:
    return re.sub(r"\s+", "", text)


def parse_trusted_list(xml_bytes: bytes) -> list[QualifiedTsaEntry]:
    """Parse a single ETSI TS 119 612 Trusted List XML blob.

    Returns the qualified-TSA service entries (granted status only).
    Non-TSA services are silently skipped.

    Raises :class:`TrustedListParseError` on malformed XML.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise TrustedListParseError(f"Trusted List XML is malformed: {exc}") from exc

    # The root element is <TrustServiceStatusList> in TSL namespace.
    # Walk to /TrustServiceProviderList/TrustServiceProvider/TSPServices/
    # /TSPService/ServiceInformation
    entries: list[QualifiedTsaEntry] = []
    for tsp_service in root.iter(f"{{{TSL_NS}}}TSPService"):
        service_info = tsp_service.find(f"{{{TSL_NS}}}ServiceInformation")
        if service_info is None:
            continue
        type_elem = service_info.find(f"{{{TSL_NS}}}ServiceTypeIdentifier")
        if type_elem is None or type_elem.text is None:
            continue
        service_type = type_elem.text.strip()
        if service_type not in (ETSI_QTST_URI, ETSI_TSA_URI):
            continue

        status_elem = service_info.find(f"{{{TSL_NS}}}ServiceStatus")
        status = status_elem.text.strip() if status_elem is not None and status_elem.text else ""
        # Only "granted" / "undersupervision" services are operational.
        # Reject "withdrawn", "expired", etc.
        if "granted" not in status and "undersupervision" not in status:
            continue

        name_elem = service_info.find(f"{{{TSL_NS}}}ServiceName")
        service_name = ""
        if name_elem is not None:
            # ServiceName contains <Name> children — take the first one
            # with an English locale, or the first overall.
            for name_child in name_elem.findall(f"{{{TSL_NS}}}Name"):
                if name_child.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "").startswith("en"):
                    service_name = (name_child.text or "").strip()
                    break
            if not service_name:
                first = name_elem.find(f"{{{TSL_NS}}}Name")
                if first is not None and first.text is not None:
                    service_name = first.text.strip()

        # Extract the digital identity certs.
        identity = service_info.find(f"{{{TSL_NS}}}ServiceDigitalIdentity")
        if identity is None:
            continue
        for digital_id in identity.findall(f"{{{TSL_NS}}}DigitalId"):
            cert_elem = digital_id.find(f"{{{TSL_NS}}}X509Certificate")
            if cert_elem is None or cert_elem.text is None:
                continue
            b64_text = _strip_ws(cert_elem.text)
            try:
                cert_der = b64decode(b64_text)
            except Exception as exc:
                raise TrustedListParseError(
                    f"failed to decode X509Certificate base64 for service {service_name!r}: {exc}"
                ) from exc
            entries.append(
                QualifiedTsaEntry(
                    service_name=service_name,
                    service_type=service_type,
                    status=status,
                    cert_der=cert_der,
                )
            )

    return entries


def load_qualified_tsa_trust_roots(xml_bytes: bytes) -> list[bytes]:
    """Convenience: parse a Trusted List and return DER bytes only.

    Equivalent to ``[e.cert_der for e in parse_trusted_list(xml_bytes)]``,
    suitable to feed directly into
    :func:`~attestplane.anchoring.verify_chain_with_anchors` as the
    ``trust_roots_der`` argument.
    """
    return [e.cert_der for e in parse_trusted_list(xml_bytes)]


__all__ = [
    "ETSI_QTST_URI",
    "ETSI_TSA_URI",
    "EidasError",
    "QualifiedTsaEntry",
    "TrustedListParseError",
    "load_qualified_tsa_trust_roots",
    "parse_trusted_list",
]
