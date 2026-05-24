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
