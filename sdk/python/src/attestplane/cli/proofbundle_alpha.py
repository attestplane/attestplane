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

ALPHA_ENVELOPE_SCHEMA_VERSION = 1
VERIFICATION_SCOPE = "proofbundle_alpha_local"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

CheckStatus = Literal["pass", "fail"]
FailureKind = Literal["verification_failed", "invalid_input"]


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
            result.chain_result.reason
            or result.metadata_reason
            or result.policy_trace_refs_reason
            or "bundle failed"
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


def verify_alpha_proofbundle_file(path: Path) -> dict[str, Any]:
    """Verify a local P3.1 ProofBundle verification envelope.

    Returns a machine-readable report. ``exit_code`` follows the CLI contract:
    0 valid, 1 verification failed, 2 invalid input/malformed/unsupported.
    """
    checks: list[AlphaCheck] = []
    root, parse_check = _load_json(path)
    checks.append(parse_check)
    if parse_check.status == "fail":
        return _report(path, checks)

    root_dict, shape_check = _check_root_shape(root)
    checks.append(shape_check)
    if root_dict is None:
        return _report(path, checks)

    checks.append(_check_schema_version(root_dict))
    proof_bundle, proof_checks = _check_proof_bundle(root_dict)
    checks.extend(proof_checks)
    checks.extend([
        _check_artifact(root_dict),
        _check_hash_chain(root_dict, proof_bundle),
        _check_obligation_refs(root_dict, proof_bundle),
        _check_in_toto_statement(root_dict, proof_bundle),
        _check_dsse_envelope(root_dict),
        _check_storage_compatibility(root_dict),
        _check_provenance(root_dict),
    ])
    return _report(path, checks)


def _report(path: Path, checks: list[AlphaCheck]) -> dict[str, Any]:
    failed = [check for check in checks if check.status == "fail"]
    invalid = any(check.failure_kind == "invalid_input" for check in failed)
    exit_code = 2 if invalid else 1 if failed else 0
    return {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "verification_scope": VERIFICATION_SCOPE,
        "input_path": str(path),
        "checks": [check.as_json() for check in checks],
        "summary": {
            "checks_passed": len(checks) - len(failed),
            "checks_failed": len(failed),
        },
        "network_access_performed": False,
        "signature_verification_performed": False,
        "anchor_verification_performed": False,
        "compliance_certification": False,
        "production_ready": False,
        "certified_provenance": False,
        "slsa_level_claimed": None,
        "warning": (
            "Alpha local ProofBundle verifier: shape, hash, chain, obligation, "
            "storage compatibility, and provenance-shape checks only. It does not "
            "perform signature verification, anchor verification, network access, "
            "or compliance certification."
        ),
    }


__all__ = [
    "ALPHA_ENVELOPE_SCHEMA_VERSION",
    "VERIFICATION_SCOPE",
    "verify_alpha_proofbundle_file",
]
