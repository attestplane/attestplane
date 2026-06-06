# SPDX-FileCopyrightText: 2026 Attestplane Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coverage-completion tests for attestplane.anchoring.eidas.

Targets the uncovered lines:
  90  — TSPService without ServiceInformation -> continue
  93  — ServiceTypeIdentifier missing/null -> continue
 107->120 — name_elem is None -> no service_name extraction -> identity lookup
 110->114 — no English Name in loop, but English check skips to fallback
 115-117  — first non-English Name used as fallback
 122  — ServiceDigitalIdentity is None -> continue
 126  — DigitalId without X509Certificate (or empty text) -> continue
"""

from __future__ import annotations

from base64 import b64encode
from datetime import UTC, datetime

import pytest

from attestplane.anchoring.base import ANCHOR_SCHEMA_VERSION, AnchorRecord
from attestplane.anchoring.eidas import (
    ETSI_QTST_URI,
    ETSI_TSA_URI,
    TSL_NS,
    TrustedListParseError,
    load_qualified_tsa_trust_roots,
    parse_trusted_list,
)
from attestplane.anchoring.testing import TestTSAAuthority
from attestplane.anchoring.verifier import verify_chain_with_anchors
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import ChainHead, EventDraft

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)

_GRANTED = "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted"
_FAKE_CERT_DER = b"\x30\x82\x01\x00" + b"\x00" * 252  # 256-byte synthetic "cert"


def _xml(*service_blocks: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<TrustServiceStatusList xmlns="{TSL_NS}">\n'
        "<TrustServiceProviderList>\n"
        "<TrustServiceProvider>\n"
        "<TSPServices>\n"
        + "".join(service_blocks)
        + "</TSPServices>\n"
        "</TrustServiceProvider>\n"
        "</TrustServiceProviderList>\n"
        "</TrustServiceStatusList>\n"
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# eidas.py line 90 — TSPService with no ServiceInformation -> continue
# ---------------------------------------------------------------------------


def test_parse_tspservice_without_service_information_is_skipped() -> None:
    """eidas.py line 90 — TSPService element with no ServiceInformation child is silently skipped."""
    xml = _xml(
        # Service with no ServiceInformation at all
        "<TSPService/>\n",
        # And a valid service to confirm the loop continues
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">Valid TSA</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    # The empty TSPService is skipped; the valid one is parsed.
    assert len(entries) == 1
    assert entries[0].service_name == "Valid TSA"


# ---------------------------------------------------------------------------
# eidas.py line 93 — ServiceTypeIdentifier missing -> continue
# ---------------------------------------------------------------------------


def test_parse_service_without_type_identifier_is_skipped() -> None:
    """eidas.py line 93 — ServiceInformation with no ServiceTypeIdentifier is silently skipped."""
    xml = _xml(
        # ServiceInformation present but no ServiceTypeIdentifier
        f"""<TSPService>
  <ServiceInformation>
    <ServiceName><Name xml:lang="en">No Type TSA</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert entries == []


def test_parse_service_with_empty_type_identifier_text_is_skipped() -> None:
    """eidas.py line 93 — ServiceTypeIdentifier with no text -> type_elem.text is None -> continue."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier/>
    <ServiceName><Name xml:lang="en">Empty Type TSA</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert entries == []


# ---------------------------------------------------------------------------
# eidas.py 107->120 — name_elem is None -> service_name="" (no extraction), continues to identity
# ---------------------------------------------------------------------------


def test_parse_service_without_service_name_element() -> None:
    """eidas.py 107->120 — ServiceName element absent -> service_name='', still extracts certs."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <!-- No ServiceName element -->
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert len(entries) == 1
    assert entries[0].service_name == ""


# ---------------------------------------------------------------------------
# eidas.py 110->114 + 115-117 — no English Name -> fallback to first Name child
# ---------------------------------------------------------------------------


def test_parse_service_no_english_name_uses_first_name() -> None:
    """eidas.py 115-117 — no English lang Name -> fall back to first Name child's text."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName>
      <Name xml:lang="de">Deutscher Zeitstempel</Name>
      <Name xml:lang="fr">Horodatage</Name>
    </ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert len(entries) == 1
    # No English name -> fallback to first child = German name
    assert entries[0].service_name == "Deutscher Zeitstempel"


def test_parse_service_name_elem_has_no_children() -> None:
    """eidas.py 115 — name_elem present but no Name children -> first=None -> service_name=''."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName/>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert len(entries) == 1
    assert entries[0].service_name == ""


def test_parse_service_first_name_child_has_no_text() -> None:
    """eidas.py 116 — first Name child exists but has no text -> service_name stays ''."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName>
      <Name xml:lang="de"/>
    </ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert len(entries) == 1
    assert entries[0].service_name == ""


# ---------------------------------------------------------------------------
# eidas.py line 122 — ServiceDigitalIdentity is None -> continue
# ---------------------------------------------------------------------------


def test_parse_service_without_digital_identity_is_skipped() -> None:
    """eidas.py line 122 — no ServiceDigitalIdentity element -> service produces no entries."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">No Identity TSA</Name></ServiceName>
    <!-- No ServiceDigitalIdentity -->
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert entries == []


# ---------------------------------------------------------------------------
# eidas.py line 126 — DigitalId without X509Certificate -> continue
# ---------------------------------------------------------------------------


def test_parse_digital_id_without_x509certificate_is_skipped() -> None:
    """eidas.py line 126 — DigitalId present but no X509Certificate child -> skipped."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">SubjectKeyId TSA</Name></ServiceName>
    <ServiceDigitalIdentity>
      <!-- DigitalId with only SubjectKeyId, not X509Certificate -->
      <DigitalId><SubjectKeyId>AAAA</SubjectKeyId></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert entries == []


def test_parse_digital_id_with_empty_x509certificate_is_skipped() -> None:
    """eidas.py line 126 — X509Certificate element present but text is None/empty -> continue."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">Empty Cert TSA</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate/></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert entries == []


# ---------------------------------------------------------------------------
# Mixed: service with some valid DigitalIds and some skippable ones
# ---------------------------------------------------------------------------


def test_parse_mixed_digital_ids_only_certs_extracted() -> None:
    """A service with one skippable DigitalId and one valid X509Certificate."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">Mixed TSA</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><SubjectKeyId>ignored</SubjectKeyId></DigitalId>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert len(entries) == 1
    assert entries[0].cert_der == _FAKE_CERT_DER


# ---------------------------------------------------------------------------
# Verify branch: verifier.py 335->371 (OCSP module is None, skip OCSP check)
# This happens when verify_ocsp=False and _ocsp_mod is None.
# The branch goes from line 335 (if _ocsp_mod is not None and ...) -> 371 (if ocsp_failure)
# When _ocsp_mod is None the OCSP block is skipped entirely -> ocsp_status="good" -> verified.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# eidas.py lines 80-81 — malformed XML -> TrustedListParseError
# ---------------------------------------------------------------------------


def test_parse_malformed_xml_raises_trusted_list_parse_error() -> None:
    """eidas.py 80-81 — ET.ParseError -> TrustedListParseError with 'malformed' in message."""
    with pytest.raises(TrustedListParseError, match="malformed"):
        parse_trusted_list(b"<not-well-formed-xml")


# ---------------------------------------------------------------------------
# eidas.py line 96 — service_type not in TSA URIs -> continue
# ---------------------------------------------------------------------------


def test_parse_non_tsa_service_type_skipped() -> None:
    """eidas.py line 96 — ServiceTypeIdentifier not a TSA URI -> service silently skipped."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>http://uri.etsi.org/TrstSvc/Svctype/CA/QC</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">Qualified CA</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert entries == []


# ---------------------------------------------------------------------------
# eidas.py line 103 — status not "granted" or "undersupervision" -> continue
# ---------------------------------------------------------------------------


def test_parse_withdrawn_status_skipped() -> None:
    """eidas.py line 103 — 'withdrawn' status -> not operational -> service skipped."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">Withdrawn TSA</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/withdrawn</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert entries == []


def test_parse_expired_status_skipped() -> None:
    """eidas.py line 103 — 'deprecated_notUsedForTrustByAgreement' -> neither granted nor undersupervision."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">Expired TSA</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/deprecated_notUsedForTrustByAgreement</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    entries = parse_trusted_list(xml)
    assert entries == []


# ---------------------------------------------------------------------------
# eidas.py lines 130-131 — base64 decode failure -> TrustedListParseError
# ---------------------------------------------------------------------------


def test_parse_invalid_base64_cert_raises() -> None:
    """eidas.py 130-131 — non-base64 X509Certificate text -> TrustedListParseError."""
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">Bad Cert TSA</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>***not-valid-base64@@@</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    with pytest.raises(TrustedListParseError, match="X509Certificate"):
        parse_trusted_list(xml)


# ---------------------------------------------------------------------------
# eidas.py line 154 — load_qualified_tsa_trust_roots convenience function
# ---------------------------------------------------------------------------


def test_load_qualified_tsa_trust_roots_returns_der_bytes() -> None:
    """eidas.py 154 — load_qualified_tsa_trust_roots returns list of DER bytes only."""
    cert2 = b"\x30\x82\x01\x01" + b"\x01" * 252
    xml = _xml(
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_QTST_URI}</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">TSA A</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(_FAKE_CERT_DER).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>{_GRANTED}</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
        f"""<TSPService>
  <ServiceInformation>
    <ServiceTypeIdentifier>{ETSI_TSA_URI}</ServiceTypeIdentifier>
    <ServiceName><Name xml:lang="en">TSA B</Name></ServiceName>
    <ServiceDigitalIdentity>
      <DigitalId><X509Certificate>{b64encode(cert2).decode()}</X509Certificate></DigitalId>
    </ServiceDigitalIdentity>
    <ServiceStatus>http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/undersupervision</ServiceStatus>
  </ServiceInformation>
</TSPService>\n""",
    )
    roots = load_qualified_tsa_trust_roots(xml)
    assert isinstance(roots, list)
    assert len(roots) == 2
    assert _FAKE_CERT_DER in roots
    assert cert2 in roots


def test_verify_no_ocsp_when_verify_ocsp_false() -> None:
    """verifier.py 335->371 branch — verify_ocsp=False skips OCSP check, goes directly to result."""
    chain_now = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)

    chain_evs = []
    head = genesis_head()
    draft = EventDraft(event_type="eval_event", actor="agent://test/0", payload={"i": 0})
    ev = chain_extend(head, draft, now=chain_now, event_id="00000000-0000-7000-8000-000000000000")
    chain_evs.append(ev)
    head = ChainHead(seq=ev.seq, event_hash=ev.event_hash)

    authority = TestTSAAuthority(now=chain_now)
    materials = authority.materials()

    token_der = authority.sign_timestamp_response(chain_evs[0].event_hash, gen_time=chain_now, serial_number=1)
    real_ocsp = authority.issue_real_ocsp_response(gen_time=chain_now)
    anchor = AnchorRecord(
        anchor_schema_version=ANCHOR_SCHEMA_VERSION,
        anchored_seq=0,
        anchored_event_hash=chain_evs[0].event_hash,
        tsa_provider_id=f"test.tsa:{authority.common_name}",
        tsa_token=token_der,
        tsa_cert_chain=(materials.leaf_cert_der, materials.root_cert_der),
        ocsp_responses=(real_ocsp,),
        issued_at_claimed=chain_now,
    )

    # verify_ocsp=False -> _ocsp_mod stays None -> OCSP block skipped -> branch 335->371
    result = verify_chain_with_anchors(
        chain_evs,
        [anchor],
        trust_roots_der=[materials.root_cert_der],
        verify_ocsp=False,  # <-- disables OCSP, exercises 335->371 branch
        verification_time=chain_now,
    )
    ar = result.anchor_results[0]
    assert ar.valid is True
    assert ar.cert_status == "VALID"
    assert result.verification_status == "verified"
