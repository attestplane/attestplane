# Attestplane Quickstart (5 minutes)

## What is Attestplane?

Provenance for AI agents — an open cryptographic evidence substrate.
**Pre-GA. Not GA. Not production-ready. Not a compliance certification.**
No certification claimed; no compliance opinion issued.

## Prerequisites

- **Python 3.11+** (3.12 recommended; see `sdk/python/pyproject.toml`).
- *Optional:* **Node.js 22+** if you want to mirror the same chain via the
  TypeScript SDK (this Quickstart only exercises the Python SDK).
- *Optional:* `cosign` and `slsa-verifier` if you later want to verify
  downstream **release artifacts** (wheels, sdists) per
  [docs/release/verifying-signatures.md](release/verifying-signatures.md).
  These are not required to run the snippet below.

## Install

```bash
pip install attestplane                # latest from PyPI
pip install attestplane==1.4.6         # pinned to current pre-GA (recommended)
```

**Pre-GA.** Pinned version recommended for reproducibility. Not GA. The exact
tag at the time of reading may have advanced; see
[CHANGELOG.md](../CHANGELOG.md) and the
[GitHub releases](https://github.com/attestplane/attestplane/releases) page.

## Three minimal events

Save as `quickstart.py` and run with `python quickstart.py`. This appends
three events of three different `event_type`s to an in-memory substrate,
persists them to a JSONL file, and prints the head + the in-process verify
result.

```python
from attestplane import (
    AttestSubstrate,
    EventDraft,
    JsonlStorageBackend,
    LEASE_LIFECYCLE_EVENT,
    POLICY_CHECK_EVENT,
    STATE_TRANSITION_EVENT,
)

sub = AttestSubstrate()
storage = JsonlStorageBackend("chain.jsonl")

drafts = [
    EventDraft(
        event_type=LEASE_LIFECYCLE_EVENT,
        actor="agent://demo/v1",
        payload={"lease_id": "lease-demo-0001", "phase": "acquired"},
    ),
    EventDraft(
        event_type=POLICY_CHECK_EVENT,
        actor="agent://demo/v1",
        payload={"policy_id": "demo.allow_read", "decision": "allow"},
    ),
    EventDraft(
        event_type=STATE_TRANSITION_EVENT,
        actor="agent://demo/v1",
        payload={"from": "idle", "to": "working"},
    ),
]

for draft in drafts:
    chained = sub.append(draft)
    storage.append(chained)

head = sub.tip()
result = sub.verify()
print(f"head_seq={head.seq} head_hash_hex={head.event_hash.hex()}")
print(f"verify ok={result.ok} first_bad_index={result.first_bad_index}")
```

Expected last two lines (the hash will differ — it's keyed off
substrate-assigned timestamps and UUIDv7 event ids):

```
head_seq=2 head_hash_hex=<64-hex-chars>
verify ok=True first_bad_index=None
```

`AttestSubstrate` has no `close()` method; the JSONL backend `fsync()`s on
every `append`, so the file is durable once the loop exits.

## Verify

Run the chain-only walker over the file you just wrote:

```bash
$ attestplane inspect chain.jsonl
path: chain.jsonl
event_count: 3
head_seq: 2
head_hash_hex: <64-hex-chars>
event_type_histogram: {'lease.lifecycle': 1, 'policy.check': 1, 'state.transition': 1}
verify: OK first_bad_index=None reason=None
```

`attestplane inspect` is the **chain-only walker**: it re-derives every
`event_hash`, re-walks the `prev_hash` links, and re-canonicalizes each
payload. It does **not** verify signatures, RFC-3161 anchors, or full
ProofBundle structure. For those, see
[docs/release/verifying-signatures.md](release/verifying-signatures.md)
(downstream artifact verification) and the `attestplane verify` /
ProofBundle paths documented under
[docs/architecture/verifier_independence.md](architecture/verifier_independence.md).

## Next steps

- **Audit posture** — [docs/spec/aia-12-aligned-profile.md](spec/aia-12-aligned-profile.md)
  describes the EU AI Act Article 12-aligned evidence profile.
- **Trust root model** — [docs/architecture/verifier_independence.md](architecture/verifier_independence.md)
  explains why a downstream verifier never has to trust the producing
  substrate.
- **Release artifact verification** — [docs/release/verifying-signatures.md](release/verifying-signatures.md)
  is the cosign + SLSA recipe for wheels/sdists.
- **Roadmap** — [docs/roadmap/USER_ROADMAP.md](roadmap/USER_ROADMAP.md)
  covers the v1.0 GA milestone (target 2026-08-15) and stability gates.
- **Contributing** — [CONTRIBUTING.md](../CONTRIBUTING.md) walks first-time
  contributors through DCO sign-off and the local test loop.
- **Security policy** — [SECURITY.md](../SECURITY.md) documents the
  vulnerability reporting channel and pre-GA disclosure expectations.

## Explicit non-claims

- This Quickstart is for **evaluation only**. Not GA. Not production-ready.
  Not a compliance certification.
- **No certification claimed**; no compliance opinion issued. References to
  EU AI Act, DORA, GDPR, ISO/IEC 42001, or NIST AI RMF describe *technical
  alignment targets* the substrate is designed toward, not third-party
  certifications.
- **Forward-only signing** per ADR-0018 applies to releases cut after that
  ADR (v1.0.8 was the first signed release; v1.0.9 was the first with
  complete cosign + SLSA provenance). Earlier releases are unsigned by
  design and re-signing them retroactively is explicitly out of scope.
- AP-EVD/1.0 makes **one positive claim** — byte-faithful evidence — and
  disclaims six others per ADR-0014 §11. Reviewers comparing Attestplane to
  a fully attested supply-chain product should read that section before
  drawing conclusions.
