# SPDX-FileCopyrightText: 2026 The Attestplane Authors
# SPDX-License-Identifier: Apache-2.0
"""Emit a strict-valid minimum proof bundle as JSON."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import sys

from attestplane.canonical import canonicalize
from attestplane.proof_bundle import ProofBundleBuilder
from attestplane.types import ChainedEvent

_SUBJECT_DIGEST = "3f551d9" + "0" * 57
_FIXED_NOW = datetime(2026, 5, 22, 0, 0, 0, tzinfo=UTC)
_FIXED_EVENT_ID = "00000000-0000-7000-8000-000000000137"


@dataclass(frozen=True, slots=True)
class _ExampleSignatureRecord:
    signature_schema_version: int
    signed_seq: int
    signed_event_hash: bytes
    signature: bytes
    key_id: str
    public_key_der: bytes
    signing_cert_chain: tuple[bytes, ...]
    signed_at: datetime
    signature_mode: str
    signed_payload: bytes


class _ExampleSigner:
    _chain_id = "attestplane-sdk-minimum-example"

    def sign_event(self, event: ChainedEvent) -> list[_ExampleSignatureRecord]:
        return [
            _ExampleSignatureRecord(
                signature_schema_version=1,
                signed_seq=event.seq,
                signed_event_hash=event.event_hash,
                signature=b"\x13" * 64,
                key_id="13" * 16,
                public_key_der=b"attestplane-example-public-key",
                signing_cert_chain=(),
                signed_at=_FIXED_NOW,
                signature_mode="per_event",
                signed_payload=canonicalize(event.event),
            )
        ]


def build_example_bundle() -> dict[str, object]:
    return ProofBundleBuilder.minimal(
        _SUBJECT_DIGEST,
        _ExampleSigner(),
        now=_FIXED_NOW,
        event_id=_FIXED_EVENT_ID,
    )


def main() -> int:
    json.dump(build_example_bundle(), sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
