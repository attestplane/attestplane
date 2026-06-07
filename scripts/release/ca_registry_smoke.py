#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Clean-install smoke for a *published* attestplane release.

Evidence for the Controlled Availability admission criteria (#3 clean-install
smoke and the verifier portion of #4), run against the package installed from
PyPI — not a source checkout.

It imports only the public API. Modes:
  * ``smoke [EXPECTED_VERSION]`` (default): assert the import resolves to a
    site-packages install (not source) and, when a version is given, that
    ``__version__`` matches it (catches a stale-literal version drift); build a
    bundle and verify it -> ok; tamper it and verify -> rejected (claim-safety
    invariant: a mutated bundle must never verify ok).
  * ``emit <PATH>``: write a valid bundle JSON for the cross-SDK roundtrip
    (the *other* SDK, installed from its registry, verifies it).
  * ``verify <PATH>``: verify a bundle JSON produced by the other SDK -> ok.

This is intentionally a focused public-surface smoke, not the full source
conformance suite (whose vectors are not shipped in the wheel). The byte-frozen
conformance suite runs against source in CI, and the published wheel is the
byte-identical reproducible build of that source.

Usage:
    python ca_registry_smoke.py [smoke [EXPECTED_VERSION] | emit PATH | verify PATH]
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import attestplane


def _fail(msg: str) -> int:
    print(f"::error::{msg}", file=sys.stderr)
    return 1


def _build_valid_bundle() -> dict:
    from attestplane import AttestSubstrate, EventDraft, ProofBundleBuilder

    sub = AttestSubstrate()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    chain = [sub.append(EventDraft(event_type="eval_event", actor="agent", payload={"i": 0}), now=base)]
    builder = ProofBundleBuilder(chain_id="ca-smoke", producer_runtime="ca-smoke")
    builder.extend(chain)
    return builder.build(now=base)


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "smoke"
    from attestplane import verify_proof_bundle

    if mode == "emit":
        if len(argv) < 3:
            return _fail("emit requires an output path")
        Path(argv[2]).write_text(json.dumps(_build_valid_bundle()), encoding="utf-8")
        print(f"CA emit OK: wrote bundle to {argv[2]}")
        return 0

    if mode == "verify":
        if len(argv) < 3:
            return _fail("verify requires an input path")
        bundle = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        result = verify_proof_bundle(bundle)
        if not result.ok:
            return _fail(f"cross-SDK bundle failed verification: {result}")
        print(f"CA cross-verify OK: attestplane {attestplane.__version__} verified {argv[2]}")
        return 0

    # Default: self smoke. Accept "smoke [VERSION]" or a bare "[VERSION]".
    if mode == "smoke":
        expected = argv[2] if len(argv) > 2 else None
    else:
        expected = mode  # bare version argument

    # 1. Identity guard: must be the installed wheel, never a source tree.
    location = attestplane.__file__
    if "site-packages" not in location:
        return _fail(f"attestplane resolved to non-install path: {location}")
    if expected is not None and attestplane.__version__ != expected:
        return _fail(
            f"attestplane.__version__ {attestplane.__version__!r} "
            f"!= expected {expected!r} (version drift)"
        )
    if attestplane.__version__ == "0.0.0+unknown":
        return _fail("attestplane.__version__ is the dist-info-missing sentinel")

    # 2. Build a valid bundle with the public API and verify -> ok.
    bundle = _build_valid_bundle()
    if not verify_proof_bundle(bundle).ok:
        return _fail("valid bundle failed verification")

    # 3. Tamper -> reject (claim-safety: a mutated bundle must not verify ok).
    tampered = copy.deepcopy(bundle)
    tampered["events"][0]["event"]["payload"]["i"] = 999
    if verify_proof_bundle(tampered).ok:
        return _fail("tampered bundle verified ok (claim-safety broken)")

    print(
        f"CA registry smoke OK: attestplane {attestplane.__version__} @ {location} "
        f"(valid->ok, tampered->rejected)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
