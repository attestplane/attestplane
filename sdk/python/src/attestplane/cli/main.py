# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""``attestplane`` CLI dispatch.

Subcommands::

    verify <bundle.json>           — chain/report-oriented proof-bundle check, exit 0/1
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
    )
    p_verify.add_argument("bundle", type=Path, help="path to bundle.json")
    _add_format_flag(p_verify)

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


def cmd_verify(args: argparse.Namespace) -> int:
    from attestplane.verifier import (
        BundleSchemaError,
        BundleVerificationError,
        verify_proof_bundle_file,
    )

    try:
        result = verify_proof_bundle_file(args.bundle)
    except BundleSchemaError as exc:
        _emit(
            {"ok": False, "error": "schema", "detail": str(exc), **_verify_scope_metadata()},
            args.json_output,
            human=f"FAIL: schema error in {args.bundle}: {exc}\n{VERIFY_SCOPE_NOTICE}",
        )
        return 1
    except BundleVerificationError as exc:
        _emit(
            {"ok": False, "error": "io", "detail": str(exc), **_verify_scope_metadata()},
            args.json_output,
            human=f"FAIL: cannot read {args.bundle}: {exc}\n{VERIFY_SCOPE_NOTICE}",
        )
        return 1

    payload = {
        "ok": result.ok,
        "chain_id": result.chain_id,
        "event_count": result.event_count,
        "head_hash_hex": result.head_hash_hex,
        "bundle_version": result.bundle_version,
        "agreement": result.agreement,
        "chain_result": {
            "ok": result.chain_result.ok,
            "first_bad_index": result.chain_result.first_bad_index,
            "reason": result.chain_result.reason,
        },
        "bundle_reported_ok": result.bundle_reported_ok,
        **_verify_scope_metadata(),
    }
    _emit(payload, args.json_output, human=f"{result.short_summary()}\n{VERIFY_SCOPE_NOTICE}")
    return 0 if result.ok else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    from attestplane.hashchain import verify_chain
    from attestplane.storage.base import StorageReadError
    from attestplane.storage.jsonl import JsonlStorageBackend

    backend = JsonlStorageBackend(args.chain)
    try:
        chain = backend.read_all()
    except StorageReadError as exc:
        _emit(
            {"ok": False, "error": "storage_read", "detail": str(exc)},
            args.json_output,
            human=f"FAIL: cannot read {args.chain}: {exc}",
        )
        return 1

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
    from attestplane.storage.base import StorageReadError
    from attestplane.storage.jsonl import JsonlStorageBackend

    backend = JsonlStorageBackend(args.chain)
    try:
        chain = backend.read_all()
    except StorageReadError as exc:
        _emit(
            {"ok": False, "error": "storage_read", "detail": str(exc)},
            args.json_output,
            human=f"FAIL: cannot read {args.chain}: {exc}",
        )
        return 1

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

    checks = {
        "python_version": platform.python_version(),
        "attestplane_version": __version__,
        "platform": platform.platform(),
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
