# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""``attestplane`` CLI dispatch.

Subcommands::

    verify <bundle.json>           — chain/report-oriented proof-bundle check, exit 0/1/2
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
from attestplane.verify_errors import (
    VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
    VERIFY_IO_ERROR,
    VERIFY_REQUIRED_FIELDS_MISSING,
    VERIFY_SCHEMA_ERROR,
)
from attestplane.verify_reason_codes import VERIFY_REASON_SCHEMA_INVALID

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
        help="show a human-oriented explanation of schema-version and verifier decisions",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="attestplane",
        description=(
            "Verifiable audit substrate CLI. See "
            "https://github.com/attestplane/attestplane for documentation."
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
            "Exit codes: 0 success; 2 proof-bundle contract schema/non-empty "
            "violation; 1 cryptographic, chain-integrity, I/O, or other "
            "verification failure."
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
        help=(
            "enforce the proof-bundle contract that strict bundles contain "
            "at least one event"
        ),
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
        "--out", "-o", type=Path, required=True,
        help="output path for the proof bundle JSON",
    )
    p_export.add_argument(
        "--chain-id", default="cli-export",
        help="chain_id to embed in the bundle metadata (default: 'cli-export')",
    )
    p_export.add_argument(
        "--producer-runtime", default="attestplane-cli",
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


def _schema_version_explain_lines(result: Any) -> list[str]:
    lines: list[str] = []
    if getattr(result, "schema_version_forward_compat", False):
        lines.append(
            "schema_version_forward_compat: true "
            f"(bundle schema_version {result.schema_version} exceeds supported 1.7; "
            "unknown top-level additions accepted)"
        )
    return lines


def cmd_verify(args: argparse.Namespace) -> int:
    from attestplane.verifier import (
        BundleSchemaError,
        BundleVerificationError,
        classify_bundle_schema_error,
        verify_proof_bundle_file,
    )

    bundle_path = getattr(args, "bundle_option", None) or getattr(args, "bundle", None)
    if bundle_path is None:
        sys.stderr.write("attestplane verify: error: bundle path is required\n")
        return 2
    strict_bundle_mode = getattr(args, "bundle_option", None) is not None
    require_non_empty = (
        getattr(args, "require_non_empty", False)
        or getattr(args, "require_events", False)
        or strict_bundle_mode
    )
    strict_schema = getattr(args, "strict_schema", False) or strict_bundle_mode

    try:
        result = verify_proof_bundle_file(
            bundle_path,
            require_non_empty=require_non_empty,
            require_signed_attestation=strict_schema,
        )
    except BundleSchemaError as exc:
        payload = {
            "result": "reject",
            "ok": False,
            "error": "schema",
            "error_code": VERIFY_SCHEMA_ERROR,
            "primary_reason": classify_bundle_schema_error(exc),
            "secondary_reasons": [],
            "detail": str(exc),
            "schema_version_forward_compat": False,
            **_verify_scope_metadata(),
        }
        _emit(
            payload,
            args.json_output,
            human=f"FAIL: schema error in {bundle_path}: {exc}\n{VERIFY_SCOPE_NOTICE}",
        )
        return 2
    except BundleVerificationError as exc:
        payload = {
            "result": "reject",
            "ok": False,
            "error": "io",
            "error_code": VERIFY_IO_ERROR,
            "primary_reason": VERIFY_REASON_SCHEMA_INVALID,
            "secondary_reasons": [],
            "detail": str(exc),
            "schema_version_forward_compat": False,
            **_verify_scope_metadata(),
        }
        _emit(
            payload,
            args.json_output,
            human=f"FAIL: cannot read {bundle_path}: {exc}\n{VERIFY_SCOPE_NOTICE}",
        )
        return 1

    explain_lines = _schema_version_explain_lines(result) if getattr(args, "explain", False) else []
    payload = {
        "result": "accept" if result.ok else "reject",
        "ok": result.ok,
        "chain_id": result.chain_id,
        "event_count": result.event_count,
        "require_events": require_non_empty,
        "require_non_empty": require_non_empty,
        "strict_schema": strict_schema,
        "strict_proof_bundle_schema": strict_bundle_mode,
        "head_hash_hex": result.head_hash_hex,
        "bundle_version": result.bundle_version,
        "schema_version": result.schema_version,
        "schema_version_forward_compat": result.schema_version_forward_compat,
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
        "retention_proofs_ok": result.retention_proofs_ok,
        "retention_proofs_reason": result.retention_proofs_reason,
        "signed_attestation_schema_ok": result.signed_attestation_schema_ok,
        "signed_attestation_schema_reason": result.signed_attestation_schema_reason,
        **_verify_scope_metadata(),
    }
    if not result.ok and result.error_code in {
        VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
        VERIFY_REQUIRED_FIELDS_MISSING,
    }:
        sys.stderr.write(f"{result.error_code}\n")
    human_lines = [result.short_summary(), VERIFY_SCOPE_NOTICE]
    human_lines.extend(explain_lines)
    _emit(payload, args.json_output, human="\n".join(human_lines))
    if result.ok:
        return 0
    if result.error_code in {
        VERIFY_BUNDLE_SCHEMA_INCOMPLETE,
        VERIFY_REQUIRED_FIELDS_MISSING,
    }:
        return 2
    return 1


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
        "storage": JsonlStorageBackend(":memory:").health_report() | {
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
