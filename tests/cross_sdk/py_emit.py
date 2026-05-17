# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Cross-SDK round-trip: Python emitter (step 1 of 3).

Reads ``corpus.json``, applies the Python SDK canonicalizers, and writes
``py_emit.json`` with the canonical bytes (base64-encoded) and SHA-256 hex
hash of every test case. The TypeScript step then loads this file and must
reproduce byte-for-byte identical output, proving the two SDKs do not
silently diverge.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

from attestplane import canonicalize, canonicalize_text


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main(corpus_path: Path, out_path: Path) -> None:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    result: dict[str, list[dict[str, str]]] = {"canonical_text": [], "canonical_json": []}

    for case in corpus["canonical_text"]:
        bytes_out = canonicalize_text(case["text"])
        result["canonical_text"].append(
            {
                "id": case["id"],
                "canonical_b64": base64.b64encode(bytes_out).decode("ascii"),
                "hash_hex": sha256_hex(bytes_out),
            }
        )

    for case in corpus["canonical_json"]:
        bytes_out = canonicalize(case["value"])
        result["canonical_json"].append(
            {
                "id": case["id"],
                "canonical_b64": base64.b64encode(bytes_out).decode("ascii"),
                "hash_hex": sha256_hex(bytes_out),
            }
        )

    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Python SDK emitted {len(result['canonical_text'])} text + "
          f"{len(result['canonical_json'])} JSON canonical outputs to {out_path}")


if __name__ == "__main__":
    here = Path(__file__).parent
    main(here / "corpus.json", here / "py_emit.json")
    sys.exit(0)
