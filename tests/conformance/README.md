# Conformance Vectors

`tests/conformance/vectors/canonicalization/` is an additive opt-in suite for
strict canonicalization checks. Downstream verifiers can replay the `positive/`
specs by emitting bundles through `ProofBundleBuilder.minimal(...)`, and replay
the `negative/` specs as hand-crafted must-reject cases.

The negative canonicalization corpus is versioned under
`tests/conformance/vectors/canonicalization/negative/v1/`. Each vector records a
stable `case_id`, `expected.reason_code`, and `expected.pointer`, and the local
runner asserts both values before reporting success. Future taxonomy growth adds
new files under `v1/` or a later versioned subdirectory; existing vectors stay
frozen.

The full negative corpus also includes the non-versioned canonicalization edge
fixtures in `tests/conformance/vectors/canonicalization/negative/*.json`. Each
of those fixtures now carries an additive `expected_reason_code` field so the
matrix can verify the on-disk taxonomy binding directly. Their coverage is
tracked in `tests/conformance/canonicalization_negative_matrix.md` and enforced
by `scripts/check-conformance-matrix.sh`. The minimum-bundle regression test
also asserts that each landed vector rejects with that same stable reason code,
so the rejection contract and the matrix stay aligned.

The matrix is additive and frozen. If a future audit finds an uncovered edge
case, add a new negative vector, update the checked-in matrix, and keep the
fixture hash lock in sync in the same change.

The schema-version replay cases under `tests/conformance/schema_version/` are
likewise data-driven via `vectors.json`, which binds each case to its stable
expected reason code without changing the proof-bundle fixtures themselves.
Current selector IDs include `schema_version_additive_positive` for the
forward-compatible acceptance fixture and `schema_version_unknown_required`
for the regression guard that must continue to fail closed with
`att.verify.schema_unknown`.
