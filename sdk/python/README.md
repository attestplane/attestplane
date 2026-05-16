# attestplane — Python SDK

Verifiable audit substrate for AI agents. EU AI Act Article 12 ready.

> **Status: alpha (v0.0.1).** APIs may change before v0.1.0. The canonical
> hash format and conformance vectors, however, are frozen — see [ADR-0002][adr2].

See the [project README][project-readme] for background, governance, and
trademark policy. The full design rationale for this SDK lives in [ADR-0002][adr2].

[project-readme]: https://github.com/attestplane/attestplane
[adr2]: https://github.com/attestplane/attestplane/blob/main/docs/adr/0002-substrate-data-model-and-hash-chain-v0.md

## Install

```bash
pip install attestplane
```

Requires Python ≥ 3.11.

## Quickstart

```python
from attestplane import AttestSubstrate, EventDraft, SubjectRef

sub = AttestSubstrate()

sub.append(
    EventDraft(
        event_type="ai_decision",
        actor="agent://recsys/v1",
        payload={"outcome": "approved", "confidence_bp": 9120},
        session_id="session-2026-05-17-abc",
        subject_ref=SubjectRef(scheme="sha256_salted", value="2c1b...e9"),
    )
)

print(sub.tip())            # ChainHead(seq=0, event_hash=...)
assert sub.verify().ok      # True
```

## What this SDK gives you

- An **append-only** audit log with cryptographic integrity (SHA-256 hash chain).
- Built-in **EU AI Act Art. 12(2)(a)** field coverage from day one.
- A **deterministic canonical format** that future TypeScript and Rust SDKs
  will produce byte-identical hashes for, anchored by the conformance vector
  file shipped in this package.
- Strong **GDPR pseudonymization typing** via `SubjectRef`.

## What this SDK does NOT give you (yet)

| Feature | Where |
|---|---|
| Durable storage | Anticipated ADR-0004 (M6) — bring your own DB |
| Multi-process concurrency | Anticipated ADR-0004 — single-process for v0.0.1 |
| RFC 3161 TSA anchoring | Anticipated ADR-0003 (M6) |
| Rekor / Sigstore submission | M6 |
| Cryptographic signatures on events | Anticipated ADR-0005 (M7) |
| Retention / truncation policy | Out of scope — deployer responsibility |

## EU AI Act Article 12(2)(a) mapping

The four enumerated subitems of Art. 12(2)(a) are surfaced as `EventDraft`
fields. All are optional in v0.0.1 — populate the ones your use case requires.

| Art. 12(2)(a) language | `EventDraft` field | Type |
|---|---|---|
| "period of each use of the system" | `session_id` | `str \| None` |
| "the reference database against which input data has been checked by the system" | `reference_db_ref` | `str \| None` |
| "the input data for which the search has resulted in a match" | `matched_input_ref` | `str \| None` |
| "the identification of the natural persons involved in the verification of the results" | `human_verifier` | `SubjectRef \| None` |

These are **references**, not the data itself. A real reference database or
matched input must not be inlined into the audit log — that would violate
GDPR Art. 5(1)(c) data minimization. Store the data elsewhere (object storage,
hashed lookup table) and put a stable, content-addressed identifier here.

## Restricted JSON profile

To make Python, TypeScript, and Rust SDKs produce byte-identical hashes,
canonicalization is stricter than vanilla JCS (RFC 8785):

| Allowed in `payload` | Forbidden in `payload` |
|---|---|
| UTF-8 NFC strings | Other Unicode normalization forms |
| Signed-int64 integers | Floats, NaN, ±Inf, ±0 |
| `True` / `False` / `None` | — |
| `dict` (string keys, sorted on emit) | Non-string keys; duplicate keys |
| `list` / `tuple` (order preserved) | — |
| `bytes` (emitted as base64url, no padding) | Raw bytes |
| `datetime` (RFC 3339 UTC microsecond, `Z` suffix) | Naive datetimes; non-UTC offsets |

Violations raise `CanonicalizationError` at append time.

If you need to record a real-valued measurement, multiply into a fixed-point
integer (e.g., basis points, microseconds, microcents) and document the unit.

## Conformance vectors

Ten golden `(EventDraft → event_hash hex)` pairs live in
[`tests/conformance/vectors.json`](tests/conformance/vectors.json). These
values are a **permanent external contract**:

- An auditor can re-implement canonicalization from ADR-0002 alone and verify
  against this file without trusting any SDK code.
- TypeScript and Rust SDKs (M6, M7) MUST produce identical hex for the same
  inputs, or the release is blocked.
- The file is frozen for `schema_version = 1`. Adding fields requires a new
  `schema_version` and a new vector set under a separate filename; the
  existing vectors stay valid forever.

The CI conformance test re-derives each hex on every run, so accidental
canonicalization drift fails the build immediately.

## Threading and processes

`AttestSubstrate` is safe for concurrent use from multiple threads of the same
process. It is **not** safe across process boundaries — it holds no durable
storage and uses a process-local lock. Multi-process / multi-machine backends
are deferred to ADR-0004 (anticipated M6).

## Development

```bash
git clone https://github.com/attestplane/attestplane
cd attestplane/sdk/python
uv venv --python 3.12
. .venv/bin/activate
uv pip install -e '.[dev]'

pytest                  # unit tests + conformance vectors
mypy                    # strict type check
ruff check src tests    # lint
```

Coverage gate: ≥ 90 % (currently ~ 98 %).

Type check is `mypy --strict`. The public API is fully type-annotated; consumers
should expect type checks against this package to be precise.

## License

Apache License 2.0. See [LICENSE](https://github.com/attestplane/attestplane/blob/main/LICENSE)
and [NOTICE](https://github.com/attestplane/attestplane/blob/main/NOTICE) at
the project root.

## Reporting issues

- **Bugs / feature requests:** https://github.com/attestplane/attestplane/issues
- **Security vulnerabilities:** see [SECURITY.md](https://github.com/attestplane/attestplane/blob/main/SECURITY.md) — do not open public issues.
- **Trademark questions:** see [TRADEMARK.md](https://github.com/attestplane/attestplane/blob/main/TRADEMARK.md).
