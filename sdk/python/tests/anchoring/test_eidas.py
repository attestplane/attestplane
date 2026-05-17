# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Tests for :mod:`attestplane.anchoring.eidas`.

Uses an in-tree synthetic Trusted List XML containing real X.509 certs
from TestTSAAuthority, so the loader's parsing is verified end-to-end
against actual certificate data without requiring a network fetch of a
real EU member-state Trusted List.
"""

from __future__ import annotations

from base64 import b64encode
from datetime import UTC, datetime

import pytest

pytest.importorskip("cryptography")
pytest.importorskip("asn1crypto")

from attestplane.anchoring.eidas import (
    ETSI_QTST_URI,
    ETSI_TSA_URI,
    TrustedListParseError,
    load_qualified_tsa_trust_roots,
    parse_trusted_list,
)
from attestplane.anchoring.testing import TestTSAAuthority

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _make_tl_xml(
    *,
    entries: list[tuple[str, str, str, bytes]],
) -> bytes:
    """Build a synthetic Trusted List XML containing the given (name, type, status, cert) entries."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<TrustServiceStatusList xmlns="http://uri.etsi.org/02231/v2#">',
        '<TrustServiceProviderList>',
        '<TrustServiceProvider>',
        '<TSPServices>',
    ]
    for name, service_type, status, cert_der in entries:
        b64 = b64encode(cert_der).decode("ascii")
        parts.append(f'''<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{service_type}</ServiceTypeIdentifier>
    <ServiceName>
      <Name xml:lang="en">{name}</Name>
    </ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId>
        <X509Certificate>{b64}</X509Certificate>
      </DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{status}</ServiceStatus>
  </ServiceInformation>
</TSPService>''')
    parts.extend([
        '</TSPServices>',
        '</TrustServiceProvider>',
        '</TrustServiceProviderList>',
        '</TrustServiceStatusList>',
    ])
    return "\n".join(parts).encode("utf-8")


def test_parse_extracts_qualified_tsa_certs() -> None:
    authority = TestTSAAuthority(now=_NOW)
    materials = authority.materials()
    xml = _make_tl_xml(entries=[
        ("Test QTSA", ETSI_QTST_URI,
         "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted",
         materials.root_cert_der),
    ])
    entries = parse_trusted_list(xml)
    assert len(entries) == 1
    e = entries[0]
    assert e.service_name == "Test QTSA"
    assert e.service_type == ETSI_QTST_URI
    assert "granted" in e.status
    assert e.cert_der == materials.root_cert_der


def test_parse_skips_non_tsa_services() -> None:
    authority = TestTSAAuthority(now=_NOW)
    materials = authority.materials()
    xml = _make_tl_xml(entries=[
        ("Test QTSA", ETSI_QTST_URI,
         "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted",
         materials.root_cert_der),
        ("Test CA",
         "http://uri.etsi.org/TrstSvc/Svctype/CA/QC",  # qualified cert CA, not TSA
         "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted",
         materials.root_cert_der),
    ])
    entries = parse_trusted_list(xml)
    assert len(entries) == 1
    assert entries[0].service_type == ETSI_QTST_URI


def test_parse_skips_withdrawn_status() -> None:
    authority = TestTSAAuthority(now=_NOW)
    materials = authority.materials()
    xml = _make_tl_xml(entries=[
        ("Withdrawn TSA", ETSI_QTST_URI,
         "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/withdrawn",
         materials.root_cert_der),
    ])
    entries = parse_trusted_list(xml)
    assert entries == []


def test_parse_includes_legacy_tsa_uri() -> None:
    """Pre-eIDAS TSA URI should also be accepted (legacy member-state TLs)."""
    authority = TestTSAAuthority(now=_NOW)
    materials = authority.materials()
    xml = _make_tl_xml(entries=[
        ("Legacy TSA", ETSI_TSA_URI,
         "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/undersupervision",
         materials.root_cert_der),
    ])
    entries = parse_trusted_list(xml)
    assert len(entries) == 1
    assert entries[0].service_type == ETSI_TSA_URI


def test_load_qualified_tsa_trust_roots_helper() -> None:
    authority_a = TestTSAAuthority(now=_NOW, common_name="A")
    authority_b = TestTSAAuthority(now=_NOW, common_name="B")
    xml = _make_tl_xml(entries=[
        ("A QTSA", ETSI_QTST_URI,
         "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted",
         authority_a.materials().root_cert_der),
        ("B QTSA", ETSI_QTST_URI,
         "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted",
         authority_b.materials().root_cert_der),
    ])
    roots = load_qualified_tsa_trust_roots(xml)
    assert len(roots) == 2
    assert authority_a.materials().root_cert_der in roots
    assert authority_b.materials().root_cert_der in roots


def test_malformed_xml_raises() -> None:
    with pytest.raises(TrustedListParseError, match="malformed"):
        parse_trusted_list(b"<not-xml-anywhere")


def test_empty_trusted_list_returns_empty() -> None:
    xml = (
        b'<?xml version="1.0"?>'
        b'<TrustServiceStatusList xmlns="http://uri.etsi.org/02231/v2#">'
        b'<TrustServiceProviderList></TrustServiceProviderList>'
        b'</TrustServiceStatusList>'
    )
    assert parse_trusted_list(xml) == []


def test_invalid_base64_cert_raises() -> None:
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<TrustServiceStatusList xmlns="http://uri.etsi.org/02231/v2#">\n'
        b'<TrustServiceProviderList>\n'
        b'<TrustServiceProvider>\n'
        b'<TSPServices>\n'
        b'<TSPService>\n'
        b'<ServiceInformation>\n'
        b'<ServiceTypeIdentifier>'
        + ETSI_QTST_URI.encode("ascii") + b'</ServiceTypeIdentifier>\n'
        b'<ServiceName><Name xml:lang="en">Bad</Name></ServiceName>\n'
        b'<ServiceDigitalIdentity>\n'
        b'<DigitalId>\n'
        b'<X509Certificate>***not-base64@@@</X509Certificate>\n'
        b'</DigitalId>\n'
        b'</ServiceDigitalIdentity>\n'
        b'<ServiceStatus>'
        b'http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted'
        b'</ServiceStatus>\n'
        b'</ServiceInformation>\n'
        b'</TSPService>\n'
        b'</TSPServices>\n'
        b'</TrustServiceProvider>\n'
        b'</TrustServiceProviderList>\n'
        b'</TrustServiceStatusList>\n'
    )
    with pytest.raises(TrustedListParseError, match="X509Certificate"):
        parse_trusted_list(xml)


def test_picks_english_service_name_when_multilingual() -> None:
    authority = TestTSAAuthority(now=_NOW)
    materials = authority.materials()
    b64 = b64encode(materials.root_cert_der).decode("ascii")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TrustServiceStatusList xmlns="http://uri.etsi.org/02231/v2#">\n'
        '<TrustServiceProviderList>\n'
        '<TrustServiceProvider>\n'
        '<TSPServices>\n'
        '<TSPService>\n'
        '<ServiceInformation>\n'
        f'<ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>\n'
        '<ServiceName>\n'
        '<Name xml:lang="de">Beispiel-Zeitstempel</Name>\n'
        '<Name xml:lang="en">Example Timestamp</Name>\n'
        '</ServiceName>\n'
        '<ServiceDigitalIdentity>\n'
        '<DigitalId>\n'
        f'<X509Certificate>{b64}</X509Certificate>\n'
        '</DigitalId>\n'
        '</ServiceDigitalIdentity>\n'
        '<ServiceStatus>'
        'http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted'
        '</ServiceStatus>\n'
        '</ServiceInformation>\n'
        '</TSPService>\n'
        '</TSPServices>\n'
        '</TrustServiceProvider>\n'
        '</TrustServiceProviderList>\n'
        '</TrustServiceStatusList>\n'
    ).encode()
    entries = parse_trusted_list(xml)
    assert len(entries) == 1
    assert entries[0].service_name == "Example Timestamp"
