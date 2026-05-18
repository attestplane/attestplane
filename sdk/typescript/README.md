# @attestplane/attestplane — TypeScript SDK

Apache-2.0 attestation and audit substrate for AI agent evidence chains.

> **Status: alpha (v0.0.1).** Wire format is byte-locked against the Python
> SDK's [`vectors.json`](../python/tests/conformance/vectors.json) — see
> [ADR-0002][adr2]. APIs may still change before v0.1.0.
> The current Python CLI `attestplane verify` path is chain/report-oriented
> only. It does not perform full ProofBundle, signature, anchor,
> `policy_trace_refs`, or compliance certification verification.

See the [project README][project-readme] for background, governance, and
trademark policy.

[project-readme]: https://github.com/attestplane/attestplane
[adr2]: https://github.com/attestplane/attestplane/blob/main/docs/adr/0002-substrate-data-model-and-hash-chain-v0.md

## Install

```bash
# Pin the alpha explicitly; v0.0.1 is on the 'alpha' dist-tag.
npm install @attestplane/attestplane@alpha
# or, equivalent:
npm install @attestplane/attestplane@0.0.1
```

`npm install @attestplane/attestplane` without a tag also resolves to
0.0.1 today (because it is the only published version) but treat the
alpha tag as the authoritative pre-release channel until v0.1.0 ships.

Requires Node.js ≥ 22.

## Quickstart

```typescript
import {
  AttestSubstrate,
  makeEventDraft,
  makeSubjectRef,
} from '@attestplane/attestplane';

const sub = new AttestSubstrate();

sub.append(
  makeEventDraft({
    event_type: 'ai_decision',
    actor: 'agent://recsys/v1',
    payload: { outcome: 'approved', confidence_bp: 9120 },
    session_id: 'session-2026-05-17-abc',
    subject_ref: makeSubjectRef('sha256_salted', '2c1b...e9'),
  }),
);

console.log(sub.tip());        // { seq: 0, event_hash: Uint8Array(32) [...] }
console.log(sub.verify().ok);  // true
```

## Cross-language conformance

This SDK is validated against the same `vectors.json` as the Python SDK on
every CI run. Identical input ⇒ identical `event_hash`. If you compute an
event hash in this SDK and store it, the Python SDK (and any future Rust SDK)
will reproduce the exact byte value from the same input.

## What this SDK gives you

- An **append-only** audit log with cryptographic integrity (SHA-256 hash chain).
- Built-in fields designed toward **EU AI Act Art. 12(2)(a)** auditability from day one.
- Byte-identical canonical format compatible with the Python SDK.
- Strong **GDPR pseudonymization typing** via `SubjectRef`.
- Alpha-grade verifier predicates; do not treat this SDK as production-ready
  governance, compliance certification, or runtime execution authority.

## API conventions

Field names use `snake_case` (e.g., `event_type`, `prev_hash`, `subject_ref`)
to match the canonical wire format exactly. This is a deliberate choice for
cross-language conformance: the canonical form embeds the field names, so any
rename here would break the conformance contract. See [`src/types.ts`][types].

[types]: src/types.ts

## Restricted JSON profile

Payloads must satisfy the restricted profile of ADR-0002:

| Allowed in `payload` | Forbidden |
|---|---|
| `string` (NFC-normalized UTF-8) | non-NFC strings |
| `number` (integer, safe range) | floats, `NaN`, `Infinity` |
| `bigint` (within signed 64-bit range) | bigint outside int64 |
| `true` / `false` / `null` | — |
| plain objects (string keys) | non-string keys; duplicate keys |
| arrays | — |
| `Uint8Array` (emits as base64url no padding) | other byte types |
| `Date` (UTC, encoded as RFC 3339 µs `Z`) | invalid Date |

Violations throw `CanonicalizationError` at append time.

For sub-millisecond precision, encode the timestamp as a string (JS `Date`
only stores millisecond resolution).

## Development

```bash
git clone https://github.com/attestplane/attestplane
cd attestplane/sdk/typescript
npm install

npm run lint        # Biome lint + format check
npm run typecheck   # tsc --noEmit strict
npm test            # vitest, includes cross-language conformance
npm run build       # emit dist/
```

## License

Apache License 2.0. See [LICENSE](https://github.com/attestplane/attestplane/blob/main/LICENSE)
and [NOTICE](https://github.com/attestplane/attestplane/blob/main/NOTICE).
