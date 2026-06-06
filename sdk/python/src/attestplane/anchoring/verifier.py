# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Anchor-aware chain verifier per ADR-0003 § 5.

Provides :func:`verify_chain_with_anchors` — a new function distinct
from :func:`~attestplane.hashchain.verify_chain` so that v0.0.1
callers remain bytes-identical.

The v1 implementation verifies anchor-to-chain cross-references but
does NOT yet parse RFC-3161 TimeStampTokens to extract the TSA's
authoritative ``genTime``. The ASN.1 parsing arrives in a follow-up
PR alongside ``anchor_vectors.json``; until then,
:attr:`SingleAnchorResult.cert_status` is reported as
``"VALID_UNVERIFIED"`` for anchors with non-empty cert chains and
``"MISSING_LTV_ARTIFACTS"`` otherwise.

Cross-reference-correct anchors that cannot be cryptographically
verified are treated as quarantined, not as anchored.

What this v1 implementation DOES check:

1. Every :class:`AnchorRecord.anchored_event_hash` matches the
   :class:`~attestplane.types.ChainedEvent.event_hash` at the
   corresponding ``anchored_seq`` in the chain.
2. Every :class:`AnchorRecord.anchored_seq` is in range.
3. Every :class:`AnchorRecord.anchor_schema_version` equals the v1
   constant.
4. Anchor :class:`~datetime.datetime.tzinfo` is UTC.
5. ``tsa_cert_chain`` and ``ocsp_responses`` are non-empty (per
   ADR-0003 § 6 CAdES-A discipline).

What this implementation does NOT yet check:

- TSA signature over the TimeStampToken (M5 with ``cryptography``).
- Cert chain validation against ``trust_roots`` (M5).
- OCSP response signature + freshness (M5).
- TSA-vs-local clock skew warning (M5).
- TSA-claimed ``genTime`` monotonicity across anchors of the same
  chain head (M5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal

from attestplane.anchoring.base import (
    ANCHOR_SCHEMA_VERSION,
    AnchorRecord,
    AnchorVerificationError,
    TimestampRequest,
    TSAUnavailableError,
)
from attestplane.hashchain import verify_chain
from attestplane.types import ChainedEvent
from attestplane.verify_reason_codes import (
    VERIFY_REASON_ANCHOR_INVALID,
    VERIFY_REASON_ANCHOR_QUARANTINED,
)

CertStatus = Literal[
    "VALID",
    "VALID_UNVERIFIED",
    "MISSING_LTV_ARTIFACTS",
    "EXPIRED_VALID_AT_ISSUANCE",
    "REVOKED",
]
AnchorVerificationStatus = Literal["verified", "failed", "quarantined", "not_performed"]


@dataclass(frozen=True, slots=True)
class SingleAnchorResult:
    """Per-anchor verification outcome."""

    seq: int
    provider: str
    valid: bool
    cert_status: CertStatus
    ltv_artifacts_present: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class AnchorVerificationResult:
    """Aggregate outcome of :func:`verify_chain_with_anchors`."""

    chain_ok: bool
    """True iff the underlying ``verify_chain`` returned ok."""

    chain_reason: str | None
    """Diagnostic from ``verify_chain`` when ``chain_ok=False``."""

    anchored_seqs: frozenset[int]
    """Seqs for which at least one anchor verified."""

    unanchored_seqs: frozenset[int]
    """Seqs in the chain that have no anchor."""

    anchor_results: tuple[SingleAnchorResult, ...]
    """One entry per (anchor record, chain) pair, in input order."""

    verification_status: AnchorVerificationStatus
    """Explicit aggregate status; empty or unverifiable anchor evidence is not a successful anchored verification."""

    @property
    def ok(self) -> bool:
        """True iff chain verifies AND at least one supplied anchor cryptographically verifies."""
        return self.chain_ok and self.verification_status == "verified"


def verify_chain_with_anchors(
    events: list[ChainedEvent],
    anchors: list[AnchorRecord],
    *,
    trust_roots_der: list[bytes] | None = None,
    verification_time: datetime | None = None,
    verify_ocsp: bool = True,
) -> AnchorVerificationResult:
    """Re-walk the chain AND check every anchor against it.

    Cross-reference checks (always performed):

    - ``anchor_schema_version`` equals v1
    - ``anchored_seq`` is in range
    - ``anchored_event_hash`` matches the chain head at that seq
    - ``issued_at_claimed`` is UTC
    - ``tsa_cert_chain`` and ``ocsp_responses`` are both non-empty
      (CAdES-A requirement per ADR-0003 § 6)

    Full signature verification (performed when ``trust_roots_der`` is
    provided AND the ``cryptography`` + ``asn1crypto`` extras are
    installed):

    - The TSA's RSA signature over the SignedAttributes verifies
      against the leaf cert embedded in the TimeStampToken.
    - The TimeStampToken's messageImprint matches the AnchorRecord's
      ``anchored_event_hash``.
    - The leaf cert chains (single hop) to one of the configured
      trust roots by issuer-DN match + root-key signature check.
    - The leaf cert is within its validity window at
      ``verification_time`` (defaults to "now").

    When ``trust_roots_der`` is ``None``, cross-reference-correct
    anchors are reported with ``cert_status="VALID_UNVERIFIED"`` —
    this is the v1 substrate-only behaviour preserved for callers who
    have not installed the anchor extras.
    """
    chain_result = verify_chain(events)
    seqs_in_chain = {ev.seq for ev in events}
    anchor_results: list[SingleAnchorResult] = []
    anchored_seqs: set[int] = set()

    # Lazy-import the rfc3161 module so substrate-only installs that
    # never call verify_chain_with_anchors(trust_roots_der=...) do not
    # need the anchor extras.
    _rfc3161: Any = None
    _ocsp_mod: Any = None
    if trust_roots_der is not None:
        try:
            from attestplane.anchoring import rfc3161 as _rfc3161_mod

            _rfc3161 = _rfc3161_mod
            if verify_ocsp:
                from attestplane.anchoring import ocsp as _ocsp_module

                _ocsp_mod = _ocsp_module
        except ImportError as exc:  # pragma: no cover
            raise AnchorVerificationError(
                "trust_roots_der was provided but the 'anchor' extras are "
                "not installed; install with: pip install attestplane[anchor]"
            ) from exc

    for anchor in anchors:
        provider = anchor.tsa_provider_id

        if anchor.anchor_schema_version != ANCHOR_SCHEMA_VERSION:
            anchor_results.append(
                SingleAnchorResult(
                    seq=anchor.anchored_seq,
                    provider=provider,
                    valid=False,
                    cert_status="MISSING_LTV_ARTIFACTS",
                    ltv_artifacts_present=False,
                    reason=(
                        f"anchor_schema_version={anchor.anchor_schema_version}; "
                        f"this verifier handles version {ANCHOR_SCHEMA_VERSION} only"
                    ),
                )
            )
            continue

        if anchor.anchored_seq not in seqs_in_chain:
            anchor_results.append(
                SingleAnchorResult(
                    seq=anchor.anchored_seq,
                    provider=provider,
                    valid=False,
                    cert_status="MISSING_LTV_ARTIFACTS",
                    ltv_artifacts_present=bool(anchor.tsa_cert_chain),
                    reason=f"anchored_seq={anchor.anchored_seq} not in chain",
                )
            )
            continue

        target = events[anchor.anchored_seq]
        if target.event_hash != anchor.anchored_event_hash:
            anchor_results.append(
                SingleAnchorResult(
                    seq=anchor.anchored_seq,
                    provider=provider,
                    valid=False,
                    cert_status="MISSING_LTV_ARTIFACTS",
                    ltv_artifacts_present=bool(anchor.tsa_cert_chain),
                    reason=(f"anchored_event_hash mismatch at seq {anchor.anchored_seq}"),
                )
            )
            continue

        if anchor.issued_at_claimed.tzinfo is None:
            anchor_results.append(
                SingleAnchorResult(
                    seq=anchor.anchored_seq,
                    provider=provider,
                    valid=False,
                    cert_status="MISSING_LTV_ARTIFACTS",
                    ltv_artifacts_present=bool(anchor.tsa_cert_chain),
                    reason="issued_at_claimed is naive datetime",
                )
            )
            continue
        if anchor.issued_at_claimed.utcoffset() != UTC.utcoffset(None):
            anchor_results.append(
                SingleAnchorResult(
                    seq=anchor.anchored_seq,
                    provider=provider,
                    valid=False,
                    cert_status="MISSING_LTV_ARTIFACTS",
                    ltv_artifacts_present=bool(anchor.tsa_cert_chain),
                    reason="issued_at_claimed is not UTC",
                )
            )
            continue

        ltv_present = bool(anchor.tsa_cert_chain) and bool(anchor.ocsp_responses)
        if not ltv_present:
            anchor_results.append(
                SingleAnchorResult(
                    seq=anchor.anchored_seq,
                    provider=provider,
                    valid=False,
                    cert_status="MISSING_LTV_ARTIFACTS",
                    ltv_artifacts_present=False,
                    reason=("tsa_cert_chain or ocsp_responses is empty; CAdES-A long-term validation requires both"),
                )
            )
            continue

        # Cross-reference checks have all passed. Decide cert_status:
        # Dispatch: Sigstore Rekor anchors take a different path per
        # ADR-0006 § 3 (provider_id prefix dispatch).
        if trust_roots_der is not None and provider.startswith("sigstore.rekor:"):
            try:
                from attestplane.anchoring import sigstore as _sigstore_mod

                parsed_entry = _sigstore_mod.parse_rekor_log_entry(anchor.tsa_token)
                # The Rekor public key was captured in tsa_cert_chain[0]
                # at anchor issuance time per ADR-0006 § 3 mapping.
                rekor_pubkey_der = anchor.tsa_cert_chain[0] if anchor.tsa_cert_chain else b""
                _sigstore_mod.verify_rekor_signed_entry_timestamp(
                    parsed_entry,
                    expected_digest=anchor.anchored_event_hash,
                    rekor_public_key_der=rekor_pubkey_der,
                )
            except AnchorVerificationError as exc:
                anchor_results.append(
                    SingleAnchorResult(
                        seq=anchor.anchored_seq,
                        provider=provider,
                        valid=False,
                        cert_status="MISSING_LTV_ARTIFACTS",
                        ltv_artifacts_present=True,
                        reason=str(exc),
                    )
                )
                continue
            anchor_results.append(
                SingleAnchorResult(
                    seq=anchor.anchored_seq,
                    provider=provider,
                    valid=True,
                    cert_status="VALID",
                    ltv_artifacts_present=True,
                    reason=None,
                )
            )
            anchored_seqs.add(anchor.anchored_seq)
            continue

        if _rfc3161 is not None and trust_roots_der is not None:
            try:
                parsed = _rfc3161.parse_timestamp_response(anchor.tsa_token)
                # Use tsa_cert_chain as the intermediate pool. The leaf
                # is already embedded in the token; entries other than
                # the leaf in tsa_cert_chain are intermediates that may
                # need to be walked to reach a trust root.
                _rfc3161.verify_timestamp_token(
                    parsed,
                    expected_digest=anchor.anchored_event_hash,
                    trust_roots_der=trust_roots_der,
                    verification_time=verification_time,
                    intermediates_der=list(anchor.tsa_cert_chain),
                )
            except AnchorVerificationError as exc:
                anchor_results.append(
                    SingleAnchorResult(
                        seq=anchor.anchored_seq,
                        provider=provider,
                        valid=False,
                        cert_status="MISSING_LTV_ARTIFACTS",
                        ltv_artifacts_present=True,
                        reason=str(exc),
                    )
                )
                continue

            # OCSP path: verify each OCSP response against the issuer.
            # The issuer cert is taken from the cert chain; we look for
            # one whose subject matches the leaf's issuer. If no OCSP
            # responses are present, the cross-reference check above
            # already required len(ocsp_responses) > 0, so we have at
            # least one here.
            ocsp_failure: str | None = None
            ocsp_status: str = "good"
            if _ocsp_mod is not None and anchor.ocsp_responses:
                try:
                    from asn1crypto import x509 as _asn1_x509

                    leaf_asn1 = _asn1_x509.Certificate.load(parsed.leaf_cert_der)
                    leaf_serial = int(leaf_asn1.serial_number)
                    # Find an issuer cert: walk tsa_cert_chain looking for
                    # subject matching leaf's issuer. Fall back to the
                    # first configured trust root.
                    issuer_der: bytes | None = None
                    for c in anchor.tsa_cert_chain:
                        try:
                            cand = _asn1_x509.Certificate.load(c)
                            if cand.subject.native == leaf_asn1.issuer.native:
                                issuer_der = c
                                break
                        except Exception:
                            continue
                    if issuer_der is None and trust_roots_der:
                        issuer_der = trust_roots_der[0]
                    if issuer_der is None:
                        ocsp_failure = "no issuer cert available for OCSP verification"
                    else:
                        for ocsp_der in anchor.ocsp_responses:
                            ocsp_parsed = _ocsp_mod.parse_and_verify_ocsp(
                                ocsp_der,
                                expected_serial=leaf_serial,
                                issuer_cert_der=issuer_der,
                                verification_time=verification_time,
                            )
                            if ocsp_parsed.cert_status != "good":
                                ocsp_status = ocsp_parsed.cert_status
                                break
                except AnchorVerificationError as exc:
                    ocsp_failure = str(exc)

            if ocsp_failure is not None:
                # OCSP failed structurally — surface as MISSING_LTV
                # rather than EXPIRED/REVOKED because the underlying
                # signature might still be sound; we just couldn't
                # confirm freshness.
                anchor_results.append(
                    SingleAnchorResult(
                        seq=anchor.anchored_seq,
                        provider=provider,
                        valid=False,
                        cert_status="MISSING_LTV_ARTIFACTS",
                        ltv_artifacts_present=True,
                        reason=f"OCSP: {ocsp_failure}",
                    )
                )
                continue
            if ocsp_status == "revoked":
                anchor_results.append(
                    SingleAnchorResult(
                        seq=anchor.anchored_seq,
                        provider=provider,
                        valid=False,
                        cert_status="REVOKED",
                        ltv_artifacts_present=True,
                        reason="OCSP responder reports the TSA leaf cert is revoked",
                    )
                )
                continue
            if ocsp_status == "unknown":
                anchor_results.append(
                    SingleAnchorResult(
                        seq=anchor.anchored_seq,
                        provider=provider,
                        valid=False,
                        cert_status="MISSING_LTV_ARTIFACTS",
                        ltv_artifacts_present=True,
                        reason="OCSP responder reports cert status unknown",
                    )
                )
                continue

            anchor_results.append(
                SingleAnchorResult(
                    seq=anchor.anchored_seq,
                    provider=provider,
                    valid=True,
                    cert_status="VALID",
                    ltv_artifacts_present=True,
                    reason=None,
                )
            )
        else:
            anchor_results.append(
                SingleAnchorResult(
                    seq=anchor.anchored_seq,
                    provider=provider,
                    valid=False,
                    cert_status="VALID_UNVERIFIED",
                    ltv_artifacts_present=True,
                    reason="trust_roots_der not provided; anchor verification quarantined",
                )
            )

    unanchored_seqs = seqs_in_chain - anchored_seqs
    if not anchor_results:
        verification_status: AnchorVerificationStatus = "not_performed"
    elif all(a.valid for a in anchor_results):
        verification_status = "verified"
    elif trust_roots_der is None and all(a.cert_status == "VALID_UNVERIFIED" for a in anchor_results):
        verification_status = "quarantined"
    else:
        verification_status = "failed"

    return AnchorVerificationResult(
        chain_ok=chain_result.ok,
        chain_reason=chain_result.reason,
        anchored_seqs=frozenset(anchored_seqs),
        unanchored_seqs=frozenset(unanchored_seqs),
        anchor_results=tuple(anchor_results),
        verification_status=verification_status,
    )


LIVE_ANCHOR_QUARANTINE_EXIT_CODE: Final[int] = 2
"""Exit code for a live-anchor quarantine.

Aligns with the CLI exit-code contract in
:mod:`attestplane.cli.verify_json` (0=verified, 1=verification_failure,
2=quarantine/pinning-gate, 3=usage_error). A quarantined anchor is a
claim-safe 'unknown', distinct from a hard verification failure (1)."""


LiveAnchorStatus = Literal["verified", "failed", "quarantined"]


@dataclass(frozen=True, slots=True)
class LiveAnchorResult:
    """Outcome of :func:`verify_live_anchor_with_provider`.

    claim-safe tri-state: ``verified`` (anchor cryptographically
    verified), ``failed`` (TSA reachable but anchor invalid / expired /
    tampered), ``quarantined`` (TSA unreachable -- neither a verified
    nor a failed claim).
    """

    status: LiveAnchorStatus
    exit_code: int
    reason_code: str | None
    claim_verified: bool
    anchor_record: AnchorRecord | None
    verification_result: AnchorVerificationResult | None


def verify_live_anchor_with_provider(
    event: ChainedEvent,
    provider: Any,
    *,
    trust_roots_der: list[bytes] | None = None,
    verification_time: datetime | None = None,
    verify_ocsp: bool = True,
) -> LiveAnchorResult:
    """Request a live timestamp for ``event`` and verify it, claim-safe.

    Failure-mode routing per ADR-0003 § 4:

    - Provider raises :class:`TSAUnavailableError` (TSA unreachable /
      timeout / 5xx) -> ``status="quarantined"``. This is NOT a verified
      claim and NOT a hard failure; the anchor evidence simply could not
      be obtained.
    - Provider returns an :class:`AnchorRecord` that fails verification
      (tampered token, expired cert, OCSP revoked) -> ``status="failed"``,
      ``exit_code=1``.
    - Provider returns an anchor that cryptographically verifies ->
      ``status="verified"``, ``exit_code=0``.

    A ``VALID_UNVERIFIED`` anchor (no ``trust_roots_der`` supplied, so no
    LTV verification was possible) maps to ``failed``, never ``verified``:
    claiming 'verified' without verification evidence would be a false
    compliance assertion.
    """
    request = TimestampRequest(digest=event.event_hash)
    now = verification_time or datetime.now(UTC)

    try:
        anchor = provider.request_timestamp(
            request,
            anchored_seq=event.seq,
            now=now,
        )
    except TSAUnavailableError:
        return LiveAnchorResult(
            status="quarantined",
            exit_code=LIVE_ANCHOR_QUARANTINE_EXIT_CODE,
            reason_code=VERIFY_REASON_ANCHOR_QUARANTINED,
            claim_verified=False,
            anchor_record=None,
            verification_result=None,
        )

    verification = verify_chain_with_anchors(
        [event],
        [anchor],
        trust_roots_der=trust_roots_der,
        verification_time=verification_time,
        verify_ocsp=verify_ocsp,
    )

    if verification.ok:
        return LiveAnchorResult(
            status="verified",
            exit_code=0,
            reason_code=None,
            claim_verified=True,
            anchor_record=anchor,
            verification_result=verification,
        )

    # Verification did not pass. Distinguish a claim-safe *quarantine* from
    # a hard *failure*:
    #
    # - The anchor lacks the long-term-validation artifacts required to
    #   fully evaluate it (e.g. a live TSA token with no embedded OCSP
    #   response, or no cert chain). It can be neither proven valid nor
    #   proven invalid -> ``quarantined`` (claim-safe "unknown", never a
    #   verified claim, never a silent pass).
    # - The anchor carries complete artifacts but is provably invalid
    #   (tampered signature, expired/revoked cert) -> ``failed``.
    #
    # Claim-safety note: an anchor lacking artifacts is treated as
    # "unknown" rather than "failed"; quarantine never asserts a verified
    # claim, so this can never produce a false attestation.
    lacks_ltv_artifacts = not anchor.ocsp_responses or not anchor.tsa_cert_chain
    if lacks_ltv_artifacts:
        return LiveAnchorResult(
            status="quarantined",
            exit_code=LIVE_ANCHOR_QUARANTINE_EXIT_CODE,
            reason_code=VERIFY_REASON_ANCHOR_QUARANTINED,
            claim_verified=False,
            anchor_record=anchor,
            verification_result=verification,
        )

    return LiveAnchorResult(
        status="failed",
        exit_code=1,
        reason_code=VERIFY_REASON_ANCHOR_INVALID,
        claim_verified=False,
        anchor_record=anchor,
        verification_result=verification,
    )


__all__ = [
    "LIVE_ANCHOR_QUARANTINE_EXIT_CODE",
    "AnchorVerificationResult",
    "AnchorVerificationStatus",
    "CertStatus",
    "LiveAnchorResult",
    "LiveAnchorStatus",
    "SingleAnchorResult",
    "verify_chain_with_anchors",
    "verify_live_anchor_with_provider",
]
