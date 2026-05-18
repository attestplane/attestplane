# Storage Compatibility Policy

## Current Backend

The current storage backend is Python `JsonlStorageBackend`, an alpha opt-in
JSON Lines backend. TypeScript does not ship a JSONL storage backend in this
release line.

This policy does not claim production storage, ACID behavior, database-grade
durability, crash-proof storage, or multi-writer correctness.

## Record Format Policy

JSONL record format `chained_event_jsonl.v1` is one newline-terminated JSON
object per `ChainedEvent`.

Required fields:

- `seq`
- `prev_hash_hex`
- `event_hash_hex`
- `event`

Existing v0.0.2-alpha rows have no explicit storage record version field and
remain accepted. If a future row includes `storage_record_version`, current
readers accept only `1`; unknown versions fail closed with
`unknown_record_version`.

## Scan Issue Policy

Storage scan issue format `storage_scan_issue.v1` uses the current Python
diagnostic fields:

- `kind`
- `line_no`
- `byte_offset`
- `detail`

Known issue kinds:

- `partial_trailing_line`
- `invalid_utf8`
- `malformed_json`
- `malformed_record`
- `missing_fields`
- `malformed_event`
- `unknown_record_version`

Readers must preserve/report unknown future issue codes rather than silently
treating them as storage success.

## Export Policy

ProofBundle export from JSONL storage is refused by default if scan issues are
present. The CLI reports `storage_corruption` and does not write the output
bundle.

## Unknown Version Policy

Unknown explicit storage record versions fail closed. Records without an
explicit version remain readable for v0.0.2-alpha compatibility.

## Migration Policy

Default migration policy is no destructive migration. Destructive repair,
truncate, compaction, or rewrite tooling must require explicit operator
confirmation if added later.

No downgrade support is promised.

## Repair / Truncate Policy

Automatic destructive repair is not implemented. The current scan path is
read-only and reports a valid prefix plus the first issue.

## Future Backend Policy

Future storage backends, including SQLite/Postgres or TypeScript storage
parity, require their own compatibility manifest update and tests. They must
not retroactively change JSONL v1 compatibility behavior.

## No-Go Claims

- production storage
- ACID
- database-grade durability
- multi-writer correctness
- automatic destructive repair
