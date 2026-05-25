# `attestplane verify --json`

`attestplane verify --json` emits the machine-readable CI-gating contract for
`attestplane verify`. It is intentionally separate from the legacy
human-readable report fields, and it writes a single-line JSON object on
stdout. Stderr semantics are unchanged.

## Output Contract

The payload is fixed at schema version 1:

```json
{
  "schema_version": 1,
  "result": "pass",
  "failed_gates": [],
  "bundle_id": "p3-cli-proofbundle"
}
```

- `schema_version` is the CLI result schema version.
- `result` is `pass` or `fail`.
- `failed_gates[]` is an ordered list of `{gate, error_code}` entries.
- The stable gate names are `non_empty`, `strict_schema`, `canonicalization`,
  and `signature`.
- Stable CI-facing error codes include `E_EMPTY_BUNDLE`, `E_SCHEMA_INVALID`,
  `E_CANON_MISMATCH`, and `E_SIGNATURE_INVALID`.
- `bundle_id` is surfaced when the bundle carries a stable identifier in the
  verifier-visible metadata.
- `vector_id` is surfaced when a conformance harness provides one.
- When `--explain` is set, the payload also includes a top-level
  `explanation[]` array with `{primary_reason, pointer, message}` entries.
  On success, the array contains a compact summary; on rejection, it mirrors
  the ordered rejection reasons used by the human stdout/stderr path.

Consumers should keep branching on the process exit code first, then inspect
`result` and `failed_gates[]` for diagnostics.

## `verify --explain`

`verify --explain` is the operator-oriented companion to `verify --json`.
Use it with `--json` when a CI gate needs machine-readable output and a human
still needs a plain-language rejection summary.

Synopsis:

```sh
attestplane verify --json --explain "$bundle"
```

The flag is additive: it does not bump `schema_version`, it does not change
the `verify --json` contract, and it does not alter bundle forward-
compatibility rules. It also does not change the exit-code contract or stderr
semantics.

Within the shared `att.verify.*` reason-code taxonomy, additive unknown fields
remain accepted, while unsupported major versions and fail-closed
critical/required fields surface `att.verify.schema_version_unsupported` or
`att.verify.schema_unknown` respectively.

When the two flags are combined, stdout remains valid JSON and the rationale
text is carried in `explanation[]`.

When `--explain` is used without `--json`, stdout prints a compact
`OK|FAIL signer_subject=... schema_version=... anchor=...` summary and
stderr prints one rationale line per rejection reason in the same order as
the structured payload.

### Pass Example

```json
{
  "schema_version": 1,
  "result": "pass",
  "failed_gates": [],
  "bundle_id": "p3-cli-proofbundle",
  "explanation": [
    {
      "primary_reason": null,
      "pointer": "/",
      "message": "signer_subject=key_id:... schema_version=1 anchor=absent"
    }
  ]
}
```

### Fail Example

```json
{
  "schema_version": 1,
  "result": "fail",
  "failed_gates": [
    {
      "gate": "strict_schema",
      "error_code": "E_SCHEMA_INVALID"
    }
  ],
  "bundle_id": "p3-cli-proofbundle",
  "explanation": [
    {
      "primary_reason": "att.verify.schema_version_unsupported",
      "pointer": "/chain_metadata/schema_version",
      "message": "chain_metadata.schema_version=2; this verifier handles 1"
    }
  ]
}
```

The failure example uses the shared `att.verify.*` taxonomy documented in
[`docs/errors.md`](../errors.md), and the `verify --explain` surface itself
does not bump `schema_version`.

#### Paired `--explain` / `--json` rejection example

When an operator wants both the structured payload and the human summary, the
same rejection can be observed on stdout and stderr without changing the JSON
contract:

```sh
attestplane verify --json --explain "$bundle"
```

stderr:

```text
att.verify.schema_version_unsupported /chain_metadata/schema_version: chain_metadata.schema_version=2; this verifier handles 1
```

stdout:

```json
{
  "schema_version": 1,
  "result": "fail",
  "failed_gates": [
    {
      "gate": "strict_schema",
      "error_code": "E_SCHEMA_INVALID"
    }
  ],
  "bundle_id": "p3-cli-proofbundle",
  "explanation": [
    {
      "primary_reason": "att.verify.schema_version_unsupported",
      "pointer": "/chain_metadata/schema_version",
      "message": "chain_metadata.schema_version=2; this verifier handles 1"
    }
  ]
}
```

## CI Gating Example

```sh
attestplane verify --json "$bundle" > verify.json
rc=$?
result=$(jq -r '.result' verify.json)

if [ "$rc" -ne 0 ] || [ "$result" != "pass" ]; then
  printf 'verify failed (rc=%s, result=%s)\n' "$rc" "$result"
  jq -r '.failed_gates[]? | "\(.gate) \(.error_code)"' verify.json
  exit "$rc"
fi
```

## See Also

- [`docs/schema/verify-json.md`](../schema/verify-json.md) - schema-version
  policy for the v1 verifier JSON contract.
- [`schemas/cli/verify-result-v1.json`](../../schemas/cli/verify-result-v1.json)
  - JSON Schema for the structured result.
- [`docs/errors.md`](../errors.md) - `att.verify.*` reason-code taxonomy.
