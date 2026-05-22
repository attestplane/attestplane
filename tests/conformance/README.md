# Conformance Vectors

`tests/conformance/vectors/canonicalization/` is an additive opt-in suite for
strict minimum proof-bundle canonicalization checks. Downstream verifiers can
replay the `positive/` specs by emitting bundles through
`ProofBundleBuilder.minimal(...)`, and replay the `negative/` specs as
hand-crafted must-reject cases.

The issue #137 canonicalization set covers duplicate JSON keys, NFC versus NFD
payload strings, BOM or trailing bytes around canonical JSON, and signed-int64
timestamp-style payload boundaries. It is additive only: no schema bump and no
changes to existing v1.7.x fixture hashes.
