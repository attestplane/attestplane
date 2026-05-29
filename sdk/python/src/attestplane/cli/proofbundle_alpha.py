# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Alpha CLI verifier for local ProofBundle verification envelopes.

This module intentionally stays out of the public SDK export surface. It is
the implementation behind ``attestplane verify-proofbundle`` and performs
local, fail-closed shape/hash checks only. It does not perform cryptographic
signature verification, anchored verification, network access, or compliance
certification.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from attestplane.canonical import CanonicalizationError, canonicalize
from attestplane.intoto import DSSE_PAYLOAD_TYPE, PREDICATE_TYPE_V1, STATEMENT_TYPE
from attestplane.obligations import load_all_registries
from attestplane.verifier import BundleSchemaError, verify_proof_bundle
from attestplane.verify_errors import (
    VERIFY_ARTIFACT_HASH_FAILED,
    VERIFY_CHAIN_RECOMPUTE_FAILED,
    VERIFY_EXTENSION_FAILED,
    VERIFY_EXTENSION_INVALID_INPUT,
    VERIFY_EXTENSION_UNSUPPORTED,
    VERIFY_OK,
    VERIFY_REQUIRED_FIELDS_MISSING,
    VERIFY_SCHEMA_ERROR,
    VerifyErrorCode,
)

ALPHA_ENVELOPE_SCHEMA_VERSION = 1
VERIFICATION_SCOPE = "proofbundle_alpha_local"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

# P3.2: signature / anchor extension interface allowlist.
# Cryptographic verification is NOT implemented in this alpha branch — the
# verifier accepts these algorithm/type names ONLY as inputs to fail-closed
# branches, never as evidence of successful verification. See
# docs/validation/p3_2_signed_anchored_verification_report.md.
SIGNATURE_ALGORITHM_ALLOWLIST = {"ed25519"}
ANCHOR_TYPE_ALLOWLIST = {"rfc3161"}

CheckStatus = Literal["pass", "fail"]
FailureKind = Literal["verification_failed", "invalid_input"]
ExtensionStatus = Literal[
    "skipped",
    "passed",
    "failed",
    "quarantined",
    "invalid_input",
    "unsupported",
    "not_implemented",
]


@dataclass(frozen=True, slots=True)
class AlphaCheck:
    name: str
    status: CheckStatus
    failure_kind: FailureKind | None = None
    detail: str | None = None

    def as_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": self.name, "status": self.status}
        if self.failure_kind is not None:
            payload["failure_kind"] = self.failure_kind
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


def _pass(name: str, detail: str | None = None) -> AlphaCheck:
    return AlphaCheck(name=name, status="pass", detail=detail)


def _fail(name: str, kind: FailureKind, detail: str) -> AlphaCheck:
    return AlphaCheck(name=name, status="fail", failure_kind=kind, detail=detail)


def _is_hex64(value: Any) -> bool:
    return isinstance(value, str) and HEX64_RE.fullmatch(value) is not None


def _load_json(path: Path) -> tuple[Any | None, AlphaCheck]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, _fail("json_read", "invalid_input", f"cannot read input file: {exc}")
    try:
        return json.loads(text), _pass("json_parse")
    except json.JSONDecodeError as exc:
        return None, _fail("json_parse", "invalid_input", f"malformed JSON: {exc.msg}")


def _check_root_shape(root: Any) -> tuple[dict[str, Any] | None, AlphaCheck]:
    if not isinstance(root, dict):
        return None, _fail("root_object", "invalid_input", "input must be a JSON object")
    required = {
        "proofbundle_verifier_schema_version",
        "proof_bundle",
        "artifact",
        "hash_chain",
        "obligation_references",
        "in_toto_statement",
        "dsse_envelope",
        "storage_compatibility",
        "provenance",
    }
    missing = sorted(required - set(root))
    if missing:
        return root, _fail("required_fields", "invalid_input", f"missing required fields: {missing}")
    return root, _pass("required_fields")


def _check_schema_version(root: dict[str, Any]) -> AlphaCheck:
    version = root.get("proofbundle_verifier_schema_version")
    if version != ALPHA_ENVELOPE_SCHEMA_VERSION:
        return _fail(
            "schema_version",
            "invalid_input",
            f"unsupported proofbundle_verifier_schema_version={version!r}",
        )
    return _pass("schema_version", "proofbundle_verifier_schema_version=1")


def _check_artifact(root: dict[str, Any]) -> AlphaCheck:
    artifact = root.get("artifact")
    proof_bundle = root.get("proof_bundle")
    if not isinstance(artifact, dict):
        return _fail("artifact_hash", "invalid_input", "artifact must be a JSON object")
    if artifact.get("hash_algorithm") != "sha256":
        return _fail("artifact_hash", "invalid_input", "artifact.hash_algorithm must be 'sha256'")
    if artifact.get("target") != "proof_bundle":
        return _fail("artifact_hash", "invalid_input", "artifact.target must be 'proof_bundle'")
    declared = artifact.get("sha256")
    if not _is_hex64(declared):
        return _fail("artifact_hash", "invalid_input", "artifact.sha256 must be lowercase 64-hex")
    try:
        actual = hashlib.sha256(canonicalize(proof_bundle)).hexdigest()
    except CanonicalizationError as exc:
        return _fail("artifact_hash", "invalid_input", f"proof_bundle is not canonicalizable: {exc}")
    if declared != actual:
        return _fail("artifact_hash", "verification_failed", "artifact.sha256 does not match proof_bundle")
    return _pass("artifact_hash")


def _check_proof_bundle(root: dict[str, Any]) -> tuple[dict[str, Any] | None, list[AlphaCheck]]:
    proof_bundle = root.get("proof_bundle")
    if not isinstance(proof_bundle, dict):
        return None, [_fail("proof_bundle_shape", "invalid_input", "proof_bundle must be a JSON object")]
    try:
        result = verify_proof_bundle(proof_bundle)
    except BundleSchemaError as exc:
        return proof_bundle, [_fail("proof_bundle_shape", "invalid_input", str(exc))]
    checks = [_pass("proof_bundle_shape")]
    if result.ok:
        checks.append(_pass("hash_chain_recompute"))
    else:
        reason = (
            result.chain_result.reason or result.metadata_reason or result.policy_trace_refs_reason or "bundle failed"
        )
        checks.append(_fail("hash_chain_recompute", "verification_failed", reason))
    return proof_bundle, checks


def _check_hash_chain(root: dict[str, Any], proof_bundle: dict[str, Any] | None) -> AlphaCheck:
    hash_chain = root.get("hash_chain")
    if not isinstance(hash_chain, dict):
        return _fail("hash_chain_metadata", "invalid_input", "hash_chain must be a JSON object")
    head_hash = hash_chain.get("head_hash_hex")
    if not _is_hex64(head_hash):
        return _fail("hash_chain_metadata", "invalid_input", "hash_chain.head_hash_hex must be lowercase 64-hex")
    head_seq = hash_chain.get("head_seq")
    if not isinstance(head_seq, int):
        return _fail("hash_chain_metadata", "invalid_input", "hash_chain.head_seq must be an integer")
    if proof_bundle is None:
        return _fail("hash_chain_metadata", "invalid_input", "proof_bundle unavailable")
    metadata = proof_bundle.get("chain_metadata")
    if not isinstance(metadata, dict):
        return _fail("hash_chain_metadata", "invalid_input", "proof_bundle.chain_metadata unavailable")
    if head_hash != metadata.get("head_hash_hex") or head_seq != metadata.get("head_seq"):
        return _fail(
            "hash_chain_metadata",
            "verification_failed",
            "hash_chain does not match proof_bundle chain_metadata",
        )
    return _pass("hash_chain_metadata")


def _known_obligation_ids() -> set[str]:
    ids: set[str] = set()
    for registry in load_all_registries():
        ids.update(entry.obligation_id for entry in registry.entries)
    return ids


def _check_obligation_refs(root: dict[str, Any], proof_bundle: dict[str, Any] | None) -> AlphaCheck:
    refs = root.get("obligation_references")
    if not isinstance(refs, list):
        return _fail("obligation_references", "invalid_input", "obligation_references must be an array")
    for idx, ref in enumerate(refs):
        if not isinstance(ref, dict):
            return _fail("obligation_references", "invalid_input", f"obligation_references[{idx}] must be an object")
        if not isinstance(ref.get("obligation_id"), str) or not ref["obligation_id"]:
            return _fail(
                "obligation_references",
                "invalid_input",
                f"obligation_references[{idx}].obligation_id is invalid",
            )
    declared = [ref["obligation_id"] for ref in refs]
    if len(declared) != len(set(declared)):
        return _fail("obligation_references", "invalid_input", "obligation_references contains duplicate obligation_id")
    unknown = sorted(set(declared) - _known_obligation_ids())
    if unknown:
        return _fail("obligation_references", "invalid_input", f"unknown obligation ids: {unknown}")
    bundle_ids: list[str] = []
    if proof_bundle is not None:
        mappings = proof_bundle.get("framework_mappings", [])
        if not isinstance(mappings, list):
            return _fail("obligation_references", "invalid_input", "proof_bundle.framework_mappings must be an array")
        for idx, mapping in enumerate(mappings):
            if not isinstance(mapping, dict) or not isinstance(mapping.get("obligation_id"), str):
                return _fail(
                    "obligation_references",
                    "invalid_input",
                    f"framework_mappings[{idx}] obligation_id invalid",
                )
            bundle_ids.append(mapping["obligation_id"])
    if declared != bundle_ids:
        return _fail(
            "obligation_references",
            "verification_failed",
            "obligation_references must match proof_bundle.framework_mappings order",
        )
    return _pass("obligation_references")


def _check_in_toto_statement(root: dict[str, Any], proof_bundle: dict[str, Any] | None) -> AlphaCheck:
    statement = root.get("in_toto_statement")
    if not isinstance(statement, dict):
        return _fail("in_toto_shape", "invalid_input", "in_toto_statement must be a JSON object")
    if statement.get("_type") != STATEMENT_TYPE:
        return _fail("in_toto_shape", "invalid_input", f"in_toto_statement._type must be {STATEMENT_TYPE!r}")
    if statement.get("predicateType") != PREDICATE_TYPE_V1:
        return _fail(
            "in_toto_shape",
            "invalid_input",
            "in_toto_statement.predicateType is not the Attestplane v1 predicate",
        )
    subjects = statement.get("subject")
    if not isinstance(subjects, list) or len(subjects) != 1 or not isinstance(subjects[0], dict):
        return _fail("in_toto_shape", "invalid_input", "in_toto_statement.subject must contain one subject object")
    digest = subjects[0].get("digest")
    if not isinstance(digest, dict) or not _is_hex64(digest.get("sha256")):
        return _fail("in_toto_shape", "invalid_input", "in_toto_statement.subject[0].digest.sha256 invalid")
    predicate = statement.get("predicate")
    if not isinstance(predicate, dict):
        return _fail("in_toto_shape", "invalid_input", "in_toto_statement.predicate must be an object")
    if proof_bundle is None:
        return _fail("in_toto_shape", "invalid_input", "proof_bundle unavailable")
    metadata = proof_bundle.get("chain_metadata", {})
    if digest.get("sha256") != metadata.get("head_hash_hex"):
        return _fail("in_toto_shape", "verification_failed", "in_toto subject digest does not match chain head")
    if predicate.get("chain_metadata") != proof_bundle.get("chain_metadata"):
        return _fail(
            "in_toto_shape",
            "verification_failed",
            "in_toto predicate.chain_metadata does not match proof_bundle",
        )
    return _pass("in_toto_shape")


def _check_dsse_envelope(root: dict[str, Any]) -> AlphaCheck:
    envelope = root.get("dsse_envelope")
    statement = root.get("in_toto_statement")
    if not isinstance(envelope, dict):
        return _fail("dsse_shape", "invalid_input", "dsse_envelope must be a JSON object")
    if envelope.get("payloadType") != DSSE_PAYLOAD_TYPE:
        return _fail("dsse_shape", "invalid_input", f"dsse_envelope.payloadType must be {DSSE_PAYLOAD_TYPE!r}")
    payload = envelope.get("payload")
    if not isinstance(payload, str):
        return _fail("dsse_shape", "invalid_input", "dsse_envelope.payload must be base64 text")
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list):
        return _fail("dsse_shape", "invalid_input", "dsse_envelope.signatures must be an array")
    for idx, signature in enumerate(signatures):
        if not isinstance(signature, dict):
            return _fail("dsse_shape", "invalid_input", f"dsse_envelope.signatures[{idx}] must be an object")
    try:
        decoded = json.loads(base64.standard_b64decode(payload))
    except Exception as exc:
        return _fail("dsse_shape", "invalid_input", f"dsse payload is not base64 JSON: {exc}")
    if decoded != statement:
        return _fail("dsse_shape", "verification_failed", "dsse payload does not match in_toto_statement")
    return _pass("dsse_shape", "shape only; cryptographic signatures are not verified")


def _check_storage_compatibility(root: dict[str, Any]) -> AlphaCheck:
    storage = root.get("storage_compatibility")
    if not isinstance(storage, dict):
        return _fail("storage_compatibility", "invalid_input", "storage_compatibility must be a JSON object")
    expected = {
        "schema_version": "storage_compatibility_manifest.v1",
        "record_format": "chained_event_jsonl.v1",
        "backend": "jsonl",
    }
    for key, value in expected.items():
        if storage.get(key) != value:
            return _fail("storage_compatibility", "invalid_input", f"storage_compatibility.{key} must be {value!r}")
    if storage.get("multi_writer_safe") is not False:
        return _fail("storage_compatibility", "invalid_input", "storage_compatibility.multi_writer_safe must be false")
    return _pass("storage_compatibility")


def _check_provenance(root: dict[str, Any]) -> AlphaCheck:
    provenance = root.get("provenance")
    if not isinstance(provenance, dict):
        return _fail("provenance_shape", "invalid_input", "provenance must be a JSON object")
    if provenance.get("slsa_level_claimed") is not None:
        return _fail("provenance_shape", "invalid_input", "provenance.slsa_level_claimed must be null")
    if provenance.get("certified_provenance") is not False:
        return _fail("provenance_shape", "invalid_input", "provenance.certified_provenance must be false")
    if provenance.get("production_supply_chain_security") is not False:
        return _fail("provenance_shape", "invalid_input", "provenance.production_supply_chain_security must be false")
    return _pass("provenance_shape", "no certified provenance or SLSA level is claimed")


def _signature_extension(
    root: dict[str, Any] | None,
    requested: bool,
) -> tuple[ExtensionStatus, dict[str, Any], AlphaCheck | None]:
    """P3.4 signature verification extension — real DSSE PAE + ed25519 verify.

    When ``requested`` is ``False`` (default), returns ``skipped`` with no
    check added. When ``True``, inspects ``root['signature_material']``
    and ``root['dsse_envelope']['signatures']``:

    * absent or empty → ``invalid_input`` (missing_material) + exit 2
    * algorithm outside :data:`SIGNATURE_ALGORITHM_ALLOWLIST` → ``unsupported``
      + exit 2
    * verification material present and verify-success → ``passed`` + exit 0
    * verification material present and verify-failure → ``failed`` + exit 1
    """
    summary: dict[str, Any] = {
        "performed": False,
        "scope": "p3_4_signature_extension_alpha",
    }
    if not requested:
        return "skipped", summary, None

    if not isinstance(root, dict):
        check = _fail(
            "signature_verification",
            "invalid_input",
            "input root unavailable for signature verification",
        )
        return "invalid_input", summary, check

    material = root.get("signature_material")
    envelope = root.get("dsse_envelope") if isinstance(root.get("dsse_envelope"), dict) else None
    signatures = envelope.get("signatures") if isinstance(envelope, dict) else None
    # Order: algorithm allowlist check before missing_material so a fixture
    # declaring `signature_material.algorithm = "rsa-pss-broken"` reaches
    # `unsupported` rather than `missing_material` (which would happen if
    # signatures[] also happens to be empty).
    if isinstance(material, dict):
        algorithm = material.get("algorithm")
        summary["declared_algorithm"] = algorithm
        if algorithm is not None and algorithm not in SIGNATURE_ALGORITHM_ALLOWLIST:
            summary["reason"] = "unsupported_algorithm"
            summary["allowlist"] = sorted(SIGNATURE_ALGORITHM_ALLOWLIST)
            check = _fail(
                "signature_verification",
                "invalid_input",
                f"signature algorithm {algorithm!r} is not in alpha allowlist",
            )
            return "unsupported", summary, check
    if not isinstance(signatures, list) or len(signatures) == 0:
        summary["reason"] = "missing_material"
        check = _fail(
            "signature_verification",
            "invalid_input",
            ("--verify-signature requested but dsse_envelope.signatures is empty"),
        )
        return "invalid_input", summary, check
    if not isinstance(material, dict):
        summary["reason"] = "missing_material"
        check = _fail(
            "signature_verification",
            "invalid_input",
            "--verify-signature requested but signature_material block missing",
        )
        return "invalid_input", summary, check

    algorithm = material.get("algorithm")

    # Real DSSE PAE + ed25519 verify path.
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        from attestplane.intoto import DSSE_PAYLOAD_TYPE, dsse_pae
    except ImportError as exc:
        summary["reason"] = "cryptography_extras_missing"
        check = _fail(
            "signature_verification",
            "invalid_input",
            f"cryptography library not installed: {exc}",
        )
        return "invalid_input", summary, check

    payload_type = envelope.get("payloadType") if isinstance(envelope, dict) else None
    if payload_type != DSSE_PAYLOAD_TYPE:
        summary["reason"] = "wrong_payload_type"
        check = _fail(
            "signature_verification",
            "invalid_input",
            f"dsse_envelope.payloadType {payload_type!r} is not {DSSE_PAYLOAD_TYPE!r}",
        )
        return "invalid_input", summary, check

    payload_b64 = envelope.get("payload") if isinstance(envelope, dict) else None
    if not isinstance(payload_b64, str):
        summary["reason"] = "payload_not_base64_string"
        check = _fail(
            "signature_verification",
            "invalid_input",
            "dsse_envelope.payload must be a base64 string",
        )
        return "invalid_input", summary, check
    try:
        payload_bytes = base64.standard_b64decode(payload_b64)
    except Exception as exc:
        summary["reason"] = "payload_base64_decode_failed"
        check = _fail(
            "signature_verification",
            "invalid_input",
            f"dsse_envelope.payload base64 decode failed: {exc}",
        )
        return "invalid_input", summary, check

    pae = dsse_pae(payload_type, payload_bytes)

    public_keys = material.get("public_keys")
    if not isinstance(public_keys, list) or len(public_keys) == 0:
        summary["reason"] = "missing_public_keys"
        check = _fail(
            "signature_verification",
            "invalid_input",
            "signature_material.public_keys must be a non-empty array",
        )
        return "invalid_input", summary, check
    keys_by_keyid: dict[str, Ed25519PublicKey] = {}
    for idx, key_entry in enumerate(public_keys):
        if not isinstance(key_entry, dict):
            summary["reason"] = "invalid_public_key_entry"
            check = _fail(
                "signature_verification",
                "invalid_input",
                f"public_keys[{idx}] must be an object",
            )
            return "invalid_input", summary, check
        keyid = key_entry.get("keyid")
        pem = key_entry.get("public_key_pem")
        if not isinstance(keyid, str) or not isinstance(pem, str):
            summary["reason"] = "missing_keyid_or_pem"
            check = _fail(
                "signature_verification",
                "invalid_input",
                f"public_keys[{idx}] missing keyid or public_key_pem string",
            )
            return "invalid_input", summary, check
        try:
            pub = load_pem_public_key(pem.encode("utf-8"))
        except Exception as exc:
            summary["reason"] = "invalid_pem_public_key"
            check = _fail(
                "signature_verification",
                "invalid_input",
                f"public_keys[{idx}].public_key_pem load failed: {exc}",
            )
            return "invalid_input", summary, check
        if not isinstance(pub, Ed25519PublicKey):
            summary["reason"] = "wrong_public_key_type"
            check = _fail(
                "signature_verification",
                "invalid_input",
                (
                    f"public_keys[{idx}] is not an ed25519 public key "
                    f"(got {type(pub).__name__}); allowlist is {sorted(SIGNATURE_ALGORITHM_ALLOWLIST)}"
                ),
            )
            return "unsupported", summary, check
        ed_pub: Ed25519PublicKey = pub
        keys_by_keyid[keyid] = ed_pub

    verified = 0
    for sidx, sig_entry in enumerate(signatures):
        if not isinstance(sig_entry, dict):
            summary["reason"] = "invalid_signature_entry"
            check = _fail(
                "signature_verification",
                "invalid_input",
                f"dsse_envelope.signatures[{sidx}] must be an object",
            )
            return "invalid_input", summary, check
        keyid = sig_entry.get("keyid")
        sig_b64 = sig_entry.get("sig")
        if not isinstance(keyid, str) or not isinstance(sig_b64, str):
            summary["reason"] = "missing_sig_or_keyid"
            check = _fail(
                "signature_verification",
                "invalid_input",
                f"signatures[{sidx}] missing keyid or sig string",
            )
            return "invalid_input", summary, check
        verify_key = keys_by_keyid.get(keyid)
        if verify_key is None:
            summary["reason"] = "unknown_keyid"
            check = _fail(
                "signature_verification",
                "invalid_input",
                f"signatures[{sidx}].keyid {keyid!r} not present in signature_material.public_keys",
            )
            return "invalid_input", summary, check
        try:
            sig_bytes = base64.standard_b64decode(sig_b64)
        except Exception as exc:
            summary["reason"] = "sig_base64_decode_failed"
            check = _fail(
                "signature_verification",
                "invalid_input",
                f"signatures[{sidx}].sig base64 decode failed: {exc}",
            )
            return "invalid_input", summary, check
        try:
            verify_key.verify(sig_bytes, pae)
        except InvalidSignature:
            summary["reason"] = "signature_does_not_verify"
            summary["failed_signature_index"] = sidx
            check = _fail(
                "signature_verification",
                "verification_failed",
                (f"DSSE ed25519 signature[{sidx}] (keyid={keyid!r}) does not verify against payload PAE"),
            )
            return "failed", summary, check
        verified += 1

    summary["performed"] = True
    summary["verified_signature_count"] = verified
    summary["allowlist"] = sorted(SIGNATURE_ALGORITHM_ALLOWLIST)
    summary["reason"] = "dsse_ed25519_pae_signatures_verified"
    return (
        "passed",
        summary,
        _pass(
            "signature_verification",
            f"verified {verified} DSSE ed25519 signature(s) over PAE",
        ),
    )


def _anchor_extension(
    root: dict[str, Any] | None,
    requested: bool,
) -> tuple[ExtensionStatus, dict[str, Any], AlphaCheck | None]:
    """P3.4 anchor verification extension — real RFC-3161 verify.

    When ``requested`` is ``False`` (default), returns ``skipped`` with no
    check added. When ``True``, inspects ``root['anchor_records']``:

    * absent or empty → ``invalid_input`` (missing_material) + exit 2
    * any record with ``anchor_type`` outside
      :data:`ANCHOR_TYPE_ALLOWLIST` → ``unsupported`` + exit 2
    * material present and verify-success → ``passed`` + exit 0
    * material present and verify-failure → ``quarantined`` + exit 1

    Verification calls
    :func:`attestplane.anchoring.rfc3161.verify_timestamp_token` with
    the trust roots supplied in each anchor record. No network access
    is attempted under any condition.
    """
    summary: dict[str, Any] = {
        "performed": False,
        "scope": "p3_4_anchor_extension_alpha",
        "network_access_attempted": False,
    }
    if not requested:
        return "skipped", summary, None

    if not isinstance(root, dict):
        check = _fail(
            "anchor_verification",
            "invalid_input",
            "input root unavailable for anchor verification",
        )
        return "invalid_input", summary, check

    records = root.get("anchor_records")
    if not isinstance(records, list) or len(records) == 0:
        summary["reason"] = "missing_material"
        check = _fail(
            "anchor_verification",
            "invalid_input",
            "--verify-anchor requested but proof bundle carries no anchor_records[]",
        )
        return "invalid_input", summary, check

    declared_types: list[Any] = []
    for record in records:
        if not isinstance(record, dict):
            summary["reason"] = "invalid_record_shape"
            check = _fail(
                "anchor_verification",
                "invalid_input",
                "anchor_records[] must contain JSON objects",
            )
            return "invalid_input", summary, check
        declared_types.append(record.get("anchor_type"))
    summary["declared_anchor_types"] = declared_types
    unsupported = [t for t in declared_types if t not in ANCHOR_TYPE_ALLOWLIST]
    if unsupported:
        summary["reason"] = "unsupported_anchor_type"
        summary["allowlist"] = sorted(ANCHOR_TYPE_ALLOWLIST)
        summary["unsupported_types"] = unsupported
        check = _fail(
            "anchor_verification",
            "invalid_input",
            f"anchor_type(s) {unsupported!r} not in alpha allowlist",
        )
        return "unsupported", summary, check

    # Real RFC-3161 cryptographic verification path.
    try:
        from attestplane.anchoring.base import AnchorVerificationError
        from attestplane.anchoring.rfc3161 import (
            parse_timestamp_response,
            verify_timestamp_token,
        )
    except ImportError as exc:
        summary["reason"] = "anchor_extras_missing"
        check = _fail(
            "anchor_verification",
            "invalid_input",
            f"attestplane anchor extras not installed: {exc}",
        )
        return "invalid_input", summary, check

    verified = 0
    for ridx, record in enumerate(records):
        token_b64 = record.get("tsa_token_b64")
        digest_hex = record.get("anchored_event_hash_hex")
        trust_b64s = record.get("trust_roots_der_b64")
        if not isinstance(token_b64, str) or not isinstance(digest_hex, str):
            summary["reason"] = "missing_token_or_digest"
            check = _fail(
                "anchor_verification",
                "invalid_input",
                f"anchor_records[{ridx}] missing tsa_token_b64 or anchored_event_hash_hex",
            )
            return "invalid_input", summary, check
        if not isinstance(trust_b64s, list) or len(trust_b64s) == 0:
            summary["reason"] = "missing_trust_roots"
            check = _fail(
                "anchor_verification",
                "invalid_input",
                f"anchor_records[{ridx}].trust_roots_der_b64 must be a non-empty array",
            )
            return "invalid_input", summary, check
        try:
            token_der = base64.standard_b64decode(token_b64)
        except Exception as exc:
            summary["reason"] = "token_base64_decode_failed"
            check = _fail(
                "anchor_verification",
                "invalid_input",
                f"anchor_records[{ridx}].tsa_token_b64 decode failed: {exc}",
            )
            return "invalid_input", summary, check
        try:
            expected_digest = bytes.fromhex(digest_hex)
        except ValueError as exc:
            summary["reason"] = "digest_not_hex"
            check = _fail(
                "anchor_verification",
                "invalid_input",
                f"anchor_records[{ridx}].anchored_event_hash_hex not valid hex: {exc}",
            )
            return "invalid_input", summary, check
        trust_ders: list[bytes] = []
        for tidx, t_b64 in enumerate(trust_b64s):
            if not isinstance(t_b64, str):
                summary["reason"] = "invalid_trust_root_entry"
                check = _fail(
                    "anchor_verification",
                    "invalid_input",
                    f"anchor_records[{ridx}].trust_roots_der_b64[{tidx}] must be a string",
                )
                return "invalid_input", summary, check
            try:
                trust_ders.append(base64.standard_b64decode(t_b64))
            except Exception as exc:
                summary["reason"] = "trust_root_decode_failed"
                check = _fail(
                    "anchor_verification",
                    "invalid_input",
                    f"anchor_records[{ridx}].trust_roots_der_b64[{tidx}] decode failed: {exc}",
                )
                return "invalid_input", summary, check
        try:
            parsed = parse_timestamp_response(token_der)
        except AnchorVerificationError as exc:
            summary["reason"] = "token_parse_failed"
            check = _fail(
                "anchor_verification",
                "verification_failed",
                f"anchor_records[{ridx}] tsa_token parse failed: {exc}",
            )
            return "failed", summary, check
        # Optional intermediates_der pass-through (cert-chain depth > 1).
        intermediates_der: list[bytes] = []
        import contextlib

        chain_b64s = record.get("tsa_cert_chain_b64")
        if isinstance(chain_b64s, list):
            # Skip the first entry (leaf) — it's already inside the token.
            for c_b64 in chain_b64s[1:]:
                if isinstance(c_b64, str):
                    # Best-effort: malformed intermediates trip the cert-walk
                    # check downstream, so we don't surface decode errors here.
                    with contextlib.suppress(Exception):
                        intermediates_der.append(base64.standard_b64decode(c_b64))
        try:
            verify_timestamp_token(
                parsed,
                expected_digest=expected_digest,
                trust_roots_der=trust_ders,
                intermediates_der=intermediates_der or None,
            )
        except AnchorVerificationError as exc:
            summary["reason"] = "rfc3161_verify_failed"
            summary["failed_anchor_index"] = ridx
            summary["quarantine_reason"] = "rfc3161_verification_failed"
            check = _fail(
                "anchor_verification",
                "verification_failed",
                f"anchor_records[{ridx}] RFC-3161 verification failed: {exc}",
            )
            return "quarantined", summary, check
        verified += 1

    summary["performed"] = True
    summary["verified_anchor_count"] = verified
    summary["allowlist"] = sorted(ANCHOR_TYPE_ALLOWLIST)
    summary["reason"] = "rfc3161_tokens_verified"
    return (
        "passed",
        summary,
        _pass(
            "anchor_verification",
            f"verified {verified} RFC-3161 anchor token(s) against trust roots",
        ),
    )


def verify_alpha_proofbundle_file(
    path: Path,
    *,
    verify_signature: bool = False,
    verify_anchor: bool = False,
) -> dict[str, Any]:
    """Verify a local P3.1/P3.2 ProofBundle verification envelope.

    Returns a machine-readable report. ``exit_code`` follows the CLI contract:
    0 valid, 1 verification failed, 2 invalid input/malformed/unsupported.

    When ``verify_signature`` or ``verify_anchor`` is ``True``, the matching
    fail-closed extension is exercised. The alpha verifier does NOT perform
    cryptographic verification; it only validates that the proof bundle
    carries declared verification material and supported algorithms /
    anchor types, and otherwise fails closed.
    """
    checks: list[AlphaCheck] = []
    root, parse_check = _load_json(path)
    checks.append(parse_check)
    if parse_check.status == "fail":
        return _report(
            path,
            checks,
            verify_signature=verify_signature,
            verify_anchor=verify_anchor,
            signature_status="skipped" if not verify_signature else "invalid_input",
            anchor_status="skipped" if not verify_anchor else "invalid_input",
            signature_summary={"performed": False, "reason": "input_unparsable"},
            anchor_summary={"performed": False, "reason": "input_unparsable"},
        )

    root_dict, shape_check = _check_root_shape(root)
    checks.append(shape_check)
    if root_dict is None:
        return _report(
            path,
            checks,
            verify_signature=verify_signature,
            verify_anchor=verify_anchor,
            signature_status="skipped" if not verify_signature else "invalid_input",
            anchor_status="skipped" if not verify_anchor else "invalid_input",
            signature_summary={"performed": False, "reason": "root_not_object"},
            anchor_summary={"performed": False, "reason": "root_not_object"},
        )

    checks.append(_check_schema_version(root_dict))
    proof_bundle, proof_checks = _check_proof_bundle(root_dict)
    checks.extend(proof_checks)
    checks.extend(
        [
            _check_artifact(root_dict),
            _check_hash_chain(root_dict, proof_bundle),
            _check_obligation_refs(root_dict, proof_bundle),
            _check_in_toto_statement(root_dict, proof_bundle),
            _check_dsse_envelope(root_dict),
            _check_storage_compatibility(root_dict),
            _check_provenance(root_dict),
        ]
    )

    sig_status, sig_summary, sig_check = _signature_extension(root_dict, verify_signature)
    if sig_check is not None:
        checks.append(sig_check)
    anc_status, anc_summary, anc_check = _anchor_extension(root_dict, verify_anchor)
    if anc_check is not None:
        checks.append(anc_check)

    return _report(
        path,
        checks,
        verify_signature=verify_signature,
        verify_anchor=verify_anchor,
        signature_status=sig_status,
        anchor_status=anc_status,
        signature_summary=sig_summary,
        anchor_summary=anc_summary,
    )


def _report(
    path: Path,
    checks: list[AlphaCheck],
    *,
    verify_signature: bool = False,
    verify_anchor: bool = False,
    signature_status: ExtensionStatus = "skipped",
    anchor_status: ExtensionStatus = "skipped",
    signature_summary: dict[str, Any] | None = None,
    anchor_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failed = [check for check in checks if check.status == "fail"]
    invalid = any(check.failure_kind == "invalid_input" for check in failed)
    exit_code = 2 if invalid else 1 if failed else 0
    error_code = _alpha_error_code(failed)
    sig_perf = signature_status == "passed"
    anc_perf = anchor_status in {"passed", "quarantined"}
    return {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "error_code": error_code,
        "verification_scope": VERIFICATION_SCOPE,
        "input_path": str(path),
        "checks": [check.as_json() for check in checks],
        "summary": {
            "checks_passed": len(checks) - len(failed),
            "checks_failed": len(failed),
        },
        "network_access_performed": False,
        "signature_verification_requested": verify_signature,
        "signature_verification_performed": sig_perf,
        "signature_verification_status": signature_status,
        "signature_verification_summary": signature_summary,
        "signature_verification_claims": {
            "cryptographic_verification_performed": sig_perf,
            "certified_provenance": False,
            "production_supply_chain_security": False,
            "slsa_level_claimed": None,
        },
        "anchor_verification_requested": verify_anchor,
        "anchor_verification_performed": anc_perf,
        "anchor_verification_status": anchor_status,
        "anchor_verification_summary": anchor_summary,
        "anchor_verification_claims": {
            "anchor_verification_performed": anc_perf,
            "long_term_archival_trust": False,
            "legal_timestamp_attestation": False,
            "network_access_attempted": False,
        },
        # Back-compat scalar fields (kept identical to P3.1 shape so existing
        # consumers do not break).
        "compliance_certification": False,
        "production_ready": False,
        "certified_provenance": False,
        "slsa_level_claimed": None,
        "safe_claims": [
            "alpha local structural ProofBundle verifier",
            "fail-closed missing/tampered/unsupported detection",
            "deterministic JSON report",
            "no network access",
        ],
        "no_go_claims": [
            "not production-ready",
            "not compliance-ready",
            "not certification-ready",
            "not certified provenance",
            "not SLSA L3",
            "not production-grade supply-chain security",
            "not legal timestamp attestation",
            "not long-term archival trust guarantee",
            "alpha verifier does not perform cryptographic DSSE signature verification",
            "alpha verifier does not perform RFC-3161 anchor verification",
        ],
        "warning": (
            "Alpha local ProofBundle verifier: shape, hash, chain, obligation, "
            "storage compatibility, and provenance-shape checks only. It does not "
            "perform signature verification, anchor verification, network access, "
            "or compliance certification."
        ),
    }


def _alpha_error_code(failed: list[AlphaCheck]) -> VerifyErrorCode:
    if not failed:
        return VERIFY_OK
    first = failed[0]
    if first.failure_kind == "invalid_input":
        if first.name == "required_fields":
            return VERIFY_REQUIRED_FIELDS_MISSING
        if first.name in {"signature_verification", "anchor_verification"}:
            if first.detail and "unsupported" in first.detail:
                return VERIFY_EXTENSION_UNSUPPORTED
            return VERIFY_EXTENSION_INVALID_INPUT
        return VERIFY_SCHEMA_ERROR
    if first.name == "artifact_hash":
        return VERIFY_ARTIFACT_HASH_FAILED
    if first.name == "hash_chain_recompute":
        return VERIFY_CHAIN_RECOMPUTE_FAILED
    if first.name in {"signature_verification", "anchor_verification"}:
        return VERIFY_EXTENSION_FAILED
    return VERIFY_CHAIN_RECOMPUTE_FAILED


__all__ = [
    "ALPHA_ENVELOPE_SCHEMA_VERSION",
    "ANCHOR_TYPE_ALLOWLIST",
    "SIGNATURE_ALGORITHM_ALLOWLIST",
    "VERIFICATION_SCOPE",
    "verify_alpha_proofbundle_file",
]
