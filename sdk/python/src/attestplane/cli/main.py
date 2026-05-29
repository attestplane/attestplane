# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""``attestplane`` CLI dispatch.

Subcommands::

    verify <bundle.json>           — chain/report-oriented proof-bundle check, exit 0/1/2/3
    verify-proofbundle <file.json> — alpha local ProofBundle verifier, JSON report, exit 0/1/2
    inspect <chain.jsonl>          — print a chain summary, exit 0/1
    export <chain.jsonl> --out OUT — build a proof bundle from a JSONL chain
    doctor                         — environment self-check, exit 0/1

All subcommands print human-readable text to stdout. Pass ``--json`` on
any subcommand to emit a structured JSON report instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from attestplane import __version__
from attestplane.cli.verify_json import (
    _verify_explanations,
    _verify_success_summary,
    build_verify_json_outcome,
    verify_result_exit_code,
)
from attestplane.verify_errors import (
    VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
    VERIFY_IO_ERROR,
    VERIFY_REQUIRED_FIELDS_MISSING,
    VERIFY_SCHEMA_ERROR,
)
from attestplane.verify_reason_codes import (
    VERIFY_REASON_CANONICAL_MISMATCH,
    VERIFY_REASON_SCHEMA_INVALID,
    VERIFY_REASON_SCHEMA_UNKNOWN,
)

VERIFY_SCOPE = "chain_report_only"
VERIFY_SCOPE_NOTICE = (
    "MODE: chain/report-oriented, not a full verifier. This command replays bundle events, "
    "compares the embedded verification_report with the recomputed chain result, and fails "
    "closed on malformed ProofBundle metadata and policy_trace_refs closure. It does not "
    "perform signature verification, anchor verification, or compliance certification."
)


def _verify_scope_metadata() -> dict[str, Any]:
    return {
        "verification_scope": VERIFY_SCOPE,
        "full_proof_bundle_verification": False,
        "proof_bundle_metadata_closure_performed": True,
        "policy_trace_refs_verification_performed": True,
        "signature_verification_performed": False,
        "anchor_verification_performed": False,
        "compliance_certification": False,
        "warning": VERIFY_SCOPE_NOTICE,
    }


def _add_format_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="emit structured JSON to stdout instead of human-readable text",
    )


def _add_explain_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--explain",
        action="store_true",
        help="include the derived reasons list in the verifier report",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="attestplane",
        description=(
            "Verifiable audit substrate CLI. See https://github.com/attestplane/attestplane for documentation."
        ),
    )
    parser.add_argument("--version", action="version", version=f"attestplane {__version__}")

    sub = parser.add_subparsers(dest="cmd", required=True, metavar="SUBCOMMAND")

    p_verify = sub.add_parser(
        "verify",
        help=(
            "chain/report-oriented proof-bundle check; not full ProofBundle, "
            "signature, anchor, or compliance verification"
        ),
        description=VERIFY_SCOPE_NOTICE,
        epilog=(
            "Exit codes: 0 success; 1 verification failure; 2 quarantine / "
            "fail-closed bundle rejection; 3 usage, I/O, or malformed input."
        ),
    )
    p_verify.add_argument("bundle", nargs="?", type=Path, help="path to bundle.json")
    p_verify.add_argument(
        "--bundle",
        dest="bundle_option",
        type=Path,
        help=(
            "path to bundle.json; enables strict proof-bundle schema mode "
            "(non-empty events plus at least one signed attestation)"
        ),
    )
    p_verify.add_argument(
        "--require-events",
        dest="require_events",
        action="store_true",
        help="fail closed when the proof bundle contains zero events",
    )
    p_verify.add_argument(
        "--require-non-empty",
        dest="require_non_empty",
        action="store_true",
        help=("enforce the proof-bundle contract that strict bundles contain at least one event"),
    )
    p_verify.add_argument(
        "--strict-schema",
        dest="strict_schema",
        action="store_true",
        help="enforce the proof-bundle contract's minimum signed-attestation schema",
    )
    _add_explain_flag(p_verify)
    _add_format_flag(p_verify)

    p_verify_pb = sub.add_parser(
        "verify-proofbundle",
        help="alpha local ProofBundle/evidence-bundle verifier; JSON report; no signature or anchor verification",
        description=(
            "Alpha local ProofBundle verifier. Checks local JSON shape, ProofBundle "
            "metadata closure, hash-chain recomputation, artifact hash, obligation "
            "references, in-toto/DSSE shape, storage compatibility metadata, and "
            "provenance-shape no-go claims. It performs no network access, signature "
            "verification, anchor verification, or compliance certification."
        ),
    )
    p_verify_pb.add_argument("bundle", type=Path, help="path to P3.1 ProofBundle verification envelope")
    p_verify_pb.add_argument(
        "--verify-signature",
        dest="verify_signature",
        action="store_true",
        help=(
            "P3.2 alpha extension: request fail-closed DSSE signature material "
            "inspection. Does NOT perform cryptographic signature verification — "
            "positive crypto path is deferred to a follow-up branch."
        ),
    )
    p_verify_pb.add_argument(
        "--verify-anchor",
        dest="verify_anchor",
        action="store_true",
        help=(
            "P3.2 alpha extension: request fail-closed RFC-3161 anchor material "
            "inspection. Does NOT perform RFC-3161 token verification, network "
            "access, or eIDAS qualified TSA selection — positive anchor path is "
            "deferred to a follow-up branch."
        ),
    )

    p_inspect = sub.add_parser("inspect", help="summarise a JSONL chain file")
    p_inspect.add_argument("chain", type=Path, help="path to chain.jsonl")
    _add_format_flag(p_inspect)

    p_export = sub.add_parser("export", help="build a proof bundle from a JSONL chain")
    p_export.add_argument("chain", type=Path, help="path to chain.jsonl")
    p_export.add_argument(
        "--out",
        "-o",
        type=Path,
        required=True,
        help="output path for the proof bundle JSON",
    )
    p_export.add_argument(
        "--chain-id",
        default="cli-export",
        help="chain_id to embed in the bundle metadata (default: 'cli-export')",
    )
    p_export.add_argument(
        "--producer-runtime",
        default="attestplane-cli",
        help="producer_runtime to embed (default: 'attestplane-cli')",
    )
    _add_format_flag(p_export)

    p_doctor = sub.add_parser("doctor", help="environment self-check")
    _add_format_flag(p_doctor)

    return parser


def _emit(payload: dict[str, Any], json_output: bool, *, human: str) -> None:
    if json_output:
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(human + "\n")


def _reason_entries(
    result: Any,
    *,
    bundle: dict[str, Any] | None = None,
    explain: bool = False,
) -> list[dict[str, str]]:
    reasons: list[dict[str, str]] = []
    for code in (result.primary_reason, *result.secondary_reasons):
        if code is None:
            continue
        reasons.append({"code": code, "severity": "error"})
    if explain and bundle is not None and result.ok:
        reasons.extend(_explain_reserved_reasons(bundle))
    return reasons


def _verify_human_summary(
    result: Any | None,
    *,
    bundle: dict[str, Any] | None = None,
    status: str,
) -> str:
    if bundle is None or result is None:
        return f"{status}"
    return f"{status} {_verify_success_summary(bundle)}"


def _write_verify_explanations(entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        primary_reason = entry.get("primary_reason")
        pointer = entry.get("pointer", "/")
        message = entry.get("message", "")
        prefix = primary_reason if primary_reason is not None else "ok"
        sys.stderr.write(f"{prefix} {pointer}: {message}\n")


_KNOWN_BUNDLE_TOP_LEVEL_FIELDS = {
    "bundle_version",
    "chain_metadata",
    "events",
    "verification_report",
    "forbidden_fields",
    "framework_mappings",
    "signature",
    "policy_trace_refs",
    "signatures",
    "retention_proofs",
}
_KNOWN_CHAIN_METADATA_FIELDS = {
    "chain_id",
    "genesis_hash_hex",
    "head_hash_hex",
    "head_seq",
    "producer_runtime",
    "schema_version",
    "anchor_ref",
    "evidence_taxonomy_version",
}
_KNOWN_VERIFICATION_REPORT_FIELDS = {
    "ok",
    "first_bad_index",
    "reason",
    "verified_at",
    "verifier_version",
    "verification_method",
}
_KNOWN_EVENT_ITEM_FIELDS = {
    "seq",
    "prev_hash_hex",
    "event_hash_hex",
    "event",
}
_KNOWN_AUDIT_EVENT_FIELDS = {
    "schema_version",
    "event_id",
    "timestamp",
    "event_type",
    "actor",
    "payload",
    "subject_ref",
    "session_id",
    "reference_db_ref",
    "matched_input_ref",
    "human_verifier",
}
_KNOWN_SUBJECT_REF_FIELDS = {"scheme", "value"}
_KNOWN_SIGNATURE_FIELDS = {
    "signature_schema_version",
    "signed_seq",
    "signed_event_hash_hex",
    "signature_hex",
    "key_id",
    "public_key_der_b64",
    "signing_cert_chain_b64",
    "signed_at",
    "signature_mode",
    "signed_payload_b64",
}
_KNOWN_RETENTION_PROOF_FIELDS = {
    "retention_proof_schema_version",
    "proof_id",
    "action",
    "target_event_hash_hex",
    "commit_event_hash_hex",
    "reason",
    "redacted_event_hash_hex",
}
_KNOWN_FRAMEWORK_MAPPING_FIELDS = {
    "obligation_id",
    "evidence_event_indexes",
    "implementation_status_at_bundle_time",
}


def _explain_reserved_reasons(bundle: dict[str, Any]) -> list[dict[str, str]]:
    extras: list[str] = []
    top_level_unknown = sorted(set(bundle) - _KNOWN_BUNDLE_TOP_LEVEL_FIELDS)
    if top_level_unknown:
        extras.extend(f"bundle.{key}" for key in top_level_unknown)
    chain_metadata = bundle.get("chain_metadata")
    if isinstance(chain_metadata, dict):
        for key in sorted(set(chain_metadata) - _KNOWN_CHAIN_METADATA_FIELDS):
            extras.append(f"chain_metadata.{key}")
    verification_report = bundle.get("verification_report")
    if isinstance(verification_report, dict):
        for key in sorted(set(verification_report) - _KNOWN_VERIFICATION_REPORT_FIELDS):
            extras.append(f"verification_report.{key}")
    framework_mappings = bundle.get("framework_mappings")
    if isinstance(framework_mappings, list):
        for index, mapping in enumerate(framework_mappings):
            if not isinstance(mapping, dict):
                continue
            for key in sorted(set(mapping) - _KNOWN_FRAMEWORK_MAPPING_FIELDS):
                extras.append(f"framework_mappings[{index}].{key}")
    events = bundle.get("events")
    if isinstance(events, list):
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            for key in sorted(set(event) - _KNOWN_EVENT_ITEM_FIELDS):
                extras.append(f"events[{index}].{key}")
            payload = event.get("event")
            if isinstance(payload, dict):
                _collect_nested_reserved_reasons(
                    payload,
                    f"events[{index}].event",
                    _KNOWN_AUDIT_EVENT_FIELDS,
                    extras,
                )
    signatures = bundle.get("signatures")
    if isinstance(signatures, list):
        for index, signature in enumerate(signatures):
            if isinstance(signature, dict):
                _collect_nested_reserved_reasons(
                    signature,
                    f"signatures[{index}]",
                    _KNOWN_SIGNATURE_FIELDS,
                    extras,
                )
    retention_proofs = bundle.get("retention_proofs")
    if isinstance(retention_proofs, list):
        for index, proof in enumerate(retention_proofs):
            if isinstance(proof, dict):
                _collect_nested_reserved_reasons(
                    proof,
                    f"retention_proofs[{index}]",
                    _KNOWN_RETENTION_PROOF_FIELDS,
                    extras,
                )
    if not extras:
        return []
    return [
        {
            "code": VERIFY_REASON_SCHEMA_UNKNOWN,
            "severity": "reserved",
            "detail": f"ignored additive fields: {', '.join(extras)}",
        }
    ]


def _collect_nested_reserved_reasons(
    obj: dict[str, Any],
    prefix: str,
    known_fields: set[str],
    extras: list[str],
) -> None:
    unknown = sorted(set(obj) - known_fields)
    for key in unknown:
        extras.append(f"{prefix}.{key}")
    if "subject_ref" in obj and isinstance(obj["subject_ref"], dict):
        _collect_nested_reserved_reasons(
            obj["subject_ref"],
            f"{prefix}.subject_ref",
            _KNOWN_SUBJECT_REF_FIELDS,
            extras,
        )
    if "human_verifier" in obj and isinstance(obj["human_verifier"], dict):
        _collect_nested_reserved_reasons(
            obj["human_verifier"],
            f"{prefix}.human_verifier",
            _KNOWN_SUBJECT_REF_FIELDS,
            extras,
        )


def cmd_verify(args: argparse.Namespace) -> int:
    from attestplane.canonical import CanonicalizationError
    from attestplane.verifier import (
        BundleSchemaError,
        classify_bundle_schema_error,
        verify_proof_bundle,
    )

    bundle_path = getattr(args, "bundle_option", None) or getattr(args, "bundle", None)
    if bundle_path is None:
        sys.stderr.write("attestplane verify: error: bundle path is required\n")
        return 2
    strict_bundle_mode = getattr(args, "bundle_option", None) is not None
    require_non_empty = (
        getattr(args, "require_non_empty", False) or getattr(args, "require_events", False) or strict_bundle_mode
    )
    strict_schema = getattr(args, "strict_schema", False) or strict_bundle_mode

    if args.json_output:
        outcome = build_verify_json_outcome(
            bundle_path,
            require_non_empty=require_non_empty,
            require_signed_attestation=strict_schema,
            explain=getattr(args, "explain", False),
        )
        _emit(outcome.payload, True, human="")
        if outcome.stderr_code is not None:
            sys.stderr.write(f"{outcome.stderr_code}\n")
        return outcome.exit_code

    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        result = verify_proof_bundle(
            bundle,
            require_non_empty=require_non_empty,
            require_signed_attestation=strict_schema,
        )
    except FileNotFoundError as exc:
        explain = getattr(args, "explain", False)
        human = f"FAIL: cannot read {bundle_path}: {exc}"
        if not explain:
            human = f"{human}\n{VERIFY_SCOPE_NOTICE}"
        _emit(
            {
                "ok": False,
                "error": "io",
                "error_code": VERIFY_IO_ERROR,
                "primary_reason": VERIFY_REASON_SCHEMA_INVALID,
                "secondary_reasons": [],
                "detail": str(exc),
                **_verify_scope_metadata(),
            },
            args.json_output,
            human=human,
        )
        if explain and not args.json_output:
            _write_verify_explanations(
                [
                    {
                        "primary_reason": VERIFY_REASON_SCHEMA_INVALID,
                        "pointer": "/",
                        "message": str(exc),
                    }
                ]
            )
        return 3
    except json.JSONDecodeError as exc:
        explain = getattr(args, "explain", False)
        human = f"FAIL: schema error in {bundle_path}: {exc}"
        if not explain:
            human = f"{human}\n{VERIFY_SCOPE_NOTICE}"
        _emit(
            {
                "ok": False,
                "error": "schema",
                "error_code": VERIFY_SCHEMA_ERROR,
                "primary_reason": VERIFY_REASON_SCHEMA_INVALID,
                "secondary_reasons": [],
                "detail": f"{bundle_path}: not valid JSON: {exc.msg}",
                **_verify_scope_metadata(),
            },
            args.json_output,
            human=human,
        )
        if explain and not args.json_output:
            _write_verify_explanations(
                [
                    {
                        "primary_reason": VERIFY_REASON_SCHEMA_INVALID,
                        "pointer": "/",
                        "message": f"{bundle_path}: not valid JSON: {exc.msg}",
                    }
                ]
            )
        return 3
    except BundleSchemaError as exc:
        explain = getattr(args, "explain", False)
        human = f"FAIL: schema error in {bundle_path}: {exc}"
        if not explain:
            human = f"{human}\n{VERIFY_SCOPE_NOTICE}"
        primary_reason = classify_bundle_schema_error(exc)
        _emit(
            {
                "ok": False,
                "error": "schema",
                "error_code": VERIFY_SCHEMA_ERROR,
                "primary_reason": primary_reason,
                "secondary_reasons": [],
                "detail": str(exc),
                **_verify_scope_metadata(),
            },
            args.json_output,
            human=human,
        )
        if explain and not args.json_output:
            _write_verify_explanations(
                [
                    {
                        "primary_reason": primary_reason,
                        "pointer": "/",
                        "message": str(exc),
                    }
                ]
            )
        return 2
    except CanonicalizationError as exc:
        explain = getattr(args, "explain", False)
        human = f"FAIL: canonicalization error in {bundle_path}: {exc}"
        if not explain:
            human = f"{human}\n{VERIFY_SCOPE_NOTICE}"
        _emit(
            {
                "ok": False,
                "error": "canonicalization",
                "error_code": VERIFY_SCHEMA_ERROR,
                "primary_reason": VERIFY_REASON_CANONICAL_MISMATCH,
                "secondary_reasons": [],
                "detail": str(exc),
                **_verify_scope_metadata(),
            },
            args.json_output,
            human=human,
        )
        if explain and not args.json_output:
            outcome = build_verify_json_outcome(
                bundle_path,
                require_non_empty=require_non_empty,
                require_signed_attestation=strict_schema,
                explain=True,
            )
            _write_verify_explanations(outcome.payload.get("explanation", []))
        return 1

    payload = {
        "ok": result.ok,
        "chain_id": result.chain_id,
        "event_count": result.event_count,
        "require_events": require_non_empty,
        "require_non_empty": require_non_empty,
        "strict_schema": strict_schema,
        "strict_proof_bundle_schema": strict_bundle_mode,
        "head_hash_hex": result.head_hash_hex,
        "bundle_version": result.bundle_version,
        "agreement": result.agreement,
        "chain_result": {
            "ok": result.chain_result.ok,
            "first_bad_index": result.chain_result.first_bad_index,
            "reason": result.chain_result.reason,
        },
        "bundle_reported_ok": result.bundle_reported_ok,
        "error_code": result.error_code,
        "primary_reason": result.primary_reason,
        "secondary_reasons": list(result.secondary_reasons),
        "reasons": _reason_entries(result, bundle=bundle, explain=getattr(args, "explain", False)),
        "retention_proofs_ok": result.retention_proofs_ok,
        "retention_proofs_reason": result.retention_proofs_reason,
        "signed_attestation_schema_ok": result.signed_attestation_schema_ok,
        "signed_attestation_schema_reason": result.signed_attestation_schema_reason,
        **_verify_scope_metadata(),
    }
    explain = getattr(args, "explain", False)
    if not result.ok and result.error_code in {
        VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
        VERIFY_REQUIRED_FIELDS_MISSING,
    }:
        sys.stderr.write(f"{result.error_code}\n")
    human = result.short_summary()
    if explain:
        human = _verify_human_summary(
            result,
            bundle=bundle,
            status="OK" if result.ok else "FAIL",
        )
    else:
        human = f"{human}\n{VERIFY_SCOPE_NOTICE}"
    _emit(payload, args.json_output, human=human)
    if explain and not args.json_output and not result.ok:
        _write_verify_explanations(_verify_explanations(result, bundle=bundle, explain=True))
    return verify_result_exit_code(result)


def cmd_verify_proofbundle(args: argparse.Namespace) -> int:
    from attestplane.cli.proofbundle_alpha import verify_alpha_proofbundle_file

    payload = verify_alpha_proofbundle_file(
        args.bundle,
        verify_signature=getattr(args, "verify_signature", False),
        verify_anchor=getattr(args, "verify_anchor", False),
    )
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return int(payload["exit_code"])


def cmd_inspect(args: argparse.Namespace) -> int:
    from attestplane.hashchain import verify_chain
    from attestplane.storage.jsonl import JsonlStorageBackend

    backend = JsonlStorageBackend(args.chain)
    scan = backend.scan()
    if scan.issues:
        issue = scan.issues[0]
        _emit(
            {
                "ok": False,
                "error": "storage_corruption",
                "storage_health": "corrupt",
                "valid_prefix_event_count": len(scan.events),
                "issue": {
                    "kind": issue.kind,
                    "line_no": issue.line_no,
                    "byte_offset": issue.byte_offset,
                    "detail": issue.detail,
                },
            },
            args.json_output,
            human=(
                f"FAIL: storage corruption in {args.chain}: "
                f"{issue.kind} at line {issue.line_no} byte {issue.byte_offset}: "
                f"{issue.detail}"
            ),
        )
        return 1
    chain = list(scan.events)

    result = verify_chain(chain)
    event_types: dict[str, int] = {}
    for ev in chain:
        event_types[ev.event.event_type] = event_types.get(ev.event.event_type, 0) + 1

    payload = {
        "ok": result.ok,
        "path": str(args.chain),
        "event_count": len(chain),
        "head_seq": chain[-1].seq if chain else -1,
        "head_hash_hex": chain[-1].event_hash.hex() if chain else ("0" * 64),
        "event_type_histogram": event_types,
        "first_bad_index": result.first_bad_index,
        "reason": result.reason,
        "storage_health": "ok",
        "valid_prefix_event_count": len(chain),
    }
    if args.json_output:
        _emit(payload, True, human="")
    else:
        lines = [
            f"path: {args.chain}",
            f"event_count: {len(chain)}",
            f"head_seq: {payload['head_seq']}",
            f"head_hash_hex: {payload['head_hash_hex']}",
            f"event_type_histogram: {event_types}",
            f"verify: {'OK' if result.ok else 'FAIL'} "
            f"first_bad_index={result.first_bad_index} reason={result.reason!r}",
        ]
        _emit(payload, False, human="\n".join(lines))
    return 0 if result.ok else 1


def cmd_export(args: argparse.Namespace) -> int:
    from attestplane.proof_bundle import ProofBundleBuilder
    from attestplane.storage.jsonl import JsonlStorageBackend

    backend = JsonlStorageBackend(args.chain)
    scan = backend.scan()
    if scan.issues:
        issue = scan.issues[0]
        _emit(
            {
                "ok": False,
                "error": "storage_corruption",
                "storage_health": "corrupt",
                "valid_prefix_event_count": len(scan.events),
                "issue": {
                    "kind": issue.kind,
                    "line_no": issue.line_no,
                    "byte_offset": issue.byte_offset,
                    "detail": issue.detail,
                },
            },
            args.json_output,
            human=(
                f"FAIL: refusing export from corrupt storage {args.chain}: "
                f"{issue.kind} at line {issue.line_no} byte {issue.byte_offset}: "
                f"{issue.detail}"
            ),
        )
        return 1
    chain = list(scan.events)

    builder = ProofBundleBuilder(
        chain_id=args.chain_id,
        producer_runtime=args.producer_runtime,
    )
    builder.extend(chain)
    bundle = builder.build()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    payload = {
        "ok": bundle["verification_report"]["ok"],
        "out": str(args.out),
        "event_count": len(chain),
        "chain_id": args.chain_id,
        "head_hash_hex": bundle["chain_metadata"]["head_hash_hex"],
        "storage_health": "ok",
    }
    _emit(
        payload,
        args.json_output,
        human=(
            f"wrote {args.out} ({len(chain)} events, "
            f"head={bundle['chain_metadata']['head_hash_hex'][:16]}…, "
            f"verify={'OK' if payload['ok'] else 'FAIL'})"
        ),
    )
    return 0 if payload["ok"] else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    import platform

    from attestplane.storage.jsonl import JsonlStorageBackend

    checks = {
        "python_version": platform.python_version(),
        "attestplane_version": __version__,
        "platform": platform.platform(),
        "storage": JsonlStorageBackend(":memory:").health_report()
        | {
            "path": None,
        },
    }
    payload: dict[str, Any] = {"ok": True, **checks}

    # Lightweight import smoke-test — surfaces install corruption.
    try:
        import attestplane
        import attestplane.adapters
        import attestplane.event_types
        import attestplane.obligations
        import attestplane.proof_bundle
        import attestplane.storage
        import attestplane.verifier

        payload["imports"] = "ok"
        payload["package_root"] = attestplane.__file__
    except ImportError as exc:
        payload["ok"] = False
        payload["imports"] = "failed"
        payload["error"] = str(exc)

    # Sanity-check that the EU AI Act registry loads.
    try:
        from attestplane.obligations import load_eu_ai_act_article_12

        reg = load_eu_ai_act_article_12()
        payload["eu_ai_act_art12_entries"] = len(reg.entries)
    except Exception as exc:
        payload["ok"] = False
        payload["eu_ai_act_art12_entries"] = "failed"
        payload["registry_error"] = str(exc)

    if args.json_output:
        _emit(payload, True, human="")
    else:
        lines = [f"{k}: {v}" for k, v in payload.items()]
        _emit(payload, False, human="\n".join(lines))
    return 0 if payload["ok"] else 1


_DISPATCH = {
    "verify": cmd_verify,
    "verify-proofbundle": cmd_verify_proofbundle,
    "inspect": cmd_inspect,
    "export": cmd_export,
    "doctor": cmd_doctor,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return _DISPATCH[args.cmd](args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
