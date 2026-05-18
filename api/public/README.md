# Public API Manifest Gate

This directory freezes the `v0.0.2-alpha` public API surface used by the
Python and TypeScript SDKs.

The gate is intentionally lightweight:

- Python public API is extracted from `sdk/python/src/attestplane/__init__.py`
  and its root `__all__`.
- TypeScript public API is extracted from `sdk/typescript/src/index.ts`
  export declarations.
- Cross-language asymmetries are allowed only when recorded in
  `py_ts_allowlist_v1.json`.

This is not a claim that Python and TypeScript expose identical APIs. It is a
drift gate: future public API additions, removals, documentation changes, or
stability changes must update the manifest or allowlist deliberately.

Run locally:

```bash
scripts/check-public-api.sh
```

Manifests:

- `python_v1.json`
- `typescript_v1.json`
- `py_ts_allowlist_v1.json`

Forbidden drift includes:

- removing an `alpha_public` symbol without a deprecation note
- changing symbol stability silently
- documenting a symbol that is not exported
- exporting a new `alpha_public` symbol without a manifest update
