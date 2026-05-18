# Public API Surface Sweep — 2026-05-18

## Scope

This is a release-hardening snapshot, not a permanent API-diff gate. It checks
the Python root package exports, TypeScript root package exports, documented
README symbols, package metadata, and obvious Py/TS asymmetries for the
v0.0.2-alpha final readiness sweep.

## Python Surface

Python exposes the stable substrate primitives, event types, payload validators,
verifier predicates, proof bundle builder, storage backend, obligation registry
loaders, adapter primitives, and optional sidecar symbols when their extras are
installed.

The root `attestplane.__all__` is now conditional for optional signing symbols.
When `cryptography`, `asn1crypto`, and `yaml` are absent, `import attestplane`
still succeeds and `__all__` contains only defined names.

## TypeScript Surface

The TypeScript package metadata points at `dist/index.js` and
`dist/index.d.ts`, with root ESM export `"."`. The root `src/index.ts` exports
the documented quickstart symbols and the proof-bundle/verifier predicates used
in the v0.0.2-alpha release notes.

## Documented Symbols Checked

- Python README: `AttestSubstrate`, `EventDraft`, `SubjectRef`
- Project README TypeScript quickstart: `AttestSubstrate`, `makeEventDraft`,
  `makeSubjectRef`
- v0.0.2-alpha release notes: `ProofBundleBuilder`, `verifyProofBundle`

All documented symbols above are importable from the relevant root package.

## Asymmetries

- Python uses snake_case names and dataclass-style constructors; TypeScript uses
  camelCase factory/helper names where appropriate. This is an intentional SDK
  language convention; wire field names remain `snake_case`.
- Python root exports obligation registry and in-toto helpers that do not yet
  have TypeScript equivalents. Treat as P2 public API parity work, not a
  release blocker for v0.0.2-alpha.
- TypeScript root exports some package ergonomics (`VERSION`, `Signer`,
  `TrustRoots`) with different naming from Python. No documented example points
  at a missing symbol.

## Release Blockers

None found in this sweep.

## P2 Follow-Up

- Add a generated API-diff gate that compares Python `__all__`, TypeScript
  `index.ts`, and documented README snippets on every release branch.
- Decide whether obligation registry and in-toto helpers should gain
  TypeScript equivalents or be documented as Python-only.
